"""Explicit additive metadata backfill. Never called from startup or HTTP reads.

This function operates only on the caller's database/transaction. It never merges
rows, modifies identity/notes/files, hashes models or calls a provider.
"""
from collections import Counter
from sqlalchemy.orm import Session
from app.db.models import DownloadedResource
from app.schemas.resources import ResourceMetadata
from app.services.resource_records import diagnostic, legacy_metadata, project_resource


def backfill_metadata(db: Session) -> dict[int,list[dict[str,str]]]:
    rows=db.query(DownloadedResource).order_by(DownloadedResource.id).all()
    counts=Counter((r.provider,r.civitai_file_id) for r in rows if r.civitai_file_id is not None)
    report={}
    for row in rows:
        if row.metadata_json is None:
            snap=legacy_metadata(row) or ResourceMetadata(origin='legacy_notes',diagnostics=[diagnostic('missing_metadata','metadata')])
            if row.civitai_file_id is not None and counts[(row.provider,row.civitai_file_id)]>1:
                snap.diagnostics.append(diagnostic('duplicate_legacy_candidate','civitai_file_id'))
            row.metadata_json=snap.model_dump_json()
        report[row.id]=[d.model_dump() for d in project_resource(row).diagnostics]
    db.commit()
    return report
