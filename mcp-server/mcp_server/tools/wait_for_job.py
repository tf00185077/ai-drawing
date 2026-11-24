"""Bounded read of existing generation/training jobs and their result metadata."""
from __future__ import annotations

import json
import time
from typing import Annotated, Any
from urllib.parse import quote

import anyio
import httpx
from pydantic import Field

from mcp_server.client import get_backend_client
from mcp_server.config import get_mcp_settings
from mcp_server.media_locators import gallery_locators, LocatorUnavailable
from mcp_server.tools.lora_train import _backend_error, _strict_backend_result, _STATUS_SUCCESS_FIELDS
from mcp_server.tools.responses import backend_error_payload, envelope


# Actual calling-client tool-call limit is unverified. This is the approved
# fallback policy for the whole read, not a measured client limit.
MAX_WAIT_SECONDS = 50.0
POLL_SECONDS = 0.5


def _error(code: str, message: str, hint: str, state: dict) -> dict:
    return {'ok': False, 'error': {'code': code, 'message': message, 'hint': hint, 'details': state}}


def _generation_state(payload: dict, job_id: str) -> dict:
    state = {k: v for k, v in payload.items() if k not in {'ok', 'job_id', 'artifacts', 'image_id', 'image_path'}}
    state.update(job_id=job_id, job_domain='generation', artifacts=[], images=[])
    for row in payload.get('artifacts') or []:
        state['artifacts'].append({**row, 'artifact_id': row['id'], 'kind': row.get('artifact_type'),
                                   'local_path': None, 'artifact_url': None})
    if payload.get('image_id') is not None:
        state['images'].append({'image_id': payload['image_id'], 'artifact_id': None, 'kind': 'image',
                                'image_path': payload.get('image_path'), 'local_path': None, 'image_url': None})
    return state


def _terminal_failure(state: dict) -> dict:
    if state['status'] == 'cancelled':
        reason = state.get('error_message') if state['job_domain'] == 'training' else state.get('error')
        return _error('job_cancelled', str(reason or 'Backend job was cancelled.'),
                      'Inspect the same job before deciding on any new request.', state)
    if state['job_domain'] == 'training':
        return _error(state.get('error_code') or 'training_failed',
                      state.get('error_message') or 'Backend reported a training failure.',
                      (state.get('error_details') or {}).get('hint') or 'Inspect the safe training failure code and same job state.', state)
    error = state.get('error')
    return _error((error.get('code') if isinstance(error, dict) else None) or state.get('failure_code') or 'generation_failed',
                  str((error.get('message') if isinstance(error, dict) else error) or 'Backend generation failed.'),
                  (error.get('hint') if isinstance(error, dict) else None) or 'Inspect this job and its node/recording diagnostics before deciding on a corrected request.', state)


async def wait_for_job(
    job_id: Annotated[str, Field(min_length=1)],
    timeout_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 50.0,
) -> dict[str, Any]:
    """Wait for generation or LoRA training and return existing result locators.

    One overall timeout (default/max 50 seconds; client limit unverified) covers
    domain lookup, status/body reads, Gallery enrichment and polling. Timeout
    preserves the last-known Backend status; call again with the same job ID.
    No job is submitted or cancelled. Host locators require filesystem access;
    returned metadata does not verify file existence or retrieved bytes.
    """
    budget = min(timeout_seconds, MAX_WAIT_SECONDS)
    deadline = time.monotonic() + budget
    state = {'job_id': job_id, 'job_domain': 'unknown', 'status': 'unknown', 'artifacts': [], 'images': []}
    client = get_backend_client()
    settings = get_mcp_settings()
    encoded_id = quote(job_id, safe='')
    domain = None
    read_domain = 'generation'

    def check_deadline():
        if time.monotonic() >= deadline:
            raise TimeoutError

    def prepare(result):
        # Include normalization/serialization preparation in the budget, even
        # when CPU work finishes without an await/cancellation checkpoint.
        result = envelope(result)
        json.dumps(result, ensure_ascii=False)
        check_deadline()
        return result

    async def enrich():
        unavailable = []
        for namespace, key, route, path_key, url_key in (
            ('artifacts', 'artifact_id', 'gallery/artifacts', 'gallery_path', 'artifact_url'),
            ('images', 'image_id', 'gallery', 'image_path', 'image_url'),
        ):
            for result in state[namespace]:
                check_deadline()
                identity = result[key]
                try:
                    detail = await client.get_async(f'{route}/{identity}')
                    check_deadline()
                    if detail.get('id') != identity:
                        raise LocatorUnavailable('Gallery metadata identity mismatch')
                    path = detail.get(path_key) or result.get(path_key)
                    local, url = gallery_locators(path=path, url=detail.get(url_key), local_path=detail.get('local_path'),
                                                  gallery_dir=settings.gallery_dir, backend_url=settings.backend_api_url)
                    result.update(local_path=local, **{url_key: url})
                except LocatorUnavailable as exc:
                    result['local_path'] = exc.local_path
                    unavailable.append({key: identity, 'reason': str(exc)})
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 404:
                        raise
                    unavailable.append({key: identity, 'reason': 'Gallery metadata not found'})
        if not state['artifacts'] and not state['images']:
            unavailable.append({'reason': 'completed generation has no recorded media identity'})
        if unavailable:
            return _error('artifact_locator_unavailable', 'Generation completed; required media locators are unavailable.',
                          f'Inspect the same job {job_id} and existing Gallery metadata/MCP_GALLERY_DIR configuration before another read. Do not resubmit or migrate results automatically.',
                          {**state, 'unavailable_locators': unavailable})
        return {'ok': True, 'data': state}

    try:
        with anyio.fail_after(max(0, deadline - time.monotonic())):
            while True:
                check_deadline()
                if domain is None:
                    try:
                        payload = await client.get_async(f'generate/job/{encoded_id}')
                        domain = 'generation'
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code != 404:
                            raise
                        check_deadline()
                        read_domain = 'training'
                        try:
                            payload = await client.get_async(f'lora-train/jobs/{encoded_id}')
                            domain = 'training'
                        except httpx.HTTPStatusError as fallback:
                            if fallback.response.status_code != 404:
                                raise
                            return prepare(_error('job_not_found', 'Neither Backend job domain contains this ID.',
                                                  f'Check the existing job ID {job_id} before submitting another request.', state))
                else:
                    route = 'generate/job' if domain == 'generation' else 'lora-train/jobs'
                    payload = await client.get_async(f'{route}/{encoded_id}')
                if domain == 'training':
                    public = _strict_backend_result('wait_for_job', payload, _STATUS_SUCCESS_FIELDS)
                    if public.get('ok') is False:
                        public['error']['details'].update(state, job_domain='training')
                        return prepare(public)
                    state = {k: v for k, v in public.items() if k not in {'ok', 'tool'}}
                    state.update(job_id=job_id, job_domain='training', artifacts=[], images=[])
                else:
                    state = _generation_state(payload, job_id)
                state.setdefault('status', 'unknown')
                check_deadline()
                if state['status'] in {'failed', 'cancelled'}:
                    return prepare(_terminal_failure(state))
                if state['status'] == 'completed':
                    return prepare(await enrich() if domain == 'generation' else {'ok': True, 'data': state})
                await anyio.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
    except TimeoutError:
        return _error('timeout', 'Wait budget exhausted; Backend job status is unchanged.',
                      f'Call wait_for_job again with the same job_id {job_id}. Do not cancel or resubmit because of this timeout.',
                      {**state, 'timeout_seconds': budget})
    except Exception as exc:
        failure = (_backend_error('wait_for_job', exc) if read_domain == 'training'
                   else backend_error_payload('wait_for_job', exc))
        failure['error']['details'].update(state)
        try:
            return prepare(failure)
        except TimeoutError:
            return _error('timeout', 'Wait budget exhausted; Backend job status is unchanged.',
                          f'Call wait_for_job again with the same job_id {job_id}. Do not cancel or resubmit because of this timeout.',
                          {**state, 'timeout_seconds': budget})
