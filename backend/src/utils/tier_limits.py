"""
Tier-based feature limits for job posts and candidate pools.
"""
from __future__ import annotations

TIER_ORDER = {"guest": -1, "free": 0, "supporter": 1, "pro": 2, "enterprise": 3}

# None = unlimited
JOB_POST_LIMITS: dict[str, int | None] = {
    "free": 0,
    "supporter": 3,
    "pro": 20,
    "enterprise": None,
}

CANDIDATE_LIMITS: dict[str, int | None] = {
    "free": 0,
    "supporter": 20,
    "pro": 200,
    "enterprise": None,
}


def get_job_post_limit(tier: str) -> int | None:
    return JOB_POST_LIMITS.get(tier, 0)


def get_candidate_limit(tier: str) -> int | None:
    return CANDIDATE_LIMITS.get(tier, 0)


def is_at_limit(current_count: int, tier: str, *, resource: str = "candidate") -> bool:
    limits = JOB_POST_LIMITS if resource == "job_post" else CANDIDATE_LIMITS
    limit = limits.get(tier, 0)
    if limit is None:
        return False
    return current_count >= limit
