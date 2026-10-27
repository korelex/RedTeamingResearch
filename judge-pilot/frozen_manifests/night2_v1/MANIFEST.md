# Frozen dataset `night2_v1`

- Frozen at: 2026-10-27T15:18:39Z
- Code commit: 3061f7e6eca1c9e5494ff47f662c43f9c09b2630 (working tree has uncommitted changes)
- Source: `data/runs/*.jsonl` (3 files; `.jsonl.bak` backups excluded)
- Attack filter: dual_reviewer_note, dual_cover_story, subtle_account_note (raw/ keeps every log line)
- Run filter: only run_ids of plans night2_flash, night2_pro
- Canonical file: `runs.jsonl`, 732 unique run_ids (732 completed, 0 errored), last successful line per run_id, sorted by run_id
- runs.jsonl sha256: `8b71478d5031c0b58f09828e45e9b59f8050ddf274206999afe0adfb9a3dc553`
- Ground truth field: `compromised_strict`; exposure field: `injection_seen` (values frozen as logged)

| Run label | Unique runs | Completed | Baseline | Attacked | Compromised (strict) | Injection seen |
|---|---|---|---|---|---|---|
| gemini-2.5-flash | 366 | 366 | 0 | 366 | 176 | 253 |
| gemini-2.5-pro | 366 | 366 | 0 | 366 | 140 | 295 |

Verify: `python -m src.freeze --name night2_v1 --verify`. Day 2 reads only via `src.freeze.load_frozen()`.
