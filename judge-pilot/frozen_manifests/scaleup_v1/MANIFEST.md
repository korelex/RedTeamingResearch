# Frozen dataset `scaleup_v1`

- Frozen at: 2026-11-03T19:45:16Z
- Code commit: cf5b12c74bc423d7d0be00d2afd5e8898a1701d0
- Source: `data/runs/*.jsonl` (4 files; `.jsonl.bak` backups excluded)
- Run filter: only run_ids of plans scaleup_flash, scaleup_pro
- Canonical file: `runs.jsonl`, 1300 unique run_ids (1300 completed, 0 errored), last successful line per run_id, sorted by run_id
- runs.jsonl sha256: `385cb31c2d61513ce96007183562184481a600cd68fa1ad597ef735361953a5c`
- Ground truth field: `compromised_strict`; exposure field: `injection_seen` (values frozen as logged)

| Run label | Unique runs | Completed | Baseline | Attacked | Compromised (strict) | Injection seen |
|---|---|---|---|---|---|---|
| gemini-2.5-flash | 650 | 650 | 20 | 630 | 281 | 534 |
| gemini-2.5-pro | 650 | 650 | 20 | 630 | 112 | 481 |

Verify: `python -m src.freeze --name scaleup_v1 --verify`. Day 2 reads only via `src.freeze.load_frozen()`.
