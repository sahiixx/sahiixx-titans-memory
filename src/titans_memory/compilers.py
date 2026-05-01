"""
titans_memory/compilers.py — LLM-based memory compiler.

Inspired by Karpathy's LLM Knowledge Base architecture and
claude-memory-compiler's structured knowledge articles.

Takes raw Titans-weighted outcomes and compiles them into:
  - Structured knowledge articles
  - Decision trees
  - Design patterns (recurring solutions)

Usage:
    from titans_memory import TitansMemory, LLMCompiler

    mem = TitansMemory()
    compiler = LLMCompiler()
    article = compiler.compile_article(mem.get_memorable_outcomes())
"""

import json
from dataclasses import dataclass, asdict
from typing import Optional

from .core import MissionOutcome


@dataclass
class KnowledgeArticle:
    """A compiled memory article — the output of the Titans compiler."""

    title: str
    pattern: str
    context: str
    decision: str
    outcome: str
    confidence: float  # 0.0–1.0 based on surprise weight and frequency

    def to_markdown(self) -> str:
        return (
            f"## {self.title}\n\n"
            f"**Pattern:** {self.pattern}\n\n"
            f"**Context:** {self.context}\n\n"
            f"**Decision:** {self.decision}\n\n"
            f"**Outcome:** {self.outcome}\n\n"
            f"**Confidence:** {self.confidence:.2f}\n"
        )

    def to_dict(self) -> dict:
        return asdict(self)


class LLMCompiler:
    """Compile Titans-weighted outcomes into structured knowledge.

    Requires an LLM client (OpenAI or Anthropic) to generate articles.
    Falls back to rule-based compilation if no client is available.
    """

    def __init__(self, client: Optional[object] = None, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    def compile_article(
        self, outcomes: list[MissionOutcome], title: Optional[str] = None
    ) -> KnowledgeArticle:
        """Compile memorable outcomes into a single knowledge article."""
        if not outcomes:
            return KnowledgeArticle(
                title="Empty Memory",
                pattern="none",
                context="No memorable outcomes available.",
                decision="none",
                outcome="none",
                confidence=0.0,
            )

        # Try LLM compilation if available
        if self.client is not None:
            return self._llm_compile(outcomes, title)

        # Fallback: rule-based compilation
        return self._rule_compile(outcomes, title)

    def _llm_compile(
        self, outcomes: list[MissionOutcome], title: Optional[str] = None
    ) -> KnowledgeArticle:
        """Use an LLM to synthesize outcomes into a knowledge article."""
        prompt = self._build_prompt(outcomes)

        try:
            if hasattr(self.client, "messages"):
                # Anthropic client
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = response.content[0].text
            elif hasattr(self.client, "chat"):
                # OpenAI client
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                )
                content = response.choices[0].message.content
            else:
                raise ValueError("Unsupported client")

            return self._parse_article(content, outcomes, title)
        except Exception:
            return self._rule_compile(outcomes, title)

    def _build_prompt(self, outcomes: list[MissionOutcome]) -> str:
        lines = [
            "You are a memory compiler. Synthesize these agent mission outcomes into a single knowledge article.",
            "",
            "Outcomes (most memorable first):",
        ]
        for o in outcomes:
            lines.append(f"- [{o.ts[:10]}] {o.verdict.upper()}: {o.mission} (surprise={o.surprise}, weight={o.weight:.2f})")
        lines.extend([
            "",
            "Generate a JSON object with these fields:",
            '{"title": "...", "pattern": "...", "context": "...", "decision": "...", "outcome": "..."}',
        ])
        return "\n".join(lines)

    def _parse_article(
        self, content: str, outcomes: list[MissionOutcome], title: Optional[str] = None
    ) -> KnowledgeArticle:
        """Parse LLM output into a KnowledgeArticle."""
        # Extract JSON from markdown code blocks or raw text
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return self._rule_compile(outcomes, title)

        avg_confidence = sum(o.weight for o in outcomes) / len(outcomes)
        return KnowledgeArticle(
            title=title or data.get("title", "Compiled Memory"),
            pattern=data.get("pattern", "unknown"),
            context=data.get("context", ""),
            decision=data.get("decision", ""),
            outcome=data.get("outcome", ""),
            confidence=round(avg_confidence, 3),
        )

    def _rule_compile(
        self, outcomes: list[MissionOutcome], title: Optional[str] = None
    ) -> KnowledgeArticle:
        """Rule-based compilation without an LLM."""
        # Find the most common pattern
        verdicts = [o.verdict for o in outcomes]
        most_common = max(set(verdicts), key=verdicts.count)

        # Use highest-surprise outcome as the representative
        representative = max(outcomes, key=lambda o: o.surprise)

        avg_confidence = sum(o.weight for o in outcomes) / len(outcomes)

        return KnowledgeArticle(
            title=title or f"Pattern: {most_common} outcomes",
            pattern=f"{most_common} in {len(outcomes)} missions",
            context=representative.mission[:200],
            decision=f"Typical verdict: {most_common}",
            outcome=f"Surprise score: {representative.surprise:.2f}",
            confidence=round(avg_confidence, 3),
        )

    def compile_all(
        self, outcomes: list[MissionOutcome], articles_per_group: int = 3
    ) -> list[KnowledgeArticle]:
        """Compile outcomes into multiple articles, grouped by verdict type."""
        groups: dict[str, list[MissionOutcome]] = {}
        for o in outcomes:
            groups.setdefault(o.verdict, []).append(o)

        articles = []
        for verdict, group in groups.items():
            group_sorted = sorted(group, key=lambda o: o.weight, reverse=True)
            for i in range(0, min(len(group_sorted), articles_per_group * 3), 3):
                chunk = group_sorted[i : i + 3]
                articles.append(
                    self.compile_article(chunk, title=f"{verdict} Pattern #{i // 3 + 1}")
                )
        return articles
