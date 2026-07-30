"""Dependency-light input normalization shared by Discord entrypoints."""
import re

JOB_ID_PATTERN = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F])"
)


def normalize_job_id(value: str) -> str | None:
    """Extract one UUID from plain IDs or copied Discord command text."""
    matches = JOB_ID_PATTERN.findall(value)
    if len(matches) != 1:
        return None
    return matches[0].lower()
