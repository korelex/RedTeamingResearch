"""Freeze the Day 1 run dataset, and load it back with hash verification.

Usage (from the project root):
    python -m src.freeze --name night1_v1            # create data/frozen/night1_v1/ (refuses to overwrite)
    python -m src.freeze --name night1_v1 --verify   # re-check every SHA-256

Layout of data/frozen/<name>/ (all files read-only):
  raw/<date>.jsonl   byte-exact copies of data/runs/*.jsonl (append-only logs, incl. errored attempts)
  runs.jsonl         canonical dataset: one record per run_id (dedupe_runs rule), sorted by run_id
  config.yaml        the config the runs were produced with
  SHA256SUMS         sha256 of every file above
  MANIFEST.md        provenance: git commit, counts per model, field list
A copy of SHA256SUMS and MANIFEST.md goes to frozen_manifests/<name>/ (tracked in git; data/ is not).
Day 2 code must read runs only through load_frozen(), which fails on any hash mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.inspect_run import dedupe_runs, load_records, run_label

FROZEN_ROOT = Path("data/frozen")
MANIFEST_ROOT = Path("frozen_manifests")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
        return out + (" (working tree has uncommitted changes)" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def verify(dest: Path) -> list[str]:
    """Return a list of problems; empty means every file matches SHA256SUMS."""
    sums = dest / "SHA256SUMS"
    if not sums.exists():
        return [f"{sums} missing"]
    problems = []
    for line in sums.read_text().splitlines():
        digest, rel = line.split("  ", 1)
        p = dest / rel
        if not p.exists():
            problems.append(f"missing: {rel}")
        elif sha256(p) != digest:
            problems.append(f"hash mismatch: {rel}")
    return problems


def load_frozen(name: str = "night1_v1", root: Path = FROZEN_ROOT) -> list[dict]:
    """The only supported way for Day 2 code to read Day 1 runs."""
    dest = root / name
    problems = verify(dest)
    if problems:
        raise RuntimeError(f"frozen dataset {dest} failed verification: {problems}")
    with open(dest / "runs.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def freeze(name: str, runs_dir: Path, config: Path, attacks: list[str] | None = None,
           keep_ids: set[str] | None = None, plans: list[str] | None = None) -> Path:
    """attacks / keep_ids: keep only these runs in runs.jsonl (raw/ still holds every log line)."""
    dest = FROZEN_ROOT / name
    if dest.exists():
        raise SystemExit(f"{dest} already exists; a frozen dataset is never overwritten. Use a new --name.")
    (dest / "raw").mkdir(parents=True)
    raw_files = sorted(runs_dir.glob("*.jsonl"))  # *.jsonl.bak (pre-backfill backups) are deliberately excluded
    for p in raw_files:
        shutil.copy2(p, dest / "raw" / p.name)
    shutil.copy2(config, dest / "config.yaml")

    runs = sorted(dedupe_runs(load_records(str(runs_dir))), key=lambda r: str(r["run_id"]))
    if attacks:
        runs = [r for r in runs if r.get("attack") in attacks]
    if keep_ids is not None:
        runs = [r for r in runs if r["run_id"] in keep_ids]
    with open(dest / "runs.jsonl", "w", encoding="utf-8") as f:
        for r in runs:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

    files = [dest / "raw" / p.name for p in raw_files] + [dest / "runs.jsonl", dest / "config.yaml"]
    sums = "".join(f"{sha256(p)}  {p.relative_to(dest)}\n" for p in files)
    (dest / "SHA256SUMS").write_text(sums)

    done = [r for r in runs if r.get("error") is None]
    rows = []
    for label, n in sorted(Counter(run_label(r) for r in runs).items()):
        rl = [r for r in done if run_label(r) == label]
        att = [r for r in rl if not r.get("is_baseline")]
        rows.append(f"| {label} | {n} | {len(rl)} | {sum(bool(r.get('is_baseline')) for r in rl)} | {len(att)} | "
                    f"{sum(bool(r.get('compromised_strict')) for r in att)} | {sum(bool(r.get('injection_seen')) for r in att)} |")
    manifest = "\n".join([
        f"# Frozen dataset `{name}`",
        "",
        f"- Frozen at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Code commit: {_git_commit()}",
        f"- Source: `{runs_dir}/*.jsonl` ({len(raw_files)} files; `.jsonl.bak` backups excluded)",
        *([f"- Attack filter: {', '.join(attacks)} (raw/ keeps every log line)"] if attacks else []),
        *([f"- Run filter: only run_ids of plans {', '.join(plans)}"] if plans else []),
        f"- Canonical file: `runs.jsonl`, {len(runs)} unique run_ids ({len(done)} completed, "
        f"{len(runs) - len(done)} errored), last successful line per run_id, sorted by run_id",
        f"- runs.jsonl sha256: `{sha256(dest / 'runs.jsonl')}`",
        "- Ground truth field: `compromised_strict`; exposure field: `injection_seen` (values frozen as logged)",
        "",
        "| Run label | Unique runs | Completed | Baseline | Attacked | Compromised (strict) | Injection seen |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        "Verify: `python -m src.freeze --name " + name + " --verify`. Day 2 reads only via `src.freeze.load_frozen()`.",
        "",
    ])
    (dest / "MANIFEST.md").write_text(manifest)

    for p in dest.rglob("*"):
        if p.is_file():
            p.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    mdest = MANIFEST_ROOT / name
    mdest.mkdir(parents=True, exist_ok=True)
    for fn in ("SHA256SUMS", "MANIFEST.md"):
        shutil.copy2(dest / fn, mdest / fn)
        (mdest / fn).chmod(0o644)
    return dest


def plan_run_ids(config: Path, plans: list[str]) -> set[str]:
    """run_ids a config plan generates (same rule as src.runner)."""
    from src.runner import expand_plan, load_cfg  # heavy import, only needed here
    cfg = load_cfg(str(config))
    ids = set()
    for name in plans:
        plan = cfg["plans"][name]
        model_id = cfg["vertex"][plan.get("model", "flash_model")]
        ids |= {s.run_id(model_id) for s in expand_plan(cfg, name)}
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Freeze or verify a Day 1 run dataset.")
    ap.add_argument("--name", default="night1_v1")
    ap.add_argument("--runs-dir", default="data/runs")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--attacks", nargs="+", help="keep only runs with these attack names (e.g. the Day 3 variants)")
    ap.add_argument("--plans", nargs="+", help="keep only run_ids generated by these config plans (drops smoke-only runs)")
    args = ap.parse_args(argv)
    if args.verify:
        problems = verify(FROZEN_ROOT / args.name)
        print("OK: all hashes match" if not problems else "\n".join(problems))
        return 1 if problems else 0
    keep = plan_run_ids(Path(args.config), args.plans) if args.plans else None
    dest = freeze(args.name, Path(args.runs_dir), Path(args.config), args.attacks, keep, args.plans)
    print((dest / "MANIFEST.md").read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
