"""
Unit tests for the GitHub loader helper logic.

Network-dependent behavior (actual cloning, API calls) is not exercised here;
only the pure/parsing logic is tested to keep the suite fast and offline-friendly.
"""
from __future__ import annotations


import pytest

from app.loaders.github.github_loader import GitHubCloneError, GitHubLoader


def test_parse_owner_repo_https() -> None:
    owner, repo = GitHubLoader._parse_owner_repo("https://github.com/octocat/Hello-World")
    assert owner == "octocat"
    assert repo == "Hello-World"


def test_parse_owner_repo_with_git_suffix() -> None:
    owner, repo = GitHubLoader._parse_owner_repo("https://github.com/octocat/Hello-World.git")
    assert owner == "octocat"
    assert repo == "Hello-World"


def test_parse_owner_repo_invalid_url() -> None:
    with pytest.raises(GitHubCloneError):
        GitHubLoader._parse_owner_repo("https://example.com/not-github")


def test_build_clone_url_without_token() -> None:
    url = GitHubLoader._build_clone_url("https://github.com/octocat/Hello-World", None)
    assert url == "https://github.com/octocat/Hello-World"


def test_build_clone_url_with_token() -> None:
    url = GitHubLoader._build_clone_url("https://github.com/octocat/Hello-World", "MYTOKEN")
    assert url == "https://MYTOKEN@github.com/octocat/Hello-World"
