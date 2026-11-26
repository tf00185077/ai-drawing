"""Bounded, read-only projection of the existing Backend resource rows."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BeforeValidator, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import DownloadedResource
from app.schemas.resources import ResourceList, ResourceRecord
from app.services.resource_records import WORKFLOW_FAMILIES, project_resource


class ResourceValidationRoute(APIRoute):
    def get_route_handler(self):
        handler=super().get_route_handler()
        async def sanitized(request: Request):
            try: return await handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422,content={'detail':{'code':'invalid_resource_query',
                    'message':'Resource selectors must match the documented types and bounds.',
                    'hint':'Use the list/detail parameters in /openapi.json.'}})
        return sanitized


# Python str.strip whitespace, used identically by the SQL filter and projection.
_OUTER_WHITESPACE = ' \t\n\r\v\f\x1c\x1d\x1e\x1f\x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000'

router=APIRouter(prefix='/api/resources',tags=['resources'],route_class=ResourceValidationRoute)


def trim(value):
    return value.strip() if isinstance(value,str) else value


def integer(value):
    if isinstance(value,str):
        import re
        if re.fullmatch(r'[+-]?[0-9]+',value.strip()) is None: raise ValueError('integer required')
    return value


TextFilter=Annotated[str,BeforeValidator(trim),Field(min_length=1)]
FamilyFilter=Annotated[Literal['sdxl'],BeforeValidator(trim)]
HashFilter=Annotated[str,BeforeValidator(trim),Field(pattern=r'^[0-9a-fA-F]{64}$')]


def _json_object(column):
    # Malformed legacy JSON is readable as incomplete, never a SQL error/repair.
    return case((func.json_valid(column)==1,column),else_='{}')


def _base_expression():
    resource=DownloadedResource
    legacy=_json_object(resource.notes)
    metadata=_json_object(resource.metadata_json)
    raw=case((resource.metadata_json.is_not(None),func.json_extract(metadata,'$.base_model')),
             else_=case((func.json_type(legacy,'$.base_model').is_not(None),func.json_extract(legacy,'$.base_model')),
                        else_=func.json_extract(legacy,'$.model_family')))
    raw_type=case((resource.metadata_json.is_not(None),func.json_type(metadata,'$.base_model')),
                  else_=case((func.json_type(legacy,'$.base_model').is_not(None),func.json_type(legacy,'$.base_model')),
                             else_=func.json_type(legacy,'$.model_family')))
    return case((raw_type=='text',raw),else_=None)


@router.get('',response_model=ResourceList)
def list_resources(request: Request,
    limit: Annotated[int,Query(ge=1,le=100),BeforeValidator(integer)]=25,
    offset: Annotated[int,Query(ge=0),BeforeValidator(integer)]=0,
    resource_type: Annotated[TextFilter | None,Query()]=None,
    provider: Annotated[TextFilter | None,Query()]=None,
    base_model: Annotated[TextFilter | None,Query()]=None,
    model_family: Annotated[FamilyFilter | None,Query()]=None,
    status: Annotated[TextFilter | None,Query()]=None,
    sha256: Annotated[HashFilter | None,Query()]=None,
    db: Session=Depends(get_db)) -> ResourceList:
    allowed={'limit','offset','resource_type','provider','base_model','model_family','status','sha256'}
    if set(request.query_params)-allowed:
        raise HTTPException(422,detail={'code':'invalid_resource_query','message':'Unknown resource selector',
                                      'hint':'Use the documented exact filters.'})
    query=db.query(DownloadedResource)
    for column,value in [(DownloadedResource.resource_type,resource_type),(DownloadedResource.provider,provider),
                         (DownloadedResource.status,status)]:
        if value is not None: query=query.filter(func.trim(column,_OUTER_WHITESPACE)==value)
    base=_base_expression()
    if base_model is not None: query=query.filter(func.trim(base,_OUTER_WHITESPACE)==base_model)
    if model_family is not None:
        query=query.filter(func.lower(func.trim(base,_OUTER_WHITESPACE)).in_(tuple(WORKFLOW_FAMILIES)))
    if sha256 is not None: query=query.filter(func.lower(DownloadedResource.sha256)==sha256.lower())
    total=query.count()
    rows=query.order_by(DownloadedResource.id.asc()).limit(limit).offset(offset).all()
    return ResourceList(items=[project_resource(row) for row in rows],total=total,limit=limit,offset=offset)


@router.get('/{resource_id}',response_model=ResourceRecord)
def resource_detail(resource_id: Annotated[int,PathParam(ge=1),BeforeValidator(integer)],
                    db: Session=Depends(get_db)) -> ResourceRecord:
    row=db.get(DownloadedResource,resource_id)
    if row is None:
        raise HTTPException(404,detail={'code':'resource_not_found','message':'Resource record was not found.',
                                      'hint':'List /api/resources and use an existing resource_id.'})
    return project_resource(row)
