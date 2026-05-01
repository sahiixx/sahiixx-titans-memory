"""Tests for titans_memory."""

import json
import tempfile
from pathlib import Path

import pytest

from titans_memory import TitansMemory, MissionOutcome, HooksMemory, LLMCompiler


class TestMissionOutcome:
    def test_init(self):
        o = MissionOutcome("test mission", "GO", 0.5)
        assert o.mission == "test mission"
        assert o.verdict == "GO"
        assert o.surprise == 0.5
        assert o.weight == 0.5
        assert o.ts is not None

    def test_decay(self):
        o = MissionOutcome("test", "GO", 1.0)
        initial = o.weight
        o.decay()
        assert o.weight < initial
        assert o.weight > 0

    def test_roundtrip(self):
        o = MissionOutcome("test", "NO-GO", 0.8)
        d = o.to_dict()
        o2 = MissionOutcome.from_dict(d)
        assert o2.mission == o.mission
        assert o2.verdict == o.verdict
        assert o2.surprise == o.surprise
        assert o2.weight == o.weight


class TestTitansMemory:
    def test_empty_summary(self):
        with tempfile.TemporaryDirectory() as td:
            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            assert mem.summary() == "No mission history yet."

    def test_record_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            mem.record_outcome("Build auth API", "GO", surprise_score=0.3)
            mem.record_outcome("Design DB", "GO", surprise_score=0.2)
            mem.record_outcome("Fix security bug", "NO-GO", surprise_score=0.9)

            summary = mem.summary()
            assert "3 missions" in summary
            assert "NO-GO: 1" in summary

    def test_memorable_outcomes(self):
        with tempfile.TemporaryDirectory() as td:
            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            mem.record_outcome("Routine task", "GO", surprise_score=0.1)
            mem.record_outcome("Surprising failure", "NO-GO", surprise_score=0.9)

            memorable = mem.get_memorable_outcomes(top_n=1)
            assert len(memorable) == 1
            assert memorable[0].mission == "Surprising failure"

    def test_pruning(self):
        with tempfile.TemporaryDirectory() as td:
            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            # Fill ledger beyond max
            for i in range(60):
                mem.record_outcome(f"Mission {i}", "GO", surprise_score=0.1)
            assert len(mem.ledger) <= 50

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            mem1 = TitansMemory(ledger_file=path)
            mem1.record_outcome("Test", "GO", surprise_score=0.5)

            mem2 = TitansMemory(ledger_file=path)
            assert len(mem2.ledger) == 1
            assert mem2.ledger[0].mission == "Test"

    def test_compute_surprise(self):
        with tempfile.TemporaryDirectory() as td:
            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            s = mem.compute_surprise("GO", ["GO", "GO", "GO"])
            assert s < 0.5  # expected

            s2 = mem.compute_surprise("NO-GO", ["GO", "GO", "GO"])
            assert s2 > s  # more surprising

    def test_to_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            mem.record_outcome("Test", "GO", surprise_score=0.5)
            md = mem.to_markdown()
            assert "Mission Memory" in md
            assert "Test" in md


class TestHooksMemory:
    def test_watch_empty(self):
        with tempfile.TemporaryDirectory() as td:
            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            hooks = HooksMemory(memory=mem)
            sessions = hooks.watch(td)
            assert sessions == []

    def test_ingest_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "session.md"
            path.write_text("# Build auth API\n\nSome discussion here.\n\nerror: connection refused\n")

            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            hooks = HooksMemory(memory=mem)
            hooks._ingest_markdown_session(path.read_text(), "session.md")

            assert len(mem.ledger) == 1
            assert mem.ledger[0].verdict == "NO-GO"
            assert mem.ledger[0].surprise > 0.5

    def test_ingest_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "conversation.json"
            data = {
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "A" * 500},
                ]
            }
            path.write_text(json.dumps(data))

            mem = TitansMemory(ledger_file=Path(td) / "ledger.json")
            hooks = HooksMemory(memory=mem)
            hooks._ingest_json_session(data, "conversation.json")

            assert len(mem.ledger) == 1
            assert mem.ledger[0].verdict == "GO"


class TestLLMCompiler:
    def test_compile_empty(self):
        compiler = LLMCompiler()
        article = compiler.compile_article([])
        assert article.title == "Empty Memory"
        assert article.confidence == 0.0

    def test_rule_compile(self):
        compiler = LLMCompiler()
        outcomes = [
            MissionOutcome("Build API", "GO", 0.3),
            MissionOutcome("Fix bug", "NO-GO", 0.9),
            MissionOutcome("Deploy", "GO", 0.2),
        ]
        article = compiler.compile_article(outcomes)
        assert article.title is not None
        assert article.confidence > 0
        assert "Pattern:" in article.title or "GO" in article.title or "NO-GO" in article.title

    def test_compile_all(self):
        compiler = LLMCompiler()
        outcomes = [
            MissionOutcome("A", "GO", 0.3),
            MissionOutcome("B", "GO", 0.4),
            MissionOutcome("C", "NO-GO", 0.9),
            MissionOutcome("D", "NO-GO", 0.8),
        ]
        articles = compiler.compile_all(outcomes)
        assert len(articles) >= 2  # at least GO and NO-GO groups

    def test_markdown_output(self):
        compiler = LLMCompiler()
        article = compiler.compile_article([MissionOutcome("Test", "GO", 0.5)])
        md = article.to_markdown()
        assert "##" in md
        assert "Pattern:" in md
