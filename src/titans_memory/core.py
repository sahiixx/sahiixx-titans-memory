"""
titans_memory/core.py — Surprise-weighted memory management.

Based on: "Titans: Learning to Memorize at Test Time" (Google, NeurIPS 2025)
Paper: https://arxiv.org/abs/2501.00663

Key idea:
  - Attention = short-term memory (precise, limited to context window)
  - Neural memory = long-term memory (persistent, learned)
  - Surprise metric: memorable events = those that violate expectations
  - Forgetting: weight decay proportional to how unsurprising something is

This module applies those principles to agent memory:
  - "Surprising" outcomes (unexpected verdicts, new patterns) persist longer
  - Routine outcomes decay and are pruned
  - Memory stays compact and signal-rich rather than growing unbounded
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Titans hyperparameters (adapted for discrete outcomes)
SURPRISE_DECAY = 0.9      # η — how fast past surprise fades (Titans Eq. 3)
FORGET_THRESHOLD = 0.1    # prune entries below this weight
MAX_LEDGER_ENTRIES = 50   # keep memory compact


def _default_ledger_path() -> Path:
    """Default ledger location: ~/.titans-memory/ledger.json"""
    return Path.home() / ".titans-memory" / "ledger.json"


class MissionOutcome:
    """A single mission result with a Titans-style surprise weight."""

    def __init__(
        self,
        mission: str,
        verdict: str,
        surprise: float,
        ts: Optional[str] = None,
        weight: Optional[float] = None,
    ):
        self.mission = mission
        self.verdict = verdict
        self.surprise = surprise  # 0.0 (routine) → 1.0 (completely unexpected)
        self.weight = weight if weight is not None else surprise
        self.ts = ts or datetime.now(timezone.utc).isoformat()

    def decay(self, eta: float = SURPRISE_DECAY) -> None:
        """Apply Titans-style forgetting: weight *= decay.

        Surprising things decay slower (they're more memorable).
        """
        self.weight *= eta * (1 - self.surprise * 0.3)

    def to_dict(self) -> dict:
        return {
            "mission": self.mission,
            "verdict": self.verdict,
            "surprise": self.surprise,
            "weight": self.weight,
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MissionOutcome":
        o = cls(d["mission"], d["verdict"], d["surprise"], d.get("ts"), d.get("weight"))
        if o.weight is None:
            o.weight = o.surprise
        return o


class TitansMemory:
    """Agent long-term memory with Titans-style surprise-based retention.

    Memorable outcomes (unexpected verdicts, new patterns) persist longer.
    Routine outcomes decay and are pruned, keeping memory signal-rich.

    Usage:
        mem = TitansMemory()
        mem.record_outcome(mission="Build auth API", verdict="NO-GO")
        print(mem.summary())
    """

    def __init__(self, ledger_file: Optional[Path] = None):
        self.ledger_file = ledger_file or _default_ledger_path()
        self.ledger: list[MissionOutcome] = []
        self._load_ledger()

    def _load_ledger(self) -> None:
        if self.ledger_file.exists():
            try:
                data = json.loads(self.ledger_file.read_text())
                self.ledger = [MissionOutcome.from_dict(d) for d in data]
            except (json.JSONDecodeError, KeyError, TypeError):
                backup = self.ledger_file.with_suffix(".json.bak")
                self.ledger_file.rename(backup)
                self.ledger = []
        else:
            self.ledger_file.parent.mkdir(parents=True, exist_ok=True)

    def _save_ledger(self) -> None:
        """Atomic write — tmp then rename to avoid corruption."""
        tmp = self.ledger_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps([o.to_dict() for o in self.ledger], indent=2))
        tmp.replace(self.ledger_file)

    def compute_surprise(self, verdict: str, recent_verdicts: list[str]) -> float:
        """Estimate surprise score: how much this verdict deviates from recent patterns.

        Returns 0.0 (completely expected) to 1.0 (totally unexpected).
        """
        if not recent_verdicts:
            return 0.5

        total = len(recent_verdicts)
        same = sum(1 for v in recent_verdicts if v.lower() == verdict.lower())
        frequency = same / total
        surprise = 1.0 - frequency

        # Rarer verdicts (e.g. NO-GO) are inherently more surprising
        if "no-go" in verdict.lower() and "conditional" not in verdict.lower():
            surprise = min(1.0, surprise + 0.3)

        return round(surprise, 3)

    def record_outcome(
        self, mission: str, verdict: str, surprise_score: Optional[float] = None
    ) -> MissionOutcome:
        """Record a mission outcome with Titans-style surprise weighting.

        If surprise_score is None, it's computed from recent verdict history.
        """
        # Decay all existing entries (Titans forgetting gate)
        for entry in self.ledger:
            entry.decay()

        # Prune low-weight entries (forgotten)
        self.ledger = [e for e in self.ledger if e.weight >= FORGET_THRESHOLD]

        # Compute surprise if not provided
        if surprise_score is None:
            recent = [e.verdict for e in self.ledger[-10:]]
            surprise_score = self.compute_surprise(verdict, recent)

        surprise_score = max(0.0, min(1.0, surprise_score))

        outcome = MissionOutcome(mission, verdict, surprise_score)
        self.ledger.append(outcome)

        # Keep ledger compact
        if len(self.ledger) > MAX_LEDGER_ENTRIES:
            self.ledger.sort(key=lambda e: e.weight, reverse=True)
            self.ledger = self.ledger[:MAX_LEDGER_ENTRIES]

        self._save_ledger()
        return outcome

    def get_memorable_outcomes(self, top_n: int = 5) -> list[MissionOutcome]:
        """Return the most memorable (highest-weight) mission outcomes."""
        return sorted(self.ledger, key=lambda e: e.weight, reverse=True)[:top_n]

    def to_markdown(self, top_n: int = 5) -> str:
        """Generate a Markdown summary of the most memorable outcomes."""
        if not self.ledger:
            return "_No mission history yet._"

        memorable = self.get_memorable_outcomes(top_n=top_n)
        lines = ["## Mission Memory (Titans-weighted, most memorable first)", ""]
        for o in memorable:
            lines.append(
                f"- [{o.ts[:10]}] {o.verdict.upper()} — {o.mission[:80]} "
                f"(surprise={o.surprise:.2f}, weight={o.weight:.2f})"
            )
        return "\n".join(lines)

    def summary(self) -> str:
        """Human-readable memory summary."""
        if not self.ledger:
            return "No mission history yet."

        total = len(self.ledger)
        go = sum(
            1
            for e in self.ledger
            if "go" in e.verdict.lower() and "no" not in e.verdict.lower()
        )
        no_go = sum(
            1
            for e in self.ledger
            if "no-go" in e.verdict.lower() and "conditional" not in e.verdict.lower()
        )
        conditional = total - go - no_go
        avg_surprise = sum(e.surprise for e in self.ledger) / total

        return (
            f"Memory: {total} missions | GO: {go} | CONDITIONAL: {conditional} | "
            f"NO-GO: {no_go} | avg surprise: {avg_surprise:.2f}"
        )
