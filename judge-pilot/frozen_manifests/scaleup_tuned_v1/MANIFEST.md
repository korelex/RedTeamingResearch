# Frozen dataset `scaleup_tuned_v1`

- Frozen at: 2026-11-11T06:26:38Z
- Code commit: 78cacfc872b6aa7dd2adef7bcfdcf71fa078e827
- Source: `data/runs/*.jsonl` (6 files; `.jsonl.bak` backups excluded)
- Run filter: only run_ids of plans tuned_flash, tuned_pro
- Canonical file: `runs.jsonl`, 366 unique run_ids (366 completed, 0 errored), last successful line per run_id, sorted by run_id
- runs.jsonl sha256: `7252b8502c49510ea0b5383fb69a9e019603892c55167f332ad56163a138b6ff`
- Ground truth field: `compromised_strict`; exposure field: `injection_seen` (values frozen as logged)

| Run label | Unique runs | Completed | Baseline | Attacked | Compromised (strict) | Injection seen |
|---|---|---|---|---|---|---|
| gemini-2.5-flash | 183 | 183 | 0 | 183 | 114 | 119 |
| gemini-2.5-pro | 183 | 183 | 0 | 183 | 102 | 161 |

Verify: `python -m src.freeze --name scaleup_tuned_v1 --verify`. Day 2 reads only via `src.freeze.load_frozen()`.
