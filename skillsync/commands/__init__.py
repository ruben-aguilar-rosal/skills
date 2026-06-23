"""CLI command implementations — thin orchestrators over the stages and ports."""

from skillsync.commands.accept import AcceptError, run_accept
from skillsync.commands.add import AddOutcome, run_add
from skillsync.commands.discovery import DiscoveryNotice, surface_discoveries
from skillsync.commands.ignore import IgnoreError, run_ignore
from skillsync.commands.link import LinkAction, run_link
from skillsync.commands.regen import RegenOutcome, run_regen
from skillsync.commands.reprofile import ReprofileOutcome, run_reprofile
from skillsync.commands.status import SkillStatus, gather_status

__all__ = [
    "AcceptError",
    "AddOutcome",
    "DiscoveryNotice",
    "IgnoreError",
    "LinkAction",
    "RegenOutcome",
    "ReprofileOutcome",
    "SkillStatus",
    "gather_status",
    "run_accept",
    "run_add",
    "run_ignore",
    "run_link",
    "run_regen",
    "run_reprofile",
    "surface_discoveries",
]
