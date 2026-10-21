"""Build an AgentDojo pipeline backed by Gemini on Vertex AI.

The AgentDojo CLI only accepts models from a fixed enum (agentdojo/models.py),
so this module constructs the GoogleLLM element directly and wraps it in a
named AgentPipeline.
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google import genai

from agentdojo import models
from agentdojo.agent_pipeline import AgentPipeline, PipelineConfig
from agentdojo.agent_pipeline.llms.google_llm import GoogleLLM

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
GOOGLE_DISPLAY_NAME = "AI model developed by Google"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _prepare_env() -> tuple[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    # Legacy vars that can conflict with GOOGLE_CLOUD_* in some code paths.
    os.environ.pop("GCP_PROJECT", None)
    os.environ.pop("GCP_LOCATION", None)
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION")
    if not project or not location:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION must be set (see .env)")
    return project, location


def build_pipeline(model_id: str | None = None) -> AgentPipeline:
    """Return a no-defense AgentPipeline using Gemini via Vertex AI."""
    project, location = _prepare_env()
    model_id = model_id or load_config()["vertex"]["flash_model"]

    # Attacks look up the model display name here (base_attacks.py); patch at runtime only.
    models.MODEL_NAMES.setdefault(model_id, GOOGLE_DISPLAY_NAME)

    # Some models are served only from certain locations (e.g. Gemini 3.x only from "global").
    location = (load_config()["vertex"].get("model_locations") or {}).get(model_id, location)
    client = genai.Client(vertexai=True, project=project, location=location)
    llm = GoogleLLM(model_id, client)
    config = PipelineConfig(
        llm=llm,
        model_id=None,
        defense=None,
        system_message_name=None,
        system_message=None,  # None -> AgentDojo's default system message
        tool_output_format=None,  # default: yaml
    )
    pipeline = AgentPipeline.from_config(config)
    pipeline.name = f"{model_id}-vertex"
    return pipeline
