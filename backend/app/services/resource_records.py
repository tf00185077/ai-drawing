"""Canonical metadata publication/projection; no provider or model-body reads.

Identity, path, hash and status remain authoritative ORM columns. Verification
is evidence bound to those columns and a measured file stat, never a second ID.
"""
from __future__ import annotations
import base64
import json
import math
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from pydantic import ValidationError
from app.db.models import DownloadedResource
from app.schemas.resources import (LicenseSnapshot, MeasuredEvidence, MetadataDiagnostic,
    Recommendation, ResourceMetadata, ResourceRecord)
from app.services.civitai_acquisition import redact_secrets

# The sole Phase 2 inference table. Recipe/Anima adapters are explicitly legacy.
WORKFLOW_FAMILIES = {'sdxl 1.0':'sdxl', 'illustrious':'sdxl', 'pony':'sdxl', 'noobai':'sdxl'}
LICENSE_FIELDS = ('allowNoCredit','allowCommercialUse','allowDerivatives','allowDifferentLicense')
SHA256 = re.compile(r'^[0-9a-fA-F]{64}$')
# A recognizable credential-bearing string is a complete safety unit. Token
# boundaries cannot identify the end of cookies, quoted values or auth schemes.
_IDENTIFIER_UNIT = r"(?:[\w.-]|\\(?:u[0-9a-fA-F]{4}|[bfnrt]))"
_ASSIGNMENT_LABEL = re.compile(
    r"(?<![\w.-])(?P<quote>[\"']?)(?P<label>" + _IDENTIFIER_UNIT + r"+"
    r"(?:\s+" + _IDENTIFIER_UNIT + r"+)*)"
    r"(?P=quote)\s*(?P<delimiter>[:=]?)",
)
_LABEL_ESCAPE = re.compile(r'\\(u[0-9a-fA-F]{4}|["\'\\/bfnrt])')
_LABEL_ESCAPES = {'"':'"', "'":"'", '\\':'\\', '/':'/', 'b':'\b',
                  'f':'\f', 'n':'\n', 'r':'\r', 't':'\t'}
_BEARER_AUTH = re.compile(r'\bbearer\s+\S', re.I)
_BASIC_AUTH = re.compile(r'\bbasic\s+([A-Za-z0-9+/]+={0,2})(?=$|[\s,;])', re.I)
_SENSITIVE = re.compile(
    r'(?:token|secret|authorization|password|credential|signature|cookie|api[\s_.-]*key)'
    r'(?=$|[\s_.-])', re.I,
)


def credential_label(label: str) -> bool:
    """One conservative identifier policy for keys and assignment/header labels.

    Split camelCase/acronym transitions, then recognize credential suffixes of
    identifier components (space, underscore, dot or hyphen separated). Prefixes
    need no word boundary; trailing letters do: tokenizer/api_keyboard are safe.
    """
    label = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', label.strip().strip('\"\''))
    label = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', label)
    return bool(_SENSITIVE.search(label))


def _assignment_in_view(value: str) -> bool:
    if ':' not in value and '=' not in value:
        return False  # no assignment delimiter in this recognition view
    # Decode serialized labels once, as lexical string content. Literal tabs and
    # other Unicode whitespace already have their ordinary key-policy meaning.
    def decode(match):
        escape = match[1]
        return chr(int(escape[1:], 16)) if escape.startswith('u') else _LABEL_ESCAPES[escape]
    # Adjacent same-kind quote boundaries are local label candidates, independent
    # of any enclosing prose pairing. A closing quote also remains the next
    # possible opener; unrelated prose cannot consume a real label's boundary.
    # Both literal boundaries and escape-aware boundaries are candidates: an
    # unrelated preceding backslash cannot hide an unchanged label opener.
    # Each pass advances monotonically; spans/lookaheads within it do not overlap.
    length = len(value)
    for quote in ('"', "'"):
        for escape_aware in (True, False):
            start = None
            # Match only boundaries/escape units; ordinary spans advance in C.
            # The optional escape payload also consumes a lone backslash at EOF.
            pattern = r'\\[\s\S]?|' + re.escape(quote) if escape_aware else re.escape(quote)
            for boundary in re.finditer(pattern, value):
                if escape_aware and boundary[0].startswith("\\"):
                    continue
                position = boundary.start()
                delimiter = position + 1
                while delimiter < length and value[delimiter].isspace():
                    delimiter += 1
                if start is not None and delimiter < length and value[delimiter] in ':=':
                    label = _LABEL_ESCAPE.sub(decode, value[start + 1:position])
                    if credential_label(label):
                        return True
                start = position
    # Inspect unquoted assignments too, including those inside a quoted value.
    # Maximal token runs prevent retrying long ordinary prose at every word.
    return any(match['delimiter'] and credential_label(_LABEL_ESCAPE.sub(decode, match['label']))
               for match in _ASSIGNMENT_LABEL.finditer(value))


def _credential_assignment(value: str) -> bool:
    """Bounded raw/once-serialized and local-unit candidates; original output stays."""
    seen = set()
    def inspect(view):
        if view in seen:
            return False
        seen.add(view)
        return _assignment_in_view(view)
    if inspect(value):
        return True
    if "\\" not in value:
        return False
    decoded = _json_string_view(value)
    if inspect(decoded):
        return True
    literal_units = _json_string_view(value, escape_aware=False)
    if inspect(literal_units):
        return True
    def decode(match):
        escape = match[1]
        return chr(int(escape[1:], 16)) if escape.startswith('u') else _LABEL_ESCAPES[escape]
    escaped = _LABEL_ESCAPE.sub(decode, value)
    if inspect(escaped):
        return True
    # Fixed lexical/local-unit stages cover a once-serialized unit fragment and
    # escaped text adjacent to a raw unit. No view is fed back until stable:
    # each original has at most two boundary interpretations at either stage.
    for units in (decoded, literal_units):
        if inspect(_LABEL_ESCAPE.sub(decode, units)):
            return True
    if escaped != value:
        for unit_escape_aware in (True, False):
            if inspect(_json_string_view(escaped, escape_aware=unit_escape_aware)):
                return True
    return False


def _json_string_view(value: str, *, escape_aware: bool = True) -> str:
    """Decode adjacent escaped JSON units independently of prose quote pairing.

    Consecutive quote boundaries delimit local candidates with disjoint interiors.
    A quote may end one candidate and begin the next; it is never consumed by
    unrelated prose. Valid escaped units remove their own envelope boundaries.
    Shared boundaries are removed once, without enumerating combined views.
    This recognition-only view never replaces useful original public text.
    """
    parts = []
    previous = None
    pattern = r'\\[\s\S]?|"' if escape_aware else '"'
    for boundary in re.finditer(pattern, value):
        if escape_aware and boundary[0].startswith("\\"):
            continue
        position = boundary.start()
        if previous is None:
            parts.extend((value[:position], '"'))
        else:
            content = value[previous + 1:position]
            decoded = None
            if "\\" in content:
                try:
                    decoded = json.loads('"' + content + '"')
                except ValueError:
                    pass
            if decoded is None:
                parts.extend((content, '"'))
            else:
                parts[-1] = ''  # preceding envelope, possibly already removed
                parts.extend((decoded, ''))
        previous = position
    if previous is None:
        return value
    parts.append(value[previous + 1:])
    return ''.join(parts)


def workflow_family(label: Any) -> str | None:
    return WORKFLOW_FAMILIES.get(label.strip().casefold()) if isinstance(label,str) else None


def safe_text(value: str) -> str:
    def locator(match):
        try:
            p=urlsplit(match[0]); host=p.hostname
            if not host: return '[redacted locator]'
            return urlunsplit((p.scheme,host,p.path,'',''))
        except ValueError:
            return '[redacted locator]'
    value = re.sub(r'https?://[^\s<>"\']+', locator, value, flags=re.I)
    # Credentials in free-form nested strings are not necessarily URL queries.
    # Consume ordinary token runs too: requiring a delimiter in the regex would
    # retry a long unassigned description at every word. Only assignments count.
    if _credential_assignment(value) or _BEARER_AUTH.search(value):
        return '[redacted credential]'
    # A bare Basic scheme is recognizable when its base64 contains user:password;
    # natural language such as "basic painting" is ordinary metadata.
    for match in _BASIC_AUTH.finditer(value):
        try:
            if b':' in base64.b64decode(match[1], validate=True):
                return '[redacted credential]'
        except ValueError:
            pass
    return redact_secrets(value)


def safe_evidence(value: Any) -> Any:
    if isinstance(value,dict):
        return {safe_text(k):safe_evidence(v) for k,v in value.items()
                if isinstance(k,str) and not credential_label(k) and safe_text(k) != '[redacted credential]'}
    if isinstance(value,list): return [safe_evidence(v) for v in value]
    if isinstance(value,str): return safe_text(value)
    if isinstance(value,float) and not math.isfinite(value): return None
    if value is None or isinstance(value,(bool,int,float)): return value
    return None


def normalize_metadata(snapshot: ResourceMetadata) -> ResourceMetadata:
    """Validate and sanitize every nested value, including keys and diagnostics.

    Typed client input and old stored snapshots have the same secrecy boundary.
    Ordinary hashes and safe opaque evidence retain their values. Revalidation
    fails closed if normalization cannot preserve the typed contract.
    """
    return ResourceMetadata.model_validate(safe_evidence(snapshot.model_dump(mode='json')))


def diagnostic(code: str, field: str) -> MetadataDiagnostic:
    return MetadataDiagnostic(code=code,field=field)


def provider_snapshot(version: dict, model: dict | None, file: dict) -> ResourceMetadata:
    """Only the actual selected version/file, never sample-image generation data."""
    errors=[]; label=version.get('baseModel')
    if label is not None and not isinstance(label,str): errors.append(diagnostic('invalid_base_model','base_model'))
    words=[]; trained=version.get('trainedWords')
    if trained is None: errors.append(diagnostic('missing_trigger_words','trainedWords'))
    elif not isinstance(trained,list): errors.append(diagnostic('invalid_trigger_words','trainedWords'))
    else:
        for word in trained:
            if not isinstance(word,str) or not word.strip():
                errors.append(diagnostic('invalid_trigger_word','trainedWords')); continue
            word=safe_text(word.strip())
            if word not in words: words.append(word)
    params={}; conflicts=set()
    # These source keys are explicit metadata, not image prompts or inferred defaults.
    keys={'sampler':'sampler','scheduler':'scheduler','steps':'steps','cfgScale':'cfg','cfg':'cfg',
          'width':'width','height':'height','strength':'lora_strength','loraStrength':'lora_strength'}
    opaque={}
    for origin,raw in [('version.meta',version.get('meta')),('file.metadata',file.get('metadata'))]:
        if raw is None: continue
        if not isinstance(raw,dict):
            errors.append(diagnostic('invalid_recommendations',origin)); continue
        opaque[origin]=safe_evidence(raw)
        for key,target in keys.items():
            if key not in raw: continue
            val=raw[key]
            valid=(isinstance(val,str) and bool(val.strip())) if target in {'sampler','scheduler'} else (
                type(val) is int and val>0 if target in {'steps','width','height'} else
                type(val) in {int,float} and math.isfinite(val))
            if not valid:
                errors.append(diagnostic('invalid_recommendation',origin+'.'+key)); continue
            recommendation=Recommendation(value=safe_text(val.strip()) if isinstance(val,str) else val, source_field=origin+'.'+key)
            if target in conflicts: continue
            if target in params and params[target].value!=recommendation.value:
                errors.append(diagnostic('conflicting_recommendation',target)); params.pop(target); conflicts.add(target); continue
            params[target]=recommendation
    model=model or {}; license_values={}
    for key in LICENSE_FIELDS:
        val=model.get(key)
        if val is None: continue
        valid = (isinstance(val,str) or (isinstance(val,list) and all(isinstance(v,str) for v in val))) if key=='allowCommercialUse' else type(val) is bool
        if valid: license_values[key]=safe_evidence(val)
        else: errors.append(diagnostic('invalid_license_field','license.'+key))
    if file.get('license') is not None: license_values['file_license']=safe_evidence(file['license'])
    if model.get('license') is not None: license_values['model_license']=safe_evidence(model['license'])
    missing=[k for k in LICENSE_FIELDS if k not in license_values]
    if missing: errors.append(diagnostic('license_incomplete','license'))
    size=file.get('size')
    if size is None and type(file.get('sizeKB')) in {int,float}:
        size=file['sizeKB']*1024
    if type(size) in {int,float} and math.isfinite(size) and size>=0: size=int(round(size))
    else:
        size=None; errors.append(diagnostic('invalid_declared_size' if ('size' in file or 'sizeKB' in file) else 'missing_declared_size','declared_size_bytes'))
    return normalize_metadata(ResourceMetadata(origin='civitai_provider',base_model=safe_text(label) if isinstance(label,str) else None,
        declared_size_bytes=size,trigger_words=words,recommended_parameters=params,
        license=LicenseSnapshot(values=license_values,missing_fields=missing),source_evidence=opaque,diagnostics=errors))


class ResourceIdentityConflict(ValueError):
    pass


def assert_identity(row: DownloadedResource, identity: dict[str,Any]) -> None:
    for field,value in identity.items():
        current=getattr(row,field)
        if current is not None and value is not None:
            a,b=(str(current).lower(),str(value).lower()) if field=='sha256' else (str(current),str(value))
            if a!=b: raise ResourceIdentityConflict('resource_identity_conflict')


def measured_evidence(path: Path, size: int, sha256: str) -> MeasuredEvidence:
    stat=path.stat()
    if stat.st_size!=size: raise ValueError('measured_size_conflict')
    return MeasuredEvidence(sha256=sha256.lower(),size_bytes=size,mtime_ns=stat.st_mtime_ns,inode=stat.st_ino)


def publish_metadata(row: DownloadedResource, snapshot: ResourceMetadata, *, identity: dict | None=None,
                     measured: MeasuredEvidence | None=None, operation: dict | None=None) -> None:
    """Augment this row only; caller owns its transaction and identity columns."""
    snapshot = normalize_metadata(snapshot)
    assert_identity(row,identity or {})
    if measured is not None:
        assert_identity(row,{'sha256':measured.sha256})
        if row.file_size!=measured.size_bytes: raise ResourceIdentityConflict('resource_identity_conflict')
    previous = None
    if row.metadata_json:
        try: previous = normalize_metadata(ResourceMetadata.model_validate_json(row.metadata_json))
        except ValidationError: pass
    if measured is None and previous is not None:
        measured = previous.verification
    evidence = {k:v for k,v in snapshot.source_evidence.items() if k != 'acquisition'}
    if previous is not None and 'acquisition' in previous.source_evidence:
        evidence['acquisition'] = previous.source_evidence['acquisition']
    if operation is not None:
        evidence['acquisition'] = safe_evidence(operation)
    snapshot = snapshot.model_copy(update={'source_evidence': evidence})
    for field, value in (identity or {}).items():
        if getattr(row,field) is None and value is not None: setattr(row,field,value)
    value=snapshot.model_copy(update={'verification':measured}).model_dump_json()
    if row.metadata_json!=value: row.metadata_json=value


def legacy_metadata(row: DownloadedResource) -> ResourceMetadata | None:
    if not row.notes: return None
    try: notes=json.loads(row.notes)
    except (ValueError,TypeError):
        return ResourceMetadata(origin='legacy_notes',diagnostics=[diagnostic('malformed_legacy_notes','notes')])
    if not isinstance(notes,dict):
        return ResourceMetadata(origin='legacy_notes',diagnostics=[diagnostic('malformed_legacy_notes','notes')])
    errors=[]
    base=notes.get('base_model',notes.get('model_family'))
    # Only explicit legacy source fields; frozen normalized enums are not inferred back to provider labels.
    version={'baseModel':base,'trainedWords':notes.get('trainedWords',notes.get('trigger_words')),
             'meta':notes.get('recommended_parameters')}
    file={'size':notes.get('expected_size_bytes')}
    snap=provider_snapshot(version,notes.get('license') if isinstance(notes.get('license'),dict) else None,file)
    for field,key in [('model_id','civitai_model_id'),('version_id','civitai_model_version_id'),('civitai_file_id','civitai_file_id'),('sha256','sha256')]:
        if key in notes and getattr(row,field) is not None and str(notes[key]).lower()!=str(getattr(row,field)).lower():
            errors.append(diagnostic('conflicting_legacy_identity',key))
    if notes.get('base_model') is not None and notes.get('model_family') is not None:
        from app.services.civitai_resource_legacy import normalize_model_family
        old=notes['model_family']
        compatible = {base.strip().casefold(), workflow_family(base), normalize_model_family(base)} if isinstance(base,str) else set()
        if not isinstance(old,str) or old.strip().casefold() not in compatible:
            errors.append(diagnostic('conflicting_legacy_metadata','base_model'))
    return snap.model_copy(update={'origin':'legacy_notes','diagnostics':snap.diagnostics+errors})


def metadata_for(row: DownloadedResource) -> tuple[ResourceMetadata | None,list[MetadataDiagnostic]]:
    if row.metadata_json is None: return legacy_metadata(row),[]
    try: return normalize_metadata(ResourceMetadata.model_validate_json(row.metadata_json)),[]
    except ValidationError: return None,[diagnostic('invalid_metadata','metadata')]


def canonical_base_model(metadata_json: str | None, notes: str | None) -> str | None:
    """Pure SQLite scalar: use the projection's typed parser before SQL paging.

    This transient object is never attached to a session; parsing reads no DB,
    provider or model file. Invalid typed metadata never falls back to notes.
    """
    snapshot, _ = metadata_for(DownloadedResource(metadata_json=metadata_json, notes=notes))
    return snapshot.base_model if snapshot else None


def project_resource(row: DownloadedResource) -> ResourceRecord:
    snap,errors=metadata_for(row)
    if snap is None: errors.append(diagnostic('missing_metadata','metadata'))
    else: errors+=snap.diagnostics
    base=snap.base_model if snap else None
    family=workflow_family(base)
    if family is None: errors.append(diagnostic('no_matching_workflow','base_model'))
    ids={}
    for field in ('model_id','version_id','civitai_file_id'):
        val=getattr(row,field)
        if isinstance(val,str) and val.isdecimal() and int(val)>0: ids[field]=val
        else:
            ids[field]=None
            errors.append(diagnostic('missing_provider_identity' if val is None else 'invalid_provider_identity',field))
    sha=row.sha256.lower() if isinstance(row.sha256,str) and SHA256.fullmatch(row.sha256) else None
    if sha is None: errors.append(diagnostic('missing_or_invalid_sha256','sha256'))
    available=None; stat=None
    if row.local_path:
        try:
            p=Path(row.local_path); available=p.is_file(); stat=p.stat() if available else None
        except OSError: available=False
    if available is not True: errors.append(diagnostic('path_unavailable','local_path'))
    measured=snap.verification if snap else None
    verified=None
    if measured and sha==measured.sha256 and row.file_size==measured.size_bytes and stat and (
        stat.st_size,stat.st_mtime_ns,stat.st_ino)==(measured.size_bytes,measured.mtime_ns,measured.inode): verified=True
    if verified is None: errors.append(diagnostic('verification_unknown','sha256'))
    # Diagnostics are codes/field names only. Never expose notes or validation input.
    errors=list({(d.code,d.field):d for d in errors}.values())
    return ResourceRecord(resource_id=row.id,resource_name=safe_text(row.resource_name),resource_type=safe_text(row.resource_type),
        provider=safe_text(row.provider) if row.provider else None,source_url=safe_text(row.source_url) if row.source_url else None,
        model_id=ids['model_id'],version_id=ids['version_id'],civitai_file_id=ids['civitai_file_id'],air=safe_text(row.air) if row.air else None,
        base_model=base,model_family=family,sha256=sha,sha256_verified=verified,
        declared_size_bytes=snap.declared_size_bytes if snap else None,measured_size_bytes=measured.size_bytes if measured else None,
        status=row.status,installed=row.status in {'installed','available'},local_path=safe_text(row.local_path) if row.local_path else None,
        path_available=available,trigger_words=snap.trigger_words if snap else [],recommended_parameters=snap.recommended_parameters if snap else {},
        license=snap.license if snap else LicenseSnapshot(missing_fields=list(LICENSE_FIELDS)),
        metadata_origin=snap.origin if snap else None,metadata_version=snap.version if snap else None,
        source_evidence=safe_evidence(snap.source_evidence) if snap else {},diagnostics=errors)
