"""Closed bootstrap deliberately imports no product Settings or state consumers."""
import os
import uuid
import hashlib
from pathlib import Path
from fastapi import FastAPI
from starlette.responses import JSONResponse


def closed_app():
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    digest=hashlib.sha256()
    for file in sorted(Path(__file__).parent.rglob('*.py')):
        digest.update(str(file.relative_to(Path(__file__).parent)).encode());digest.update(file.read_bytes())
    status={'schema_version':1,'state':'closed','active':{},'uncertain':{},
            'owner':os.environ.get('AI_DRAWING_MAINTENANCE_OWNER','backend'),
            'epoch':os.environ.get('AI_DRAWING_MAINTENANCE_EPOCH') or str(uuid.uuid4()),
            'version':digest.hexdigest(), 'legacy_process_certified':False}
    @app.middleware('http')
    async def deny(request,call_next):
        if request.url.path=='/maintenance/status' and request.method=='GET':
            return JSONResponse(status)
        return JSONResponse({'detail':{'code':'maintenance_closed'}},status_code=503)
    return app
