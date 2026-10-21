"""Whole-project Vertex usage and estimated cost per model, from Cloud Monitoring (read-only).

Usage (from the project root, after `gcloud auth application-default login`):
    python -m src.project_usage --config config.yaml [--start 2026-10-15] [--end 2026-10-21T08:00:00Z]

Token counts come from aiplatform.googleapis.com/publisher/online_serving/token_count (output includes thinking;
cached input is not separated, so estimates are an upper bound for clients that use context caching).
Calls come from .../model_invocation_count. Prices come only from config.yaml `pricing:`; models without a price
show "n/a". Partner models in Model Garden (StreamRawPredict) report no tokens here; see Billing for those.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

import yaml

MONITORING = "https://monitoring.googleapis.com/v3/projects/{project}/timeSeries"


def _token() -> str:
    out = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"], capture_output=True, text=True
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise SystemExit("No ADC token. Run: gcloud auth application-default login")
    return out.stdout.strip()


def _series(project: str, metric: str, start: str, end: str, group_by: list[str]) -> list[dict]:
    params = [
        ("filter", f'metric.type="{metric}"'),
        ("interval.startTime", start),
        ("interval.endTime", end),
        ("aggregation.alignmentPeriod", "3600s"),
        ("aggregation.perSeriesAligner", "ALIGN_SUM"),
        ("aggregation.crossSeriesReducer", "REDUCE_SUM"),
    ] + [("aggregation.groupByFields", g) for g in group_by]
    url = MONITORING.format(project=project) + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_token()}", "x-goog-user-project": project})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp).get("timeSeries", [])


def collect(project: str, start: str, end: str) -> dict[str, dict]:
    usage: dict[str, dict] = defaultdict(lambda: {"in": 0, "out": 0, "calls": 0, "first": None, "last": None})
    for ts in _series(project, "aiplatform.googleapis.com/publisher/online_serving/token_count", start, end,
                      ["resource.label.model_user_id", "metric.label.type"]):
        model = ts["resource"]["labels"].get("model_user_id", "?")
        kind = ts["metric"].get("labels", {}).get("type", "?")
        for p in ts["points"]:
            v = int(p["value"].get("int64Value", 0))
            if not v:
                continue
            u = usage[model]
            u["in" if kind == "input" else "out"] += v
            t = p["interval"]["endTime"][:13] + ":00Z"
            u["first"] = min(u["first"] or t, t)
            u["last"] = max(u["last"] or t, t)
    for ts in _series(project, "aiplatform.googleapis.com/publisher/online_serving/model_invocation_count", start, end,
                      ["resource.label.model_user_id"]):
        model = ts["resource"]["labels"].get("model_user_id", "?")
        usage[model]["calls"] += sum(int(p["value"].get("int64Value", 0)) for p in ts["points"])
    return usage


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Per-model Vertex usage and estimated cost for the whole project.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--project", default=None, help="default: GOOGLE_CLOUD_PROJECT from .env")
    ap.add_argument("--start", default="2026-10-15T00:00:00Z")
    ap.add_argument("--end", default=None, help="default: now")
    args = ap.parse_args(argv)

    from datetime import datetime, timezone

    from dotenv import load_dotenv

    load_dotenv(".env")
    project = args.project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise SystemExit("Set --project or GOOGLE_CLOUD_PROJECT")
    start = args.start if "T" in args.start else args.start + "T00:00:00Z"
    end = args.end or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    pricing = cfg.get("pricing") or {}
    owners = cfg.get("usage_owners") or {}

    usage = collect(project, start, end)
    rows = []
    for model, u in usage.items():
        price = pricing.get(model)
        cost = None
        if price:
            cost = (u["in"] * price["input_per_mtok"] + u["out"] * price["output_per_mtok"]) / 1e6
        rows.append((model, owners.get(model, owners.get("default", "unknown")), u, price, cost))
    rows.sort(key=lambda r: -(r[4] or 0))

    print(f"Project usage {start} -> {end} (token_count / model_invocation_count; Monitoring, read-only)")
    hdr = f"{'model':<26} {'possible owner':<28} {'calls':>6} {'input tok':>12} {'output tok':>11} {'$/1M in/out':>13} {'est. cost':>10}  hours (UTC)"
    print(hdr)
    print("-" * len(hdr))
    by_owner: dict[str, float] = defaultdict(float)
    unpriced = []
    for model, owner, u, price, cost in rows:
        ptxt = f"{price['input_per_mtok']:.2f}/{price['output_per_mtok']:.2f}" if price else "n/a"
        ctxt = f"${cost:.2f}" if cost is not None else "n/a"
        print(f"{model:<26} {owner:<28} {u['calls']:>6} {u['in']:>12,} {u['out']:>11,} {ptxt:>13} {ctxt:>10}  "
              f"{u['first'] or '-'} .. {u['last'] or '-'}")
        if cost is not None:
            by_owner[owner] += cost
        elif u["in"] or u["out"]:
            unpriced.append(model)
    print("\nEstimated cost by possible owner (priced models only):")
    for owner, c in sorted(by_owner.items(), key=lambda x: -x[1]):
        print(f"  {owner:<30} ${c:.2f}")
    print(f"  {'TOTAL':<30} ${sum(by_owner.values()):.2f}")
    if unpriced:
        print(f"Unpriced models (add to config.yaml pricing: to include): {', '.join(sorted(unpriced))}")
    print("Not covered: Model Garden partner models (StreamRawPredict) and cached-input discounts; see Billing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
