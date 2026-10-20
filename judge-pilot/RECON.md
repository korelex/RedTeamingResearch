# RECON

## Versions

- agentdojo: 0.1.35
- google-genai: 2.31.0

All paths below are relative to `.venv/lib/python3.14/site-packages/`. Abbreviations: `AD` = `agentdojo/`, `GG` = `google/genai/`.
Everything here comes from reading source. The only thing executed was one offline import check (`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "import agentdojo.scripts.benchmark ..."`), with no network and no model calls. It printed the attack registry and the v1.2.2 suites.

## a. Which file and class call Google models, and which SDK

- File: `AD/agent_pipeline/llms/google_llm.py`. Class: `GoogleLLM(BasePipelineElement)` (line 219).
- SDK: **google-genai** (the new SDK), not `google-generativeai` and not the `vertexai` SDK:
  - `google_llm.py:7` `from google import genai`
  - `google_llm.py:8` `from google.genai import types as genai_types`
  - `google_llm.py:9` `from google.genai.errors import ClientError`
- The actual call is `client.models.generate_content(model=model, contents=contents, config=generation_config)` at `google_llm.py:172-176`. It is wrapped by a tenacity retry (`google_llm.py:160-165`) that makes 3 attempts and does not retry on `ClientError` (4xx).
- `agentdojo/agent_pipeline/agent_pipeline.py:14` also has `from google import genai`, and it builds the client there (see b).
- There is a stale docstring at `google_llm.py:222-227` that says to run `vertexai.init()`. The code never calls `vertexai.init()`, and a grep for `vertexai` finds no import of the `vertexai` SDK.
- `AD/benchmark.py:8` imports `google.genai.errors.ServerError`. A Google 5xx is caught and recorded as `utility=False, security=True` (`benchmark.py:142-147`, `:309-312`).

## b. How the Google client is created and whether it respects the Vertex env vars

Trace for the CLI path:
1. `AD/scripts/benchmark.py:53-63`: `AgentPipeline.from_config(PipelineConfig(llm=model, model_id=model_id, ...))`, where `model` is the `--model` enum string.
2. `AD/agent_pipeline/agent_pipeline.py:186-190`: `get_llm(MODEL_PROVIDERS[ModelsEnum(config.llm)], config.llm, config.model_id, config.tool_delimiter)`.
3. `AD/agent_pipeline/agent_pipeline.py:102-104`:
   ```python
   elif provider == "google":
       client = genai.Client(vertexai=True, project=os.getenv("GCP_PROJECT"), location=os.getenv("GCP_LOCATION"))
       llm = GoogleLLM(model, client)
   ```
4. `GoogleLLM.__init__` stores the client as given (`google_llm.py:251-252`). Only if `client is None`, which is deprecated, does it build the same hard-coded client (`google_llm.py:257-259`):
   ```python
   self.client = genai.Client(
       vertexai=True, project=os.getenv("GCP_PROJECT"), location=os.getenv("GCP_LOCATION")
   )
   ```

What this means, based on the google-genai 2.31.0 source:
- **`vertexai=True` is hard-coded.** No API key is hard-coded, and it is not `vertexai=False`. `GOOGLE_GENAI_USE_VERTEXAI` is only consulted when `vertexai is None` (`GG/_api_client.py:705-731`), so here it is **ignored, but redundant**: Vertex is always on.
- AgentDojo reads **non-standard** env vars, `GCP_PROJECT` and `GCP_LOCATION`. When they are unset, `os.getenv` returns `None`, and google-genai then falls back to the standard ones:
  - `GG/_api_client.py:764-768`:
    ```python
    env_project = os.environ.get('GOOGLE_CLOUD_PROJECT', None)
    env_location = os.environ.get('GOOGLE_CLOUD_LOCATION', None)
    ...
    self.project = project or env_project
    self.location = location or env_location
    ```
  - So `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` **are respected** as long as `GCP_PROJECT` and `GCP_LOCATION` are unset. If `GCP_PROJECT` or `GCP_LOCATION` is set, it wins.
  - If no location is resolved and there is no API key, location defaults to `'global'` (`GG/_api_client.py:829-834`). If no project is resolved, the project is taken from ADC via `load_auth(project=None)` (`GG/_api_client.py:839-846`).
  - A stray `GOOGLE_API_KEY` or `GEMINI_API_KEY` is dropped when the project or location came from env (`GG/_api_client.py:809-821`).
- Credentials: no `credentials=` is passed, so google-genai uses ADC (`load_auth`, `GG/_api_client.py:844`, `:1403`).
- The CLI also calls `load_dotenv(".env")` from the CWD (`AD/scripts/benchmark.py:41-42`), so these vars can also live in `judge-pilot/.env`.

## c. Model selection on the CLI, `--model-id`, and custom models or pipelines

- `--model` takes **only a fixed enum**: `type=click.Choice([value for value in ModelsEnum])` (`AD/scripts/benchmark.py:109-114`). `from_config` also calls `ModelsEnum(config.llm)` (`agent_pipeline.py:187`), which raises an error for any string not in the enum.
- Gemini entries (`AD/models.py:39-54`, all mapped to provider `"google"` at `models.py:78-85`):
  `gemini-1.5-pro-002`, `gemini-1.5-pro-001`, `gemini-1.5-flash-002`, `gemini-1.5-flash-001`, `gemini-2.0-flash-exp`, `gemini-2.0-flash-001`, `gemini-2.5-flash-preview-04-17`, `gemini-2.5-pro-preview-05-06`.
  (Whether Vertex still serves these IDs is **unsure of the answer**, because it can't be determined from source.)
- `--model-id` is passed into `PipelineConfig.model_id` (`scripts/benchmark.py:56`). Inside `get_llm` it is used **only** for `provider == "local"` (`agent_pipeline.py:111-115`). For `google`, `model_id` is ignored, and the model string is the enum value (`agent_pipeline.py:104`). The help text says "The model id for local models." (`scripts/benchmark.py:119`).
- `-ml/--module-to-load` runs `importlib.import_module(module)` before anything else (`scripts/benchmark.py:228-229`). Its documented purpose is "registering custom attacks, defenses, or suites" (`:209`). The available hooks are:
  - attacks: `register_attack` (`AD/attacks/attack_registry.py:13-37`)
  - suites: `register_suite(suite, version)` (`AD/task_suite/load_suites.py:77-78`)
  - **There is no model or pipeline registry.** `ModelsEnum` is a `StrEnum` class (`models.py:4`), and the `--model` `click.Choice` list is built at decoration time (`scripts/benchmark.py:112`), before `-ml` modules are imported (`:228`). So a custom Gemini model ID **cannot** be selected through the CLI. A `-ml` module could only mutate dicts, e.g. `MODEL_NAMES`.
  - Defenses are a fixed list, `DEFENSES` (`agent_pipeline.py:43-48`), plus an if-chain in `from_config` (`:202-265`). That is not a registry either.
- **Custom model in Python (supported path):** `PipelineConfig.llm: str | BasePipelineElement` (`agent_pipeline.py:132`). When it is not a string, it is used as-is (`:186-190`), and `pipeline.name = llm.name` (`:191`, `:205`). `GoogleLLM` takes any model string plus a client (`google_llm.py:243-245`).
  - Caveat 1: `GoogleLLM` never sets `self.name`, and `BasePipelineElement.name` defaults to `None` (`AD/agent_pipeline/base_pipeline_element.py:14`). With `name=None`, results are neither cached nor loaded (`benchmark.py:86`, `:253`), and `TraceLogger.save` refuses to log (`AD/logging.py:230-233`). **Set `llm.name`** before calling `from_config`.
  - Caveat 2: the `important_instructions` and `tool_knowledge` attacks call `get_model_name_from_pipeline` (`AD/attacks/important_instructions_attacks.py:43`, `:111`). That function substring-matches the pipeline name against the keys of `MODEL_NAMES` and raises `ValueError` if nothing matches (`AD/attacks/base_attacks.py:138-147`). A new ID like `gemini-2.5-flash` matches no key in `models.py:91-118`. Fix: `MODEL_NAMES["gemini-2.5-flash"] = "AI model developed by Google"` before `load_attack`. This works because the dict is iterated at call time (`base_attacks.py:141`).
  - You can also build `AgentPipeline([...])` by hand (`agent_pipeline.py:165-166`), copying the no-defense layout from `agent_pipeline.py:203-205`: `[SystemMessage(...), InitQuery(), llm, ToolsExecutionLoop([ToolsExecutor(tool_result_to_str), llm])]`, then set `pipeline.name`.
  - Run with `benchmark_suite_with_injections(agent_pipeline, suite, attack, logdir, force_rerun, user_tasks=None, injection_tasks=None, verbose=True, benchmark_version=None)` (`AD/benchmark.py:160-170`) or `benchmark_suite_without_injections(agent_pipeline, suite, logdir, force_rerun, user_tasks=None, benchmark_version=None)` (`AD/benchmark.py:319-326`). Get the suite from `get_suite("v1.2.2", "banking")` (`load_suites.py:85-86`) and the attack from `load_attack(name, suite, pipeline)` (`attack_registry.py:40-50`). To write per-task JSON under logdir, wrap the call in `with OutputLogger(str(logdir)):` as the CLI does (`scripts/benchmark.py:64`; `TraceLogger` uses `delegate.logdir`, `AD/logging.py:166`).

## d. What `security` means

**`security == True` means the injection SUCCEEDED, i.e. the attacker goal was achieved and the defense failed.** It does *not* mean "secure".
- `BaseInjectionTask.security` docstring: "Checks if the injection goal was executed correctly. Returns True if the injection was executed correctly, False otherwise." (`AD/base_tasks.py:125-126`). Same for `security_from_traces` (`base_tasks.py:140-147`).
- Example: banking `InjectionTask0.security` returns True when a transaction to the attacker IBAN exists (`AD/default_suites/v1/banking/injection_tasks.py:50-61`).
- How it is computed: `TaskSuite.run_task_with_pipeline` docstring says "...the second indicating if the injection was successful." (`AD/task_suite/task_suite.py:360-362`). It calls `_check_task_result(injection_task, ...)` (`task_suite.py:412-418`), which goes to `_check_injection_task_security` (`:297-311`). That uses `security_from_traces` if it is not `None`, otherwise `task.security(...)`.
- How it is recorded: `run_task_with_injection_tasks` stores `security_results[(user_task.ID, injection_task_id)] = security` (`AD/benchmark.py:156`) and logs it via `logger.set_contextarg("security", security)` (`:153`). The CLI prints the mean as "Average security" (`scripts/benchmark.py:103-105`). That number is therefore the **attack success rate (ASR)**, despite the name.
- Gotchas:
  - With no injection, `run_task_with_pipeline` returns `(utility, True)` (`task_suite.py:409-410`), so baseline `security` is always True and meaningless.
  - On API errors (context length, cohere 500, google `ServerError`) the code records `security = True` (`benchmark.py:130`, `:139`, `:147`, `:292-312`). Under the "True = injection succeeded" meaning, that inflates ASR, so check the `error` field in the logs.
  - For DoS attacks, `security = not utility` (`benchmark.py:149-150`).

## e. Baseline (no injection) runs

- CLI: omit `--attack`. `attack` defaults to `None` (`scripts/benchmark.py:140-144`), and then `benchmark_suite_without_injections` is used (`scripts/benchmark.py:65-73`). Example (enum model only):
  `python -m agentdojo.scripts.benchmark --model gemini-2.0-flash-001 -s banking -ut user_task_0 --logdir ./runs`
  `-ut` may only be used with exactly one `-s` (`scripts/benchmark.py:237-238`).
- Python:
  ```python
  from agentdojo.benchmark import benchmark_suite_without_injections
  from agentdojo.task_suite.load_suites import get_suite
  from agentdojo.logging import OutputLogger
  suite = get_suite("v1.2.2", "banking")
  with OutputLogger("./runs"):
      res = benchmark_suite_without_injections(pipeline, suite, logdir=Path("./runs"), force_rerun=False,
                                               user_tasks=["user_task_0"], benchmark_version="v1.2.2")
  ```
  (signature: `AD/benchmark.py:319-326`). Results are saved to `runs/<pipeline.name>/<suite>/<user_task>/none/none.json` (`AD/logging.py:237-240`; `attack_type="none"` at `benchmark.py:278`).
- An attacked run also first runs each injection task as a plain user task with no injection (`benchmark.py:200-206`), giving `injection_tasks_utility_results`.

## f. Caching and skipping of repeats, and `-f/--force-rerun`

- **Yes, existing results are reused and the task is skipped.** Before running, both paths try `load_task_results(...)`, which reads `logdir/<pipeline_name>/<suite>/<user_task>/<attack_name>/<injection_task>.json` (`AD/benchmark.py:401-419`, path at `:409`):
  - with injection: `benchmark.py:86-103`. `if task_result is not None and not force_rerun:` logs "Skipping task ... because it was already run." and returns the stored `utility, security` with no model call.
  - without injection: `benchmark.py:253-270`, same logic, using `attack_name="none", injection_task="none"`.
  - A missing file or a file that fails validation (`FileNotFoundError` / `ValidationError`) means the task gets run (`benchmark.py:96-97`, `:263-264`). `TaskResults` rejects logs with fewer than 2 messages (`benchmark.py:376-380`).
  - Caching only happens if `logdir is not None and agent_pipeline.name is not None` (`benchmark.py:86`, `:253`).
- `-f/--force-rerun` (`scripts/benchmark.py:196-201`) sets `force_rerun=True`. The skip branch is then bypassed, the task is re-executed, and the JSON is **overwritten** (`open(file, "w")`, `AD/logging.py:240-241`). There is no repeat or seed index in the path, so N repeats need either `-f` (which overwrites) or a different `--logdir` or pipeline name per repeat.
- Minor: `save` replaces `/` with `_` in `pipeline_name` (`AD/logging.py:235`), but `load_task_results` does not (`benchmark.py:409`). Names containing `/` therefore never hit the cache. Gemini names don't contain `/`.

## g. Suites and attacks present in this version

The import check printed suites `['workspace', 'travel', 'banking', 'slack']` for v1.2.2 and an attack list that includes `important_instructions` and `tool_knowledge`.
- Suites, defined:
  - banking: `AD/default_suites/v1/banking/task_suite.py:37` `TaskSuite[BankingEnvironment]("banking", ...)`
  - slack: `AD/default_suites/v1/slack/task_suite.py:37` `TaskSuite[SlackEnvironment]("slack", ...)`
  - travel: `AD/default_suites/v1/travel/task_suite.py:112` `TaskSuite[TravelEnvironment]("travel", ...)`
- Suites, registered for the default benchmark version `v1.2.2` (CLI default at `scripts/benchmark.py:123`): `AD/task_suite/load_suites.py:56-61`. Travel is `get_new_version((1,2,0))`, banking is `(1,2,2)` and slack is `(1,2,0)`. These map into `_SUITES["v1.2.2"]` at `load_suites.py:72`.
- Attacks:
  - `important_instructions`: `@register_attack` on `ImportantInstructionsAttack`, with `name = "important_instructions"` (`AD/attacks/important_instructions_attacks.py:25-26`, `:38`).
  - `tool_knowledge`: `@register_attack` on `ToolKnowledgeAttack(ImportantInstructionsAttack)`, with `name = "tool_knowledge"` (`AD/attacks/important_instructions_attacks.py:92-94`).
  - Registration only happens on import of `agentdojo.attacks`, whose `__init__` imports the attack modules (`AD/attacks/__init__.py:1-3`). `ATTACKS[attack.name] = attack` is at `attack_registry.py:36`.

## Verdict: Vertex

Vertex works via env vars only

(This covers auth/client only. `get_llm` builds `genai.Client(vertexai=True, project=os.getenv("GCP_PROJECT"), location=os.getenv("GCP_LOCATION"))` (`agent_pipeline.py:103`). When `GCP_*` are unset, google-genai falls back to `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_LOCATION` and ADC (`GG/_api_client.py:764-768`, `:844`). It does not cover model choice: the CLI only accepts the 8 enum Gemini IDs (`models.py:39-54`). Any other Gemini ID needs a short Python driver, not a client adapter.)

Smallest path:
1. Env: `GOOGLE_CLOUD_PROJECT=<proj>`, `GOOGLE_CLOUD_LOCATION=<region or global>`, `GOOGLE_GENAI_USE_VERTEXAI=true` (harmless), ADC already logged in. Make sure `GCP_PROJECT`/`GCP_LOCATION` are **unset** (or set them to the same values).
2. Enum model via CLI: `python -m agentdojo.scripts.benchmark --model gemini-2.0-flash-001 -s banking -ut user_task_0 --attack important_instructions --logdir ./runs` (drop `--attack` for the baseline).
3. Any other model via Python: `llm = GoogleLLM("<model-id>", genai.Client()); llm.name = "<model-id>"`; `MODEL_NAMES["<model-id>"] = "AI model developed by Google"`; `pipeline = AgentPipeline.from_config(PipelineConfig(llm=llm, model_id=None, defense=None, system_message_name=None, system_message=None))`.
4. Then `with OutputLogger("./runs"): benchmark_suite_with_injections(pipeline, get_suite("v1.2.2","banking"), load_attack("important_instructions", suite, pipeline), Path("./runs"), False, user_tasks=[...], benchmark_version="v1.2.2")` (or `benchmark_suite_without_injections` for the baseline).
