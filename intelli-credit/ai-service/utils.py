"""
Shared utilities for the AI service.
"""

import re

_JOB_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_job_id(job_id: str) -> str:
    """
    Validate that a job_id contains only safe characters (alphanumeric, hyphens, underscores).
    Prevents path traversal attacks when job_id is used in filesystem paths.

    Raises ValueError if the job_id is invalid.
    Returns the job_id unchanged if valid.
    """
    if not job_id or not _JOB_ID_PATTERN.match(job_id):
        raise ValueError(f"Invalid job_id format: must contain only alphanumeric characters, hyphens, and underscores")
    return job_id
