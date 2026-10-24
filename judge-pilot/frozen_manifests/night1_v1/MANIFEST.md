# Frozen dataset `night1_v1`

- Frozen at: 2026-10-24T04:10:48Z
- Code commit: 3de535aa900a5ba51b69c49b097e86a03141c1f7 (working tree has uncommitted changes)
- Source: `data/runs/*.jsonl` (2 files; `.jsonl.bak` backups excluded)
- Canonical file: `runs.jsonl`, 592 unique run_ids (591 completed, 1 errored), last successful line per run_id, sorted by run_id
- runs.jsonl sha256: `bf82877361d447b385c6f64ae8eb0c323fe00143bfa9d73c8d0dd738c431fb9c`
- Ground truth field: `compromised_strict`; exposure field: `injection_seen` (values frozen as logged)

| Run label | Unique runs | Completed | Baseline | Attacked | Compromised (strict) | Injection seen |
|---|---|---|---|---|---|---|
| gemini-2.5-flash | 145 | 145 | 20 | 125 | 87 | 89 |
| gemini-2.5-pro | 145 | 145 | 20 | 125 | 65 | 104 |
| gemini-3.1-pro-preview | 145 | 145 | 20 | 125 | 0 | 121 |
| gemini-3.1-pro-preview@t1 | 6 | 6 | 1 | 5 | 0 | 5 |
| gemini-3.8-flash | 145 | 145 | 20 | 125 | 0 | 125 |
| gemini-3.8-flash@t1 | 6 | 5 | 1 | 4 | 0 | 4 |

Verify: `python -m src.freeze --name night1_v1 --verify`. Day 2 reads only via `src.freeze.load_frozen()`.
