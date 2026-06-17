"""Pipeline stages: deterministic and agentic steps over the skill model."""

from skillsync.stages.detect import ChangeSet, detect
from skillsync.stages.gate import Finding, GateResult, run_gate

__all__ = ["ChangeSet", "detect", "Finding", "GateResult", "run_gate"]
