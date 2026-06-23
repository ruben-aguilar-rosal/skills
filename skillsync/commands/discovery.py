"""Surface watched-folder discoveries as awareness issues.

`surface_discoveries` is the awareness half of the `watch`-folder feature: it runs
the deterministic `discover` stage and opens ONE GitHub issue per new or removed
skill, so the author learns about upstream folder changes without anything being
onboarded automatically. Adoption stays the explicit `skillsync add`; rejection is
`skillsync ignore`. The issues are the notification, never a merge gate.

Idempotency is load-bearing: discovery reports the same skill on every sync run, so
each issue is filed under a deterministic title and only opened when no OPEN issue
with that title already exists (`GhPort.find_issue`). A skill therefore yields at
most one live issue no matter how many times sync runs.
"""

from dataclasses import dataclass
from pathlib import Path

from skillsync.config import Config
from skillsync.ports.gh import GhPort
from skillsync.ports.git import GitPort
from skillsync.stages.discover import Discovery, discover

# Labels applied to every awareness issue, plus the per-kind marker label.
_BASE_LABELS = ["skillsync", "discovery"]


@dataclass(frozen=True)
class DiscoveryNotice:
    """One surfaced discovery: the finding plus the issue URL (new or pre-existing)."""

    repo: str
    skill_path: str
    name: str
    kind: str
    url: str


def surface_discoveries(
    config: Config, root: Path, *, git: GitPort, gh: GhPort
) -> list[DiscoveryNotice]:
    """Open an awareness issue per new/removed watched-folder skill, idempotently.

    Runs `discover`, then for each finding reuses an existing open issue with the
    same title or files a fresh one. Returns a `DiscoveryNotice` per finding (in
    discover order). Never onboards or ignores anything — it only surfaces.
    """
    notices: list[DiscoveryNotice] = []
    for finding in discover(config, git, root):
        url = _surface_one(finding, gh, root)
        notices.append(
            DiscoveryNotice(
                repo=finding.repo,
                skill_path=finding.skill_path,
                name=finding.name,
                kind=finding.kind,
                url=url,
            )
        )
    return notices


def _surface_one(finding: Discovery, gh: GhPort, root: Path) -> str:
    """Reuse or open the awareness issue for one finding; return its URL."""
    title = _title(finding)
    existing = gh.find_issue(root, title)
    if existing is not None:
        return existing
    body = _body(finding)
    labels = [*_BASE_LABELS, finding.kind]
    return gh.open_issue(root, title, body, labels)


def _title(finding: Discovery) -> str:
    """Build the deterministic, exact-match issue title for a finding."""
    if finding.kind == "new":
        return f"skillsync: new upstream skill {finding.skill_path} ({finding.repo})"
    return (
        f"skillsync: tracked skill {finding.skill_path} no longer exists upstream "
        f"({finding.repo})"
    )


def _body(finding: Discovery) -> str:
    """Render the awareness-issue body: what was found and the next-step commands."""
    if finding.kind == "new":
        return (
            f"`{finding.skill_path}` appeared in a watched folder of "
            f"`{finding.repo}` and is not yet tracked.\n\n"
            "Decide what to do — it will be surfaced again each sync until you do:\n\n"
            f"- **adopt** — onboard it (draft adaptation + full generation + PR):\n"
            f"  ```sh\n  skillsync add {finding.repo} {finding.skill_path}\n  ```\n"
            f"- **reject** — stop surfacing it:\n"
            f"  ```sh\n  skillsync ignore {finding.repo} {finding.skill_path}\n  ```\n"
        )
    return (
        f"`{finding.skill_path}` is pinned in `sources.yaml` but no longer exists "
        f"under the watched folder in `{finding.repo}` — it was deleted or renamed "
        "upstream.\n\n"
        "Its mirror and adaptation stay on disk; future syncs can no longer update "
        "it. Remove its pin from `sources.yaml` if you no longer want to track it, "
        "or re-`skillsync add` it under its new path.\n"
    )
