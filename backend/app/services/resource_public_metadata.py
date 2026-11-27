"""Closed public shapes; legacy snapshot storage remains a separate contract."""
import math
import re
import unicodedata
from typing import get_args

from app.schemas.resources import (DiagnosticCode, DiagnosticField, LicenseField,
    LicensePermission, PublicDiagnostic, PublicLicenseSnapshot, PublicRecommendation)

LICENSE_FIELDS = get_args(LicenseField)
PARAMETER_RANGES = {'steps':(1,150), 'cfg':(1,30), 'width':(256,2048),
                    'height':(256,2048), 'clip_skip':(1,24)}
PARAMETER_NAMES = re.compile(r'^[A-Za-z0-9_+. -]{1,64}$')


def public_name(value):
    return ''.join(c for c in value if unicodedata.category(c) != 'Cc')[:200]


def public_words(words):
    return list(dict.fromkeys(word for value in words if (word := public_name(value.strip()))))[:32]


def recommendation_value(key, value):
    if key in {'sampler','scheduler'}:
        return isinstance(value,str) and PARAMETER_NAMES.fullmatch(value) is not None
    if key not in PARAMETER_RANGES:
        return False
    lo,hi=PARAMETER_RANGES[key]
    return (type(value) in ({int,float} if key=='cfg' else {int})
            and lo<=value<=hi and math.isfinite(value))


def public_recommendations(params, errors):
    result={}
    for key, rec in params.items():
        if not recommendation_value(key,rec.value):
            errors.append(PublicDiagnostic(code='invalid_recommendation',field='recommended_parameters'))
            continue
        # Preserve explicit provenance from the two supported metadata sources.
        source=rec.source_field
        valid_sources={origin+'.'+name for origin in ('version.meta','file.metadata')
                       for name in (key,'cfgScale' if key=='cfg' else 'clipSkip' if key=='clip_skip' else key)}
        result[key]=PublicRecommendation(value=rec.value,source_field=source if source in valid_sources else key)
    return result


def public_license(license, errors):
    values={}
    for key in LICENSE_FIELDS:
        value=license.values.get(key)
        valid=(type(value) is bool or isinstance(value,str) and value in get_args(LicensePermission)
               or isinstance(value,list) and all(isinstance(v,str) and v in get_args(LicensePermission) for v in value))
        if valid:
            values[key]=value
        elif key in license.values:
            errors.append(PublicDiagnostic(code='invalid_license_field',field='license'))
    missing=[key for key in LICENSE_FIELDS if key not in values]
    if missing:
        errors.append(PublicDiagnostic(code='license_incomplete',field='license'))
    return PublicLicenseSnapshot(values=values,missing_fields=missing)


def public_diagnostics(errors):
    aliases={'trainedWords':'trigger_words','notes':'metadata_origin','metadata':'metadata_version',
             'civitai_model_id':'model_id','civitai_model_version_id':'version_id'}
    result={}
    for error in errors:
        if error.code not in get_args(DiagnosticCode):
            continue
        field=aliases.get(error.field,error.field)
        if field.startswith('license.'):
            field='license'
        if field in {'version.meta','file.metadata'} or field.startswith(('version.meta.','file.metadata.')) or field in PARAMETER_RANGES or field in {'sampler','scheduler'}:
            field='recommended_parameters'
        if field in get_args(DiagnosticField):
            result[error.code,field]=PublicDiagnostic(code=error.code,field=field)
    return list(result.values())
