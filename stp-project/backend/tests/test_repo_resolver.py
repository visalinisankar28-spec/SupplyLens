"""Unit tests for GitHub repo URL parsing."""
from app.services.repo_resolver import resolve_github_repo


def test_resolves_standard_https_github_url():
    ref = resolve_github_repo("https://github.com/apache/logging-log4j2")
    assert ref is not None
    assert ref.owner == "apache"
    assert ref.repo == "logging-log4j2"


def test_resolves_git_plus_https_url():
    ref = resolve_github_repo("git+https://github.com/lodash/lodash.git")
    assert ref is not None
    assert ref.owner == "lodash"
    assert ref.repo == "lodash"


def test_returns_none_for_non_github_url():
    ref = resolve_github_repo("https://gitlab.com/some/project")
    assert ref is None


def test_returns_none_for_missing_url():
    assert resolve_github_repo(None) is None
