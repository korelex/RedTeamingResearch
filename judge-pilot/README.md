# judge-pilot

Runs AgentDojo tasks against Gemini on Vertex AI.

## Why the adapter exists

The AgentDojo CLI's `--model` only accepts a fixed enum (`agentdojo/models.py`, `ModelsEnum`),
and `gemini-2.5-flash` is not in it. `src/vertex_setup.py` builds the pipeline directly instead:

- `GoogleLLM(model_id, genai.Client(vertexai=True, project=..., location=...))`
- `AgentPipeline.from_config(PipelineConfig(llm=<that object>, defense=None, ...))`, named `<model_id>-vertex`
- adds `model_id -> "AI model developed by Google"` to `agentdojo.models.MODEL_NAMES` at runtime, because attacks need it.
  The installed package is not modified.

`build_pipeline(model_id=None)` uses `vertex.flash_model` from `config.yaml` when no model ID is passed.

## Vertex environment (`.env`)

```
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT=<project>
GOOGLE_CLOUD_LOCATION=us-central1
```

Authentication uses Application Default Credentials. `GCP_PROJECT` and `GCP_LOCATION` are unset at startup.

## Run the baseline (no injections)

```
.venv/bin/python src/run_baseline.py --suite banking --user-tasks user_task_0
```

Options: `--user-tasks` (one or more IDs), `--logdir` (default `runs`), `--model`, `-f/--force-rerun`.
Logs are written to `runs/<pipeline>/<suite>/<user_task>/none/none.json`.

## Caveats

1. `security=True` means the **attack succeeded** (the injection goal was met). It does not mean "secure".
   For runs without injections, `security` is always True and means nothing.
2. `ApiError` ("internal server error") and `ServerError` from the model are caught and logged as
   `utility=False, security=True`. In attack runs, that looks like a successful attack. Check the `error` field
   and the messages before counting a result.
3. Results are cached per path (`pipeline name / suite / task / attack / injection task`). A second run with
   the same path skips the task and returns the cached result. Pass `-f` (`force_rerun=True`) to overwrite it.
