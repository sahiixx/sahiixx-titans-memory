"""
titans_memory/hooks.py — Hooks-based auto-capture for Claude Code & Codex.

Inspired by claude-memory-compiler (coleam00) — auto-capture every session
without manual instrumentation. Then layer Titans surprise-weighting on top
so your agent remembers what mattered, not everything.

Usage:
    from titans_memory.hooks import HooksMemory

    hooks = HooksMemory()
    hooks.watch(".claude/")          # auto-detect session files
    hooks.on_session_end(callback)   # your hook
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

SESSION_PATTERNS = [
    re.compile(r"conversation.*\.json", re.I),
    re.compile(r"session.*\.json", re.I),
    re.compile(r"claude.*\.json", re.I),
    re.compile(r"\.claude.*\.md", re.I),
]


def _find_sessions(directory: Path) -> list[Path]:
    """Find potential session files in a directory."""
    sessions = []
    if directory.exists():
        for pattern in SESSION_PATTERNS:
            sessions.extend(directory.rglob("*"))
    # Filter by pattern
    matched = []
    for p in sessions:
        if p.is_file() and any(pat.search(p.name) for pat in SESSION_PATTERNS):
            matched.append(p)
    return matched


class HooksMemory:
    """Auto-capture memory from Claude Code / Codex sessions.

    Watches session directories, extracts key decisions, and feeds them
    into TitansMemory with automatic surprise scoring.
    """

    def __init__(self, memory: Optional["TitansMemory"] = None):
        from .core import TitansMemory

        self.memory = memory or TitansMemory()
        self._callbacks: list[Callable] = []

    def watch(self, directory: str | Path) -> list[Path]:
        """Scan a directory for session files and auto-ingest them."""
        sessions = _find_sessions(Path(directory))
        for session_file in sessions:
            self._ingest_session(session_file)
        return sessions

    def _ingest_session(self, path: Path) -> None:
        """Parse a session file and record memorable outcomes."""
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            return

        # Try JSON first (Claude Code conversation exports)
        if path.suffix == ".json":
            try:
                data = json.loads(text)
                self._ingest_json_session(data, path.name)
                return
            except json.JSONDecodeError:
                pass

        # Fallback: extract markdown headings as mission + verdict proxies
        self._ingest_markdown_session(text, path.name)

    def _ingest_json_session(self, data: dict, source: str) -> None:
        """Extract from Claude Code conversation JSON."""
        messages = data.get("messages", data.get("conversation", []))
        if not messages:
            return

        # Use last assistant message as "verdict"
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        if not assistant_msgs:
            return

        last = assistant_msgs[-1]
        content = last.get("content", "")

        # Heuristic: long responses = complex mission; short = routine
        mission = f"Session from {source}"
        verdict = "GO" if len(content) > 200 else "CONDITIONAL GO"

        # Surprise: detect keywords indicating unexpected outcomes
        surprise = 0.3
        unexpected_keywords = ["error", "fail", "bug", "unexpected", "no-go", "refactor"]
        lower = content.lower()
        for kw in unexpected_keywords:
            if kw in lower:
                surprise = min(1.0, surprise + 0.2)

        self.memory.record_outcome(mission, verdict, surprise_score=round(surprise, 3))
        self._fire_callbacks(mission, verdict, surprise)

    def _ingest_markdown_session(self, text: str, source: str) -> None:
        """Extract from markdown session logs."""
        lines = text.splitlines()
        if len(lines) < 3:
            return

        mission = f"Markdown session from {source}"
        # Use first heading as mission name
        for line in lines:
            if line.startswith("# "):
                mission = line[2:].strip()[:100]
                break

        verdict = "GO"  # default
        surprise = 0.2

        # Check for error/failure patterns
        lower = text.lower()
        if any(kw in lower for kw in ["error", "fail", "exception", "no-go"]):
            verdict = "NO-GO"
            surprise = 0.8
        elif any(kw in lower for kw in ["warning", "todo", "fixme", "refactor"]):
            verdict = "CONDITIONAL GO"
            surprise = 0.5

        self.memory.record_outcome(mission, verdict, surprise_score=round(surprise, 3))
        self._fire_callbacks(mission, verdict, surprise)

    def on_session_end(self, callback: Callable) -> None:
        """Register a callback invoked after each session ingestion."""
        self._callbacks.append(callback)

    def _fire_callbacks(self, mission: str, verdict: str, surprise: float) -> None:
        for cb in self._callbacks:
            try:
                cb(mission, verdict, surprise)
            except Exception:
                pass
