"""Shared execution target contract for every product generation entry point."""
from typing import Literal

ExecutionTarget = Literal["local", "worker"]
