"""Smoke test for Gemini on Vertex AI: plain generation and function calling.

Usage (from project root):
    .venv/bin/python src/vertex_check.py
"""

import os
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def diagnose(status, message: str) -> None:
    """Print a one-line diagnosis and fix for a known API error status."""
    if status == 403 or "PERMISSION_DENIED" in str(message):
        print("  Diagnosis: API not enabled, or ADC / quota project is wrong.")
        print("  Fix: enable the Vertex AI API on the project, and check that ADC "
              "and the quota project point to GOOGLE_CLOUD_PROJECT.")
    elif status == 404 or "NOT_FOUND" in str(message):
        print("  Diagnosis: model ID or region is wrong.")
        print("  Fix: pick a valid Flash model ID from the list below and set "
              "vertex.flash_model in config.yaml (or fix the region).")
    elif status == 429:
        print("  Diagnosis: quota exceeded.")
        print("  Fix: lower concurrency (--max-workers 1) and retry with exponential backoff.")
    else:
        print("  Diagnosis: unexpected API error.")
        print("  Fix: inspect the message above and check project, region and model ID.")


def list_flash_models(client: genai.Client) -> None:
    print("  Available models containing 'flash':")
    try:
        names = [m.name for m in client.models.list() if "flash" in (m.name or "").lower()]
    except Exception as exc:  # listing is diagnostic only
        print(f"    could not list models: {type(exc).__name__}: {exc}")
        return
    if not names:
        print("    (none found)")
    for name in names:
        print(f"    {name}")
    if names:
        print(f"  Suggestion: try one of the above, e.g. {names[0]}")


def handle_api_error(client: genai.Client, exc: errors.APIError) -> None:
    status = getattr(exc, "code", None)
    message = getattr(exc, "message", None) or str(exc)
    status_str = getattr(exc, "status", None) or ""
    print(f"  Status code: {status} {status_str}".rstrip())
    print(f"  Message: {message}")
    diagnose(status, f"{status_str} {message}")
    if status == 404 or "NOT_FOUND" in f"{status_str} {message}":
        list_flash_models(client)


def test_generate(client: genai.Client, model: str, location: str) -> bool:
    print("=== Test 1: generate_content ===")
    print(f"Model ID requested: {model}")
    print(f"Region: {location}")
    start = time.perf_counter()
    response = client.models.generate_content(model=model, contents="Reply with OK")
    latency_ms = (time.perf_counter() - start) * 1000

    model_version = getattr(response, "model_version", None)
    if model_version:
        print(f"Model version: {model_version}")
    usage = response.usage_metadata
    print(f"Input tokens: {usage.prompt_token_count}")
    print(f"Output tokens: {usage.candidates_token_count}")
    print(f"Latency: {latency_ms:.0f} ms")
    print(f"Response text: {response.text!r}")
    print("Test 1: PASS")
    return True


GET_TIME_DECL = types.FunctionDeclaration(
    name="get_time",
    description="Get the current time in a given timezone.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "timezone": types.Schema(
                type=types.Type.STRING,
                description="IANA timezone name, e.g. Asia/Tokyo",
            )
        },
        required=["timezone"],
    ),
)


def test_function_calling(client: genai.Client, model: str) -> bool:
    print("=== Test 2: function calling ===")
    config = types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=[GET_TIME_DECL])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = client.models.generate_content(
        model=model,
        contents="What time is it in Tokyo? Use the tool.",
        config=config,
    )
    calls = response.function_calls or []
    matches = [fc for fc in calls if fc.name == "get_time"]
    for fc in calls:
        print(f"Function call: {fc.name} args={dict(fc.args or {})}")
    if not matches:
        print("Test 2: FAIL (no get_time function_call in response)")
        print(f"Response text: {response.text!r}")
        return False
    print("Test 2: PASS")
    return True


def main() -> int:
    load_dotenv()
    config = load_config()
    vertex_cfg = config["vertex"]
    model = vertex_cfg["flash_model"]
    location = os.environ["GOOGLE_CLOUD_LOCATION"]
    project = os.environ["GOOGLE_CLOUD_PROJECT"]

    client = genai.Client(
        vertexai=True,
        project=project,
        location=location,
    )
    print(f"Project: {project}")

    results = {}
    for name, fn in [
        ("test1", lambda: test_generate(client, model, location)),
        ("test2", lambda: test_function_calling(client, model)),
    ]:
        try:
            results[name] = fn()
        except errors.APIError as exc:
            print(f"{name}: FAIL (API error)")
            handle_api_error(client, exc)
            results[name] = False
        except Exception as exc:
            print(f"{name}: FAIL ({type(exc).__name__}: {exc})")
            results[name] = False
        print()

    all_ok = all(results.values())
    print("Overall: PASS" if all_ok else "Overall: FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
