"""On-demand smoke projection from Backend queue and durable Gallery records.

No submission, Comfy history, network access or background worker belongs here.
The training final and its registration remain independent of this projection.
"""
from pathlib import Path, PureWindowsPath
from urllib.parse import quote

from PIL import Image, UnidentifiedImageError

from app.core import queue
from app.db import database
from app.db.models import GeneratedArtifact, GeneratedImage


DIAGNOSTICS = {
    'smoke_generation_failed': ('Generation failed; training final is preserved.', 'Inspect the generation job before any separately authorized new attempt.'),
    'smoke_generation_cancelled': ('Generation was cancelled; training final is preserved.', 'Keep this generation job identity; status refresh never resubmits.'),
    'smoke_job_missing': ('No current queue state or recoverable image for this job.', 'Reconcile the recorded generation job; refresh after its Gallery records are restored.'),
    'smoke_job_unknown': ('Generation state is not recognized.', 'Reconcile the recorded generation job; do not infer success or resubmit.'),
    'smoke_artifact_unavailable': ('No retrievable image belongs to this generation job.', 'Restore a valid Gallery image and its job record, then refresh status.'),
    'smoke_submission_unknown': ('Submission outcome is uncertain.', 'Reconcile Backend submission evidence before any new attempt; automatic retry is disabled.'),
    'generation_queue_full': ('Generation queue was full; no smoke job was accepted.', 'A new explicit smoke request may retry after queue capacity is available.'),
}


def diagnostic(value):
    if not value:
        return None, None, None
    code = value if value in DIAGNOSTICS else 'smoke_submission_unknown'
    message, hint = DIAGNOSTICS[code]
    return code, message, hint


def _image_file(root: Path, locator: str) -> bool:
    # Only relative Gallery locators can be returned to public clients. Reject
    # links even when they resolve inside the root; StaticFiles also denies escapes.
    if not isinstance(locator, str) or not locator or any(c in locator for c in '\\:%?#\r\n\x00'):
        return False
    path = Path(locator)
    if path.is_absolute() or PureWindowsPath(locator).drive or any(p in {'', '.', '..'} for p in locator.split('/')):
        return False
    try:
        candidate = root
        for part in path.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                return False
        candidate.resolve().relative_to(root)
        if not candidate.is_file() or candidate.stat().st_size == 0:
            return False
        with Image.open(candidate) as image:
            image.verify()
        # verify() checks structure/checksums but does not decode pixels. It
        # consumes the image, so reopen before validating the compressed data.
        with Image.open(candidate) as image:
            image.load()
        return True
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError):
        return False


def reference(job_id, gallery_dir):
    """Lowest valid artifact id, then legacy image id; keep exact job provenance."""
    if not gallery_dir:
        return None, False
    root = Path(gallery_dir).resolve()
    with database.SessionLocal() as db:
        artifacts = db.query(GeneratedArtifact).filter_by(job_id=job_id).order_by(GeneratedArtifact.id).all()
        images = db.query(GeneratedImage).filter_by(job_id=job_id).order_by(GeneratedImage.id).all()
        candidates = [(a.gallery_path, a.id, next((i.id for i in images if i.image_path == a.gallery_path), None))
                      for a in artifacts if a.artifact_type == 'image']
        artifact_paths = {a.gallery_path for a in artifacts}
        candidates += [(i.image_path, None, i.id) for i in images if i.image_path not in artifact_paths]
        for locator, artifact_id, image_id in candidates:
            # A reused/overwritten locator claimed by another job is ambiguous.
            conflict = db.query(GeneratedArtifact.id).filter(GeneratedArtifact.gallery_path == locator,
                (GeneratedArtifact.job_id != job_id) | GeneratedArtifact.job_id.is_(None)).first()
            conflict = conflict or db.query(GeneratedImage.id).filter(GeneratedImage.image_path == locator,
                (GeneratedImage.job_id != job_id) | GeneratedImage.job_id.is_(None)).first()
            if not conflict and _image_file(root, locator):
                return {'smoke_test_artifact':locator, 'smoke_test_artifact_id':artifact_id,
                        'smoke_test_image_id':image_id, 'smoke_test_artifact_url':'/gallery/'+quote(locator, safe='/')}, True
        return None, bool(artifacts or images)


def observe(job, gallery_dir):
    """Return only smoke fields. Unknown/missing evidence is recoverable, not success."""
    previous = job['smoke_test_status']
    if previous in {'failed', 'cancelled'}:
        return {'smoke_test_status':previous, 'smoke_test_artifact':None,
                'smoke_test_error':'smoke_generation_'+previous}
    state = queue.get_job_status(job['smoke_test_job_id'])
    if state and state.get('job_id') != job['smoke_test_job_id']:
        state = {'status':'unknown'}
    current = state.get('status') if state else None
    if current in {'failed', 'cancelled'}:
        return {'smoke_test_status':current, 'smoke_test_artifact':None,
                'smoke_test_error':'smoke_generation_'+current}
    if current in {'queued', 'running'} and previous != 'completed':
        # Queue snapshots must not regress a previously observed running job.
        if previous == 'running' and current == 'queued':
            current = 'running'
        return {'smoke_test_status':current,'smoke_test_artifact':None,'smoke_test_error':None}
    if current not in {None, 'completed', 'queued', 'running'}:
        return {'smoke_test_status':'unknown','smoke_test_artifact':None,'smoke_test_error':'smoke_job_unknown'}
    found, has_records = reference(job['smoke_test_job_id'], gallery_dir)
    if found:
        return {'smoke_test_status':'completed','smoke_test_artifact':found['smoke_test_artifact'],'smoke_test_error':None}
    unavailable = has_records or current == 'completed' or previous in {'completed','artifact_unavailable'}
    return {'smoke_test_status':'artifact_unavailable' if unavailable else 'unknown',
            'smoke_test_artifact':None,
            'smoke_test_error':'smoke_artifact_unavailable' if unavailable else 'smoke_job_missing'}


def decorate(job, gallery_dir):
    result = dict(job)
    if not result.get('smoke_test_job_id') and result.get('smoke_test_status') in {'submitting','submitted','submission_unknown'}:
        result['smoke_test_error'] = 'smoke_submission_unknown'
    result.update(smoke_test_artifact_id=None, smoke_test_image_id=None, smoke_test_artifact_url=None)
    if result.get('smoke_test_status') == 'completed' and result.get('smoke_test_job_id'):
        found, _ = reference(result['smoke_test_job_id'], gallery_dir)
        if found and found['smoke_test_artifact'] == result.get('smoke_test_artifact'):
            result.update(found)
        else:
            result.update(smoke_test_status='artifact_unavailable', smoke_test_artifact=None,
                          smoke_test_error='smoke_artifact_unavailable')
    code, message, hint = diagnostic(result.get('smoke_test_error'))
    result.update(smoke_test_error_code=code, smoke_test_error=message, smoke_test_hint=hint)
    return result
