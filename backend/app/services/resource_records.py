"""Canonical metadata publication/projection; no provider or model-body reads.

Identity, path, hash and status remain authoritative ORM columns. Verification
is evidence bound to those columns and a measured file stat, never a second ID.
"""
from __future__ import annotations
from contextlib import contextmanager
import json
import math
from pathlib import Path
import re
from threading import RLock
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from pydantic import ValidationError
from app.db.models import DownloadedResource
from app.schemas.resources import (LicenseSnapshot, MeasuredEvidence, MetadataDiagnostic,
    Recommendation, ResourceMetadata, ResourceRecord)
from app.services.civitai_acquisition import redact_secrets
from app.services.resource_public_metadata import (public_name, public_words, recommendation_value,
    public_recommendations, public_license, public_diagnostics)

# Both stock callers share this Backend's admission boundary. The committed
# row owns subsequent work; this lock only serializes inspection/claim, never
# a model-body download. It is not a durable or cross-process reservation.
resource_admission = RLock()


@contextmanager
def bounded_resource_admission(operation):
    """Wait only within the caller's existing budget; release only our level.

    Direct legacy service calls without an operation can enter an available lock
    immediately, but cannot wait without an applicable absolute deadline.
    """
    from app.services.civitai_provider import _timeout_error
    remaining = operation.remaining() if operation is not None else 0
    if not resource_admission.acquire(timeout=remaining):
        raise _timeout_error()
    try:
        if operation is not None:
            operation.remaining()
        yield
    finally:
        resource_admission.release()

# The sole Phase 2 inference table. Recipe/Anima adapters are explicitly legacy.
WORKFLOW_FAMILIES = {'sdxl 1.0':'sdxl', 'illustrious':'sdxl', 'pony':'sdxl', 'noobai':'sdxl'}
LICENSE_FIELDS = ('allowNoCredit','allowCommercialUse','allowDerivatives','allowDifferentLicense')
SHA256 = re.compile(r'^[0-9a-fA-F]{64}$')


def workflow_family(label: Any) -> str | None:
    return WORKFLOW_FAMILIES.get(label.strip().casefold()) if isinstance(label,str) else None


_TRANSPORT_FIELDS = {'authorization','proxy-authorization','cookie','set-cookie',
                     'token','api_key','apikey','x-api-key'}


def safe_text(value: str) -> str:
    return safe_evidence(value)


def safe_evidence(value: Any) -> Any:
    """Bounded transport filtering and exact held-key replacement; no recognizer."""
    from app.services.civitai_provider import resolve_credentials, CivitaiProviderError
    try:
        authorization=resolve_credentials()
    except CivitaiProviderError:
        authorization=None  # unreadable credentials cannot make legacy reads fail
    secrets=tuple(v for v in (authorization,(authorization or '').split(' ',1)[-1]) if v)
    def locator(url):
        try:
            p=urlsplit(url)
            if not p.hostname: return '[redacted locator]'
            return urlunsplit((p.scheme,p.netloc.rsplit('@',1)[-1],p.path,'',''))
        except ValueError:
            return '[redacted locator]'
    def clean(item):
        if isinstance(item,dict):
            return {clean(k):clean(v) for k,v in item.items()
                    if isinstance(k,str) and k.casefold() not in _TRANSPORT_FIELDS}
        if isinstance(item,list): return [clean(v) for v in item]
        if isinstance(item,str):
            # Received locators are whole values; do not tokenize their query.
            if re.fullmatch(r'https?://\S+',item,flags=re.I):
                item=locator(item)
            else:
                # Apostrophes are legal URL characters, including in queries.
                item=re.sub(r'https?://[^\s<>"]+',lambda m:locator(m[0]),item,flags=re.I)
            return redact_secrets(item,secrets=secrets,redact_query=False)
        if isinstance(item,float) and not math.isfinite(item): return None
        if item is None or isinstance(item,(bool,int,float)): return item
        return None
    return clean(value)


def normalize_metadata(snapshot: ResourceMetadata) -> ResourceMetadata:
    """Keep internal acquisition state while bounding public metadata values."""
    snapshot=ResourceMetadata.model_validate(safe_evidence(snapshot.model_dump(mode='json')))
    errors=list(snapshot.diagnostics)
    params=public_recommendations(snapshot.recommended_parameters,errors)
    license=public_license(snapshot.license,errors)
    return snapshot.model_copy(update={'base_model':safe_text(public_name(snapshot.base_model)) if snapshot.base_model is not None else None,
        'trigger_words':safe_evidence(public_words(snapshot.trigger_words)),'recommended_parameters':params,'license':license,
        'diagnostics':public_diagnostics(errors)})


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
          'width':'width','height':'height','clip_skip':'clip_skip','clipSkip':'clip_skip'}
    opaque={}
    for origin,raw in [('version.meta',version.get('meta')),('file.metadata',file.get('metadata'))]:
        if raw is None: continue
        if not isinstance(raw,dict):
            errors.append(diagnostic('invalid_recommendations',origin)); continue
        opaque[origin]=safe_evidence(raw)
        for key,target in keys.items():
            if key not in raw: continue
            val=raw[key]
            if isinstance(val,str): val=val.strip()
            valid=recommendation_value(target,val)
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
        license_values[key]=safe_evidence(val)
    missing=[k for k in LICENSE_FIELDS if k not in license_values]
    if missing: errors.append(diagnostic('license_incomplete','license'))
    from app.services.civitai_download_policy import selected_size
    size=selected_size(file)
    if size is None:
        errors.append(diagnostic('invalid_declared_size' if ('size' in file or 'sizeKB' in file) else 'missing_declared_size','declared_size_bytes'))
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


def measured_evidence(path: Path, size: int, sha256: str, *, identity=None) -> MeasuredEvidence:
    stat=path.stat()
    if identity is not None:
        from app.services.civitai_safe_download import file_identity, _matches
        if file_identity(stat)!=identity or not _matches(path, identity):
            from app.services.civitai_download_policy import download_error
            raise download_error('civitai_file_changed', 'Final changed while recording measured evidence')
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
    errors=public_diagnostics(errors)
    return ResourceRecord(resource_id=row.id,resource_name=public_name(safe_text(public_name(row.resource_name))),resource_type=public_name(safe_text(public_name(row.resource_type))),
        provider=public_name(safe_text(public_name(row.provider))) if row.provider else None,
        source_url=f"https://civitai.com/models/{ids['model_id']}?modelVersionId={ids['version_id']}" if ids['model_id'] and ids['version_id'] else None,
        model_id=ids['model_id'],version_id=ids['version_id'],civitai_file_id=ids['civitai_file_id'],air=public_name(safe_text(public_name(row.air))) if row.air else None,
        base_model=base,model_family=family,sha256=sha,sha256_verified=verified,
        declared_size_bytes=snap.declared_size_bytes if snap else None,measured_size_bytes=measured.size_bytes if measured else None,
        status=safe_text(row.status),installed=row.status in {'installed','available'},local_path=safe_text(row.local_path) if row.local_path else None,
        path_available=available,trigger_words=snap.trigger_words if snap else [],recommended_parameters=snap.recommended_parameters if snap else {},
        license=public_license(snap.license,[]) if snap else public_license(LicenseSnapshot(),[]),
        metadata_origin=snap.origin if snap else None,metadata_version=snap.version if snap else None,
        diagnostics=errors)


_PARTIAL_UNSET = object()


def download_context(row, size, sha256):
    """Resume authority is the existing resource row, never public path text."""
    association = {'provider': row.provider, 'model_id': row.model_id, 'version_id': row.version_id,
                   'file_id': row.civitai_file_id, 'resource_id': row.id,
                   'size': size, 'sha256': sha256.lower()}
    snapshot, _ = metadata_for(row)
    outcome = snapshot.source_evidence.get('acquisition') if snapshot else None
    partial = outcome.get('partial') if isinstance(outcome, dict) else None
    return association, partial


def publish_download_state(row, status, error=None, *, measured=None, partial=_PARTIAL_UNSET):
    snapshot, _ = metadata_for(row)
    snapshot = snapshot or ResourceMetadata(origin='legacy_notes')
    previous = snapshot.source_evidence.get('acquisition')
    if partial is _PARTIAL_UNSET:
        partial = previous.get('partial') if isinstance(previous, dict) else None
    operation = {'status': status, 'error': error}
    if partial is not None and status != 'installed':
        operation['partial'] = partial
    publish_metadata(row, snapshot, measured=measured, operation=operation)
