#!/usr/bin/env python3
"""Stable cron entrypoint: preserves dispatch exit code and stdout."""
from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent.parent
r=subprocess.run([sys.executable,str(root/'pipeline'/'dispatch.py')],cwd=root)
raise SystemExit(r.returncode)
