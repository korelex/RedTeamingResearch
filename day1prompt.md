# Phase 0 — Install AgentDojo (explicit steps)

1. Check prerequisites and print versions: `python3 --version` (need 3.10+),
   `git --version`, `gcloud --version`. If gcloud is missing, STOP and tell me
   how to install it for my OS. Do not install it yourself.
2. Create the project and a fresh virtual environment:
     mkdir judge-pilot && cd judge-pilot
     python3 -m venv .venv && source .venv/bin/activate
     pip install --upgrade pip
3. Install AgentDojo and the Google SDK:
     pip install agentdojo google-genai pyyaml
   Then run `pip show agentdojo google-genai` and write both versions into
   config.yaml and RECON.md. Pin them in requirements.txt with `pip freeze`.
4. Verify the install works offline: list the available suites and attacks
   using AgentDojo's own API or CLI help (no model call yet).
5. Recon by reading the installed source (not guessing):
   a. Which file and class call Google models, and which SDK they use.
   b. Whether that code creates its client in a way that respects the Vertex env
      vars (GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION),
      or hard-codes an API key path.
   c. Whether the benchmark CLI accepts any model ID, or only a fixed list of
      model names. If fixed, explain how to register a custom model/pipeline.
   d. The exact meaning of the `security` result (does True = injection succeeded?).
   e. How to run user tasks with no injection (baseline).
   f. Whether repeats are cached/skipped when logs already exist.
   g. Confirm suites banking, slack, travel and attacks important_instructions,
      tool_knowledge exist in this version.
6. Write RECON.md with answers to a–g, with file paths and line numbers as evidence.

🛑 HUMAN CHECKPOINT 1: show me RECON.md. Say clearly: "Vertex works via env vars
only" OR "Vertex needs an adapter, because <reason from source>".

# Phase 1 — Connect Vertex AI (explicit steps)

Step A — commands for ME to run (print them; do NOT run any auth command yourself):
     gcloud auth login
     gcloud config set project <MY_PROJECT_ID>
     gcloud services enable aiplatform.googleapis.com
     gcloud auth application-default login
     gcloud auth application-default set-quota-project <MY_PROJECT_ID>
Wait for me to say "auth done".

Step B — environment config:
- Create .env.example (committed) and .env (gitignored) with:
     GOOGLE_GENAI_USE_VERTEXAI=True
     GOOGLE_CLOUD_PROJECT=<MY_PROJECT_ID>
     GOOGLE_CLOUD_LOCATION=us-central1
- Load .env at the start of every script (python-dotenv). Never print the project's
  credentials. Printing the project ID is fine.

Step C — connection test (src/vertex_check.py):
- Using google-genai with vertexai=True, send one tiny prompt ("Reply with OK") to
  the Gemini Flash model ID from config.yaml.
- Print: model ID actually used, region, input/output tokens, latency, response text.
- If it fails, diagnose by error type and tell me the fix:
    403 / permission denied → API not enabled or ADC/quota project wrong
    404 model not found     → model ID or region wrong; list valid Flash IDs for my region
    429                     → quota; suggest lower concurrency
- Also do one tool-calling test (a dummy function like get_time) to confirm function
  calling works through Vertex, since AgentDojo depends on it.

Step D — wire into AgentDojo:
- If recon says env vars are enough: run 1 AgentDojo banking task with no injection
  and confirm it completes through Vertex.
- If not: write src/vertex_setup.py, a minimal adapter that builds AgentDojo's
  Google LLM element with a Vertex client (or registers a custom pipeline). Keep it
  small, document it in README.md, then run the same 1-task test.

🛑 HUMAN CHECKPOINT 2: show me the connection test output and the 1-task AgentDojo
result. I will check that the call appears in Vertex AI usage in the console
before we continue.