"""Readable, durable LoRA allocations and confined per-run delivery primitives.

No trainer, network, model loader or service is invoked by this module.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import struct
import unicodedata
from pathlib import Path, PureWindowsPath

from sqlalchemy import func, text
from app.db.models import LoraOutputReservation


class DeliveryError(ValueError):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        self.details = {}
        super().__init__(message)


def validate_output_name(value: str) -> str:
    if not isinstance(value, str):
        raise DeliveryError('invalid_output_name', 'output_name must be text')
    name = unicodedata.normalize('NFC', value)
    if (not 1 <= len(name) <= 64
        or name in {'.', '..'} or name.endswith('.') or name[-1:].isspace()
        or any(unicodedata.category(c).startswith('C') or c in '<>:"/\\|?*' for c in name)
        or len(name.encode('utf-8')) > 192
        or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', name, re.I)):
        raise DeliveryError('invalid_output_name', 'use 1–64 NFC characters, at most 192 UTF-8 bytes, without extensions, device names or forbidden path characters')
    if name.casefold().endswith(('.safetensors', '.ckpt', '.pth')):
        raise DeliveryError('invalid_output_name', 'output_name must not include a model extension')
    return name


def name_key(name: str) -> str:
    return unicodedata.normalize('NFC', name).casefold()


def output_config_hash(requested: str, recipe_hash: str) -> str:
    return hashlib.sha256(json.dumps([validate_output_name(requested), recipe_hash], ensure_ascii=False).encode()).hexdigest()


def reserve_name(db, *, job_id: str, requested: str, occupied: set[str], created_utc: str) -> dict:
    """Reserve in the SAME SQLite write transaction as the new durable job.

    BEGIN IMMEDIATE serializes cross-process writers; unique constraints also
    enforce resolved-name and per-request serial uniqueness. Nothing is recycled.
    """
    requested = validate_output_name(requested)
    db.execute(text('BEGIN IMMEDIATE'))
    existing = db.get(LoraOutputReservation, job_id)
    if existing:
        if existing.requested_name != requested:
            raise DeliveryError('output_allocation_conflict', 'job already owns a different requested name')
        return allocation(existing)
    key = name_key(requested)
    serial = (db.query(func.max(LoraOutputReservation.serial)).filter_by(request_key=key).scalar() or 0) + 1
    while True:
        resolved = validate_output_name(requested if serial == 1 else f'{requested}_{serial:03d}')
        if name_key(resolved) not in occupied and not db.query(LoraOutputReservation).filter_by(resolved_key=name_key(resolved)).first():
            break
        serial += 1
    stamp = re.sub(r'[-:]', '', created_utc.split('.')[0]).replace('+0000', 'Z')
    if not stamp.endswith('Z'): stamp += 'Z'
    row = LoraOutputReservation(job_id=job_id, requested_name=requested, request_key=key,
                                resolved_name=resolved, resolved_key=name_key(resolved),
                                serial=serial, run_locator=f'{resolved}__{stamp}')
    db.add(row)
    db.flush()
    return allocation(row)


def allocation(row) -> dict:
    return dict(job_id=row.job_id, output_name=row.requested_name,
                resolved_output_name=row.resolved_name, output_serial=row.serial,
                run_locator=row.run_locator)


def confined(path: Path, root: Path) -> Path:
    """Reject symlinks/reparse points at every existing component, including root."""
    root, path = root.absolute(), path.absolute()
    try: path.relative_to(root)
    except ValueError: raise DeliveryError('unsafe_run_path', 'path is outside the declared run')
    for p in [path, *path.parents]:
        try: info = p.lstat()
        except FileNotFoundError: continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise DeliveryError('unsafe_run_path', 'symlink/reparse paths are not supported')
    if not path.resolve().is_relative_to(root.resolve()):
        raise DeliveryError('unsafe_run_path', 'resolved path escaped run root')
    return path


def run_path(train_root: Path, locator: str) -> Path:
    if not locator or Path(locator).name != locator or '/' in locator or '\\' in locator:
        raise DeliveryError('unsafe_run_path', 'invalid run locator')
    root = train_root.absolute() / 'output' / 'runs'
    return confined(root / locator, root)


def check_run_paths(train_root: Path, locator: str, resolved: str, publish_root: Path | None = None) -> Path:
    root = run_path(train_root, locator)
    paths = [root / 'artifacts' / f'{resolved}.safetensors', root / 'training-parameters.json']
    if publish_root: paths.append(publish_root / 'AI-Drawing' / locator / f'{resolved}.safetensors')
    for path in paths:
        if len(str(path).encode('utf-16-le'))//2 > 259 or any(len(part.encode('utf-8')) > 255 for part in path.parts):
            raise DeliveryError('output_path_too_long', 'resolved output path exceeds portable path limits; choose a shorter name or approved root')
        confined(path, train_root if path.is_relative_to(train_root) else publish_root)
    return root


def create_run(root: Path, *, job_id: str) -> None:
    confined(root, root.parent)
    root.mkdir(parents=True, exist_ok=False)
    for part in ('artifacts', 'configs', 'logs', 'state', 'cache'):
        (root / part).mkdir()
    write_json(root / 'manifest.json', {'schema_version':'lora-run/v1', 'job_id':job_id, 'run_locator':root.name, 'status':'queued'})


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: dict) -> None:
    atomic_write(path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode())


def atomic_write(path: Path, content: bytes) -> None:
    confined(path, path.parent)
    # Exclusive staging, then atomic replacement of this job's own metadata.
    stage = path.with_name('.'+path.name+'.writing')
    with stage.open('xb') as f:
        f.write(content); f.flush(); os.fsync(f.fileno())
    try: os.replace(stage, path)
    finally: stage.unlink(missing_ok=True)


def validate_final(path: Path, artifacts: Path) -> str:
    confined(path, artifacts)
    if path.parent != artifacts or path.suffix != '.safetensors' or not path.is_file():
        raise DeliveryError('output_missing', 'the declared exact final file is missing')
    # Parse the safetensors container without torch or a model load.
    try:
        size = path.stat().st_size
        with path.open('rb') as f:
            n = struct.unpack('<Q', f.read(8))[0]
            if n < 2 or n > min(size-8, 16*1024*1024): raise ValueError('header length')
            def unique(pairs):
                result={}
                for k,v in pairs:
                    if k in result: raise ValueError('duplicate tensor')
                    result[k]=v
                return result
            header=json.loads(f.read(n), object_pairs_hook=unique)
        if not isinstance(header, dict): raise ValueError('header')
        offsets=[]; names=[]
        sizes={'BOOL':1,'U8':1,'I8':1,'F8_E4M3':1,'F8_E5M2':1,'I16':2,'U16':2,'F16':2,'BF16':2,'I32':4,'U32':4,'F32':4,'F64':8,'I64':8,'U64':8}
        for name, tensor in header.items():
            if name == '__metadata__':
                if not isinstance(tensor,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in tensor.items()): raise ValueError('metadata')
                continue
            shape=tensor['shape']; start,end=tensor['data_offsets']; width=sizes[tensor['dtype']]
            if not shape or any(type(x) is not int or x<=0 for x in shape): raise ValueError('shape')
            if type(start) is not int or type(end) is not int or start<0 or end-start != math.prod(shape)*width or end>size-8-n: raise ValueError('tensor bounds')
            offsets.append((start,end));names.append(name)
        cursor=0
        for start,end in sorted(offsets):
            if start != cursor: raise ValueError('non-contiguous tensors')
            cursor=end
        if cursor != size-8-n or not names: raise ValueError('payload length')
        down=[name for name in names if name.endswith(('.lora_down.weight','.lora_A.weight'))]
        if not down: raise ValueError('no LoRA weights')
        for name in down:
            other=name.replace('.lora_down.weight','.lora_up.weight').replace('.lora_A.weight','.lora_B.weight')
            if other not in header or len(header[name]['shape']) < 2 or len(header[other]['shape']) < 2 or header[name]['shape'][0] != header[other]['shape'][1]: raise ValueError('LoRA pair')
    except (OSError, ValueError, KeyError, TypeError, struct.error, OverflowError) as exc:
        raise DeliveryError('invalid_lora_output', 'final file is not a nonempty valid safetensors LoRA container') from exc
    return digest(path)


def publish_final(source: Path, *, artifacts: Path, publish_root: Path, locator: str, identity: dict) -> tuple[str, str]:
    """Verified copy with atomic no-clobber publication and durable retry ownership."""
    import shutil
    content_hash=validate_final(source, artifacts)
    if content_hash != identity['sha256']:
        raise DeliveryError('output_hash_changed', 'validated source content changed')
    target_dir=confined(publish_root/'AI-Drawing'/locator, publish_root)
    target=target_dir/source.name
    marker=target_dir/'registration.json'
    confined(marker,publish_root)
    confined(target, publish_root)
    try:
        target_dir.mkdir(parents=True, exist_ok=False)
        with marker.open('x',encoding='utf-8') as f:
            json.dump(identity,f,ensure_ascii=False,sort_keys=True); f.flush(); os.fsync(f.fileno())
    except FileExistsError:
        try: known=json.loads(marker.read_text(encoding='utf-8'))
        except (OSError,ValueError): raise DeliveryError('lora_registration_conflict','publication folder has unknown ownership')
        if known != identity: raise DeliveryError('lora_registration_conflict','publication belongs to different job or content')
    if target.exists():
        confined(target,publish_root)
        if digest(target) != content_hash: raise DeliveryError('lora_registration_conflict','publication content differs')
        return target.relative_to(publish_root).as_posix(),str(target)
    stage=target_dir/('.'+source.name+'.copying')
    try:
        with source.open('rb') as src, stage.open('xb') as dst:
            shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
        if digest(stage) != content_hash or digest(source) != content_hash:
            raise DeliveryError('lora_copy_hash_mismatch','publication copy differs from validated source')
        try: os.link(stage,target)
        except FileExistsError: raise DeliveryError('lora_registration_conflict','publication appeared during copy')
        if digest(target) != content_hash: raise DeliveryError('lora_copy_hash_mismatch','published file hash mismatch')
    finally:
        # Delete only the staging file created by this call.
        if 'dst' in locals(): stage.unlink(missing_ok=True)
    return target.relative_to(publish_root).as_posix(),str(target)
