"""Cost estimation and spend-cap tracking. Prices come only from config.yaml (`pricing:`)."""

from __future__ import annotations

import threading
from pathlib import Path

from src.logger import iter_logged_runs


class PricingMissing(KeyError):
    pass


def get_prices(config: dict, model_id: str) -> tuple[float, float]:
    pricing = (config.get("pricing") or {}).get(model_id)
    if not pricing or "input_per_mtok" not in pricing or "output_per_mtok" not in pricing:
        raise PricingMissing(f"No pricing for model {model_id!r} in config.yaml `pricing:`")
    return float(pricing["input_per_mtok"]), float(pricing["output_per_mtok"])


def estimate_cost(tokens_in: int, tokens_out: int, input_per_mtok: float, output_per_mtok: float) -> float:
    return (tokens_in * input_per_mtok + tokens_out * output_per_mtok) / 1_000_000


class CostTracker:
    """Running spend total. Starts from the sum of est_cost_usd over all existing data/runs/*.jsonl lines
    (errored runs included: their tokens were billed too)."""

    def __init__(self, config: dict, model_id: str, runs_dir: Path, spend_cap_usd: float | None = None):
        self.input_per_mtok, self.output_per_mtok = get_prices(config, model_id)
        self.spend_cap_usd = float(spend_cap_usd if spend_cap_usd is not None else config["spend_cap_usd"])
        self._lock = threading.Lock()
        self.total = 0.0
        for r in iter_logged_runs(runs_dir):
            c = r.get("est_cost_usd")
            if isinstance(c, (int, float)):
                self.total += float(c)
        self.starting_total = self.total

    def cost_of(self, tokens_in: int, tokens_out: int) -> float:
        return estimate_cost(tokens_in, tokens_out, self.input_per_mtok, self.output_per_mtok)

    def add(self, usd: float) -> None:
        with self._lock:
            self.total += usd

    def should_stop(self) -> bool:
        with self._lock:
            return self.total >= self.spend_cap_usd
