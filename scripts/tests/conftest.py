from pathlib import Path
import sys

import pytest


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_ROOT))


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
