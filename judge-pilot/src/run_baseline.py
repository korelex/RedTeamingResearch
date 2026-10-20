"""Run AgentDojo user tasks WITHOUT injections through Gemini on Vertex AI.

Usage (from project root):
    .venv/bin/python src/run_baseline.py --suite banking --user-tasks user_task_0
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentdojo.benchmark import benchmark_suite_without_injections  # noqa: E402
from agentdojo.logging import OutputLogger  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402

from vertex_setup import PROJECT_ROOT, build_pipeline  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

BENCHMARK_VERSION = "v1.2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="banking")
    parser.add_argument("--user-tasks", nargs="+", default=["user_task_0"])
    parser.add_argument("--logdir", default="runs")
    parser.add_argument("--model", default=None, help="Vertex model ID (default: config.yaml)")
    parser.add_argument("-f", "--force-rerun", action="store_true")
    args = parser.parse_args()

    logdir = Path(args.logdir)
    if not logdir.is_absolute():
        logdir = PROJECT_ROOT / logdir

    pipeline = build_pipeline(args.model)
    suite = get_suite(BENCHMARK_VERSION, args.suite)
    print(f"pipeline={pipeline.name} suite={suite.name} version={BENCHMARK_VERSION} logdir={logdir}")

    for task_id in args.user_tasks:
        start = time.time()
        # OutputLogger sets the log directory; without it TraceLogger writes inside site-packages.
        with OutputLogger(str(logdir)):
            results = benchmark_suite_without_injections(
                pipeline,
                suite,
                logdir=logdir,
                force_rerun=args.force_rerun,
                user_tasks=[task_id],
                benchmark_version=BENCHMARK_VERSION,
            )
        elapsed = time.time() - start
        utility = results["utility_results"][(task_id, "")]
        log_path = logdir / pipeline.name.replace("/", "_") / suite.name / task_id / "none" / "none.json"
        print(f"{task_id}: utility={utility} wall_time={elapsed:.1f}s log={log_path} exists={log_path.exists()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
