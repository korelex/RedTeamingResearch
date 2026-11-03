# Frozen dataset `scaleup_smoke`

- Frozen at: 2026-11-03T17:55:36Z
- Code commit: f26fee24c982d143336d3b5bac7f768570431c1b (working tree has uncommitted changes)
- Source: `data/runs/*.jsonl` (4 files; `.jsonl.bak` backups excluded)
- Run filter: only run_ids of plans smoke_scaleup_flash, smoke_scaleup_pro
- Canonical file: `runs.jsonl`, 24 unique run_ids (24 completed, 0 errored), last successful line per run_id, sorted by run_id
- runs.jsonl sha256: `bada4c63a31ce351b6df2f698439dea14d88dd525b17e24995d250863e92df7c`
- Ground truth field: `compromised_strict`; exposure field: `injection_seen` (values frozen as logged)

| Run label | Unique runs | Completed | Baseline | Attacked | Compromised (strict) | Injection seen |
|---|---|---|---|---|---|---|
| gemini-2.5-flash | 12 | 12 | 2 | 10 | 6 | 7 |
| gemini-2.5-pro | 12 | 12 | 2 | 10 | 4 | 7 |

Verify: `python -m src.freeze --name scaleup_smoke --verify`. Day 2 reads only via `src.freeze.load_frozen()`.
