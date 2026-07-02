"""
Loader for public and private GitHub repositories.

Uses GitPython to clone the repository and PyGithub to fetch additional
repository metadata (owner, languages, license, description) via the API.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import git
from github import Github, GithubException
from github.Auth import Token

from app.schemas.metadata import InputType, ProjectMetadata
from app.utils.file_utils import is_dependency_file, is_entry_file
from app.utils.logger import get_logger
from app.utils.tree_builder import build_tree

logger = get_logger(__name__)

_GITHUB_URL_RE = re.compile(
    r"github\.com[/:](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?/?$"
)


class GitHubCloneError(Exception):
    """Raised when cloning a GitHub repository fails."""


class GitHubLoader:
    """Clones GitHub repositories and collects their metadata."""

    def __init__(self, default_token: str | None = None, clone_timeout_seconds: int = 300) -> None:
        self._default_token = default_token
        self._clone_timeout = clone_timeout_seconds

    def collect(
        self,
        repo_url: str,
        project_dir: Path,
        branch: str | None = None,
        access_token: str | None = None,
    ) -> tuple[dict, dict, list]:
        """
        Clone `repo_url` into `project_dir` and build tree/files/metadata.
        """
        token = access_token or self._default_token
        owner, repo_name = self._parse_owner_repo(repo_url)
        clone_url = self._build_clone_url(repo_url, token)

        logger.info("Cloning GitHub repository %s (branch=%s)", repo_url, branch or "default")
        commit_hash, resolved_branch = self._clone(clone_url, project_dir, branch)

        api_metadata = self._fetch_api_metadata(owner, repo_name, token)

        tree, files, folders = build_tree(project_dir)
        entry_files = [f["path"] for f in files if is_entry_file(f["name"])]
        dependencies = [f["path"] for f in files if is_dependency_file(f["name"])]

        readme_content = self._find_readme(project_dir)

        metadata = ProjectMetadata(
            input_type=InputType.GITHUB_PRIVATE if token else InputType.GITHUB_PUBLIC,
            project_name=repo_name,
            source=repo_url,
            language=api_metadata.get("primary_language"),
            files=[f["path"] for f in files],
            folders=folders,
            entry_files=entry_files,
            dependencies=dependencies,
            extra={
                "owner": owner,
                "branch": resolved_branch,
                "commit_hash": commit_hash,
                "license": api_metadata.get("license"),
                "languages": api_metadata.get("languages", {}),
                "description": api_metadata.get("description"),
                "stars": api_metadata.get("stars"),
                "readme_present": readme_content is not None,
            },
        ).model_dump()

        return metadata, tree, files

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
        match = _GITHUB_URL_RE.search(repo_url)
        if not match:
            raise GitHubCloneError(f"Could not parse owner/repo from URL: {repo_url}")
        return match.group("owner"), match.group("repo")

    @staticmethod
    def _build_clone_url(repo_url: str, token: str | None) -> str:
        """Inject a PAT into the clone URL for private repository access."""
        if not token:
            return repo_url
        if repo_url.startswith("https://"):
            return repo_url.replace("https://", f"https://{token}@", 1)
        return repo_url

    def _clone(self, clone_url: str, project_dir: Path, branch: str | None) -> tuple[str, str]:
        project_dir.mkdir(parents=True, exist_ok=True)
        try:
            kwargs: dict[str, Any] = {"depth": 1}
            if branch:
                kwargs["branch"] = branch
            repo = git.Repo.clone_from(clone_url, project_dir, **kwargs)
            commit_hash = repo.head.commit.hexsha
            resolved_branch = repo.active_branch.name if not repo.head.is_detached else (branch or "unknown")
            return commit_hash, resolved_branch
        except git.GitCommandError as exc:
            raise GitHubCloneError(f"Failed to clone repository: {exc}") from exc

    @staticmethod
    def _fetch_api_metadata(owner: str, repo_name: str, token: str | None) -> dict:
        """Fetch supplementary metadata via the GitHub API. Best-effort; failures are non-fatal."""
        try:
            gh = Github(auth=Token(token)) if token else Github()
            repo = gh.get_repo(f"{owner}/{repo_name}")
            license_info = None
            try:
                license_info = repo.get_license().license.name
            except GithubException:
                license_info = None

            return {
                "primary_language": repo.language,
                "languages": repo.get_languages(),
                "license": license_info,
                "description": repo.description,
                "stars": repo.stargazers_count,
            }
        except GithubException as exc:
            logger.warning("GitHub API metadata fetch failed for %s/%s: %s", owner, repo_name, exc)
            return {}
        except Exception as exc:  # noqa: BLE001 - best-effort enrichment, never fatal
            logger.warning("Unexpected error fetching GitHub API metadata: %s", exc)
            return {}

    @staticmethod
    def _find_readme(project_dir: Path) -> str | None:
        for candidate in ("README.md", "README.rst", "README.txt", "readme.md"):
            path = project_dir / candidate
            if path.exists():
                try:
                    return path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    return None
        return None
