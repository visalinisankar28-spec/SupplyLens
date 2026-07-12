"""
Repository resolver.

Scorecard is keyed by GitHub owner/repo. Registry metadata gives us a raw
URL that may point at GitHub, GitLab, a bare domain, or nothing at all.
This module isolates that messy parsing so the rest of the codebase only
ever deals with a clean (owner, repo) tuple or None.
"""
import re
from dataclasses import dataclass

_GITHUB_URL_PATTERN = re.compile(
    r"github\.com[/:](?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?(?:/.*)?$"
)


@dataclass(frozen=True)
class GitHubRepoRef:
    owner: str
    repo: str


def resolve_github_repo(repository_url: str | None) -> GitHubRepoRef | None:
    """
    Extract a (owner, repo) pair from a repository URL if it points to GitHub.

    Returns None for non-GitHub URLs (e.g. self-hosted GitLab) - this is an
    honest, documented MVP limitation: Scorecard's public API and coverage
    are GitHub-centric, so non-GitHub-hosted components will show as
    "unresolved" in the health profile rather than silently guessing.
    """
    if not repository_url:
        return None
    match = _GITHUB_URL_PATTERN.search(repository_url)
    if not match:
        return None
    owner = match.group("owner")
    repo = match.group("repo")
    return GitHubRepoRef(owner=owner, repo=repo)
