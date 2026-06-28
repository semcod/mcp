"""Tenant loading, auth, audit log, and repo usage tracking."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import Header, HTTPException

from gateway_config import AUDIT_LOG, REDIS_URL, REPO_USAGE_TTL_SECONDS, TENANTS_DIR

try:
    from redis import Redis

    RQ_AVAILABLE = True
except Exception:
    Redis = None
    RQ_AVAILABLE = False


def load_tenants() -> dict[str, dict]:
    tenants: dict[str, dict] = {}
    if not TENANTS_DIR.exists():
        return tenants
    for path in TENANTS_DIR.glob("*.yaml"):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        tenant_id = data.get("tenant_id") or path.stem
        tenants[tenant_id] = data
    return tenants


TENANTS = load_tenants()


def get_redis_client() -> Redis | None:
    if not RQ_AVAILABLE or not REDIS_URL:
        return None
    try:
        return Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        return None


def track_repo_usage(tenant_id: str, repo_id: str, platform: str = "github") -> None:
    redis = get_redis_client()
    if not redis:
        return
    try:
        key = f"mcp:repo_usage:{tenant_id}"
        timestamp = int(time.time())
        redis.hset(key, repo_id, json.dumps({"timestamp": timestamp, "platform": platform, "count": 1}))
        redis.hincrby(f"mcp:repo_count:{tenant_id}", repo_id, 1)
        redis.expire(key, REPO_USAGE_TTL_SECONDS)
        redis.expire(f"mcp:repo_count:{tenant_id}", REPO_USAGE_TTL_SECONDS)
    except Exception:
        pass


def get_last_used_repo(tenant_id: str) -> str | None:
    redis = get_redis_client()
    if not redis:
        return None
    try:
        key = f"mcp:repo_usage:{tenant_id}"
        if not redis.exists(key):
            return None
        repos = redis.hgetall(key)
        if not repos:
            return None
        latest_repo = None
        latest_timestamp = 0
        for repo_id, data_str in repos.items():
            try:
                data = json.loads(data_str)
                timestamp = data.get("timestamp", 0)
                if timestamp > latest_timestamp:
                    latest_timestamp = timestamp
                    latest_repo = repo_id
            except Exception:
                continue
        return latest_repo
    except Exception:
        return None


def get_most_used_repo(tenant_id: str) -> str | None:
    redis = get_redis_client()
    if not redis:
        return None
    try:
        key = f"mcp:repo_count:{tenant_id}"
        if not redis.exists(key):
            return None
        counts = redis.hgetall(key)
        if not counts:
            return None
        most_used_repo = None
        max_count = 0
        for repo_id, count_str in counts.items():
            try:
                count = int(count_str)
                if count > max_count:
                    max_count = count
                    most_used_repo = repo_id
            except Exception:
                continue
        return most_used_repo
    except Exception:
        return None


def get_preferred_repo(tenant_id: str) -> str | None:
    return get_last_used_repo(tenant_id) or get_most_used_repo(tenant_id)


def find_tenant_by_key(api_key: str) -> dict | None:
    for tenant in TENANTS.values():
        if api_key in tenant.get("api_keys", []):
            return tenant
    return None


def authenticate(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    api_key = authorization.split(" ", 1)[1].strip()
    tenant = find_tenant_by_key(api_key)
    if not tenant:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return tenant


def audit(event: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {**event, "ts": time.time()}
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
