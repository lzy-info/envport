"""Versioned, JSON-safe findings shared by doctor and schema validation."""

from datetime import datetime, timezone


def finding(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def report(kind: str, checks: list[dict], **metadata) -> dict:
    counts = {status: sum(c["status"] == status for c in checks)
              for status in ("pass", "fail", "skip")}
    return {
        "schema_version": "envport.report.v1",
        "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if counts["fail"] else "pass",
        "summary": counts,
        **metadata,
        "checks": checks,
    }
