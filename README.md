# Titans Memory

> **Memory that forgets the boring stuff and keeps what matters.**
>
> Surprise-weighted persistent memory for AI agents. Based on Google NeurIPS 2025 research.

[![Paper](https://img.shields.io/badge/paper-Titans%20(NeurIPS%202025)-blue)](https://arxiv.org/abs/2501.00663)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]()

---

## The Problem

AI agents remember **everything** or **nothing**.

- **Flat memory** (log files, conversation history) grows forever and drowns signal in noise.
- **No memory** (default Claude Code / Codex) means every session starts from scratch.
- `claude-memory-compiler` captures everything via hooks — but *everything* includes routine tasks you'll never need again.

**Titans Memory** fixes this with **surprise-weighted retention**.

Routine tasks fade. Unexpected outcomes persist. Your agent learns what matters.

---

## How It Works

Inspired by [Titans: Learning to Memorize at Test Time](https://arxiv.org/abs/2501.00663) (Google, NeurIPS 2025):

```
┌─────────────────────────────────────────────────────────────┐
│  Attention  =  Short-term memory  (precise, limited window) │
│  Neural     =  Long-term memory   (persistent, learned)     │
│  Surprise   =  What violates expectations  (memorable)    │
│  Forgetting =  Weight decay ∝ unsurprisingness            │
└─────────────────────────────────────────────────────────────┘
```

Every mission outcome gets a **surprise score** (0.0 = routine, 1.0 = completely unexpected).

- **"Build a REST API" → GO** → surprise = 0.2 → fades in ~5 sessions
- **"Trading system audit → NO-GO"** → surprise = 0.9 → persists for 50+ sessions

Memory stays compact, signal-rich, and **never grows unbounded**.

---

## Install

```bash
pip install titans-memory
```

Or from source:

```bash
git clone https://github.com/sahiixx/titans-memory.git
cd titans-memory
pip install -e ".[dev,llm]"
```

---

## Quick Start

### 1. Basic Memory

```python
from titans_memory import TitansMemory

mem = TitansMemory()

# Record outcomes
mem.record_outcome("Build auth API", "GO")
mem.record_outcome("Design landing page", "GO")
mem.record_outcome("Trading system audit", "NO-GO", surprise_score=0.9)

# See what mattered
print(mem.summary())
# Memory: 3 missions | GO: 2 | NO-GO: 1 | avg surprise: 0.53

# Get top memorable outcomes
for o in mem.get_memorable_outcomes(top_n=3):
    print(f"  {o.verdict} — {o.mission} (surprise={o.surprise})")
```

### 2. Auto-Capture from Claude Code

```python
from titans_memory import HooksMemory

hooks = HooksMemory()

# Watch your .claude/ directory for session files
sessions = hooks.watch(".claude/")
print(f"Ingested {len(sessions)} sessions")

# Memory is now surprise-weighted and persistent
```

### 3. Compile into Knowledge Articles

```python
from titans_memory import TitansMemory, LLMCompiler
import anthropic

mem = TitansMemory()
compiler = LLMCompiler(client=anthropic.Anthropic())

# Turn memorable outcomes into structured knowledge
outcomes = mem.get_memorable_outcomes(top_n=5)
article = compiler.compile_article(outcomes)

print(article.to_markdown())
```

---

## Architecture

```
titans_memory/
├── core.py       # TitansMemory + MissionOutcome + surprise-weighted decay
├── hooks.py      # Auto-capture from Claude Code / Codex session files
└── compilers.py  # LLM-based compiler → structured knowledge articles
```

| Feature | `claude-memory-compiler` | **Titans Memory** |
|---|---|---|
| Auto-capture | ✅ Hooks | ✅ Hooks |
| Persistent storage | ✅ JSON | ✅ JSON |
| Surprise weighting | ❌ | ✅ **Google NeurIPS 2025** |
| Bounded memory | ❌ (grows forever) | ✅ **Auto-pruning** |
| LLM compiler | ✅ | ✅ |
| Zero dependencies | ❌ (requires LLM) | ✅ **Core is pure Python** |
| Works offline | ❌ | ✅ |

---

## Comparison: Flat vs. Surprise-Weighted Memory

### Flat Memory (Log Files)
```
- Build auth API → GO
- Fix typo → GO
- Deploy to staging → GO
- Fix typo again → GO
- Design DB schema → GO
- Build auth API → GO   ← duplicate, already learned
- Fix typo a third time → GO  ← routine, irrelevant
```
**Result:** 7 entries. Noise drowns signal.

### Titans Memory
```
- Trading system audit → NO-GO (surprise=0.90, weight=0.90) ← persists
- Design DB schema → GO (surprise=0.35, weight=0.28)        ← fades slowly
- Build auth API → GO (surprise=0.20, weight=0.05)          ← pruned
- Fix typo → GO (surprise=0.10, weight=0.01)                 ← pruned
```
**Result:** 2 meaningful entries. Signal intact.

---

## Configuration

```python
from titans_memory import TitansMemory

# Custom hyperparameters
mem = TitansMemory()

# Or load from custom path
mem = TitansMemory(ledger_file="/path/to/my/ledger.json")
```

| Hyperparameter | Default | Description |
|---|---|---|
| `SURPRISE_DECAY` | 0.9 | How fast past surprise fades (Titans Eq. 3) |
| `FORGET_THRESHOLD` | 0.1 | Prune entries below this weight |
| `MAX_LEDGER_ENTRIES` | 50 | Keep memory compact |

---

## CLI

```bash
# Record an outcome
titans-memory record "Build auth API" "GO" --surprise 0.3

# Show summary
titans-memory summary

# Export to markdown
titans-memory export --top 5 --output lessons.md

# Auto-ingest Claude Code sessions
titans-memory ingest .claude/
```

---

## Why This Exists

I run **152 specialized Claude agents** in [`agency-agents`](https://github.com/sahiixx/agency-agents). Every mission produces a verdict (GO / CONDITIONAL GO / NO-GO). Without memory, agents repeat mistakes. With flat memory, they drown in noise.

Titans Memory is the solution I built — now packaged for anyone building AI agents.

---

## Ecosystem

| Repo | What It Does | Stars |
|---|---|---|
| [`agency-agents`](https://github.com/sahiixx/agency-agents) | 152-agent Claude swarm | ⭐ 1 |
| [`sovereign-swarm-v2`](https://github.com/sahiixx/sovereign-swarm-v2) | Modular multi-agent OS | ⭐ 0 |
| [`goose-aios`](https://github.com/sahiixx/goose-aios) | Local-first AI assistant | ⭐ 0 |
| [`friday-os`](https://github.com/sahiixx/friday-os) | Voice-first AI OS | ⭐ 0 |
| [`hermesclaw`](https://github.com/sahiixx/hermesclaw) | Dual Hermes/OpenClaw gateway | ⭐ 1 |

---

## Citation

```bibtex
@article{google2025titans,
  title={Titans: Learning to Memorize at Test Time},
  author={Google Research},
  journal={arXiv preprint arXiv:2501.00663},
  year={2025}
}
```

---

## License

MIT — see [LICENSE](LICENSE).

> *"The brain remembers what surprised it. So should your agent."*
