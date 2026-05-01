"""
Titans Memory — Surprise-weighted persistent memory for AI agents.

Based on "Titans: Learning to Memorize at Test Time" (Google, NeurIPS 2025)
Paper: https://arxiv.org/abs/2501.00663

Unlike flat memory systems that remember everything (and grow forever),
Titans Memory weights every experience by how *surprising* it was.
Routine tasks fade. Unexpected outcomes persist. Your agent learns what matters.
"""

from .core import MissionOutcome, TitansMemory
from .hooks import HooksMemory
from .compilers import LLMCompiler

__version__ = "0.1.0"
__all__ = ["MissionOutcome", "TitansMemory", "HooksMemory", "LLMCompiler"]
