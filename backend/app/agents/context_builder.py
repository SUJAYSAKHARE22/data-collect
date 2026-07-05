"""
Context builder: selects and reads a representative, budget-limited slice
of a collected project (metadata + tree + files + file content) to send to
the LLM. This never sends the entire project — it prioritizes entry files,
dependency manifests, and the largest source files up to a character budget,
which keeps requests fast and avoids blowing the model's context window.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dll", ".so",
    ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".avi",
    ".lock", ".map",
}

SKIP_DIR_PARTS = {"node_modules", ".git", "dist", "build", "__pycache__", "venv", ".venv", "coverage"}


@dataclass
class ContextFile:
    path: str
    language: str | None
    size_bytes: int
    content: str
    truncated: bool


@dataclass
class ProjectContext:
    project_name: str
    source: str
    input_type: str
    language: str | None
    framework: str | None
    total_files: int
    total_folders: int
    entry_files: list[str]
    dependency_files: list[str]
    languages: dict
    files: list[ContextFile] = field(default_factory=list)

    def file_paths(self) -> set[str]:
        return {f.path for f in self.files}


def _is_relevant(file_record: dict) -> bool:
    path = file_record.get("path", "")
    ext = (file_record.get("extension") or "").lower()
    if ext in BINARY_EXTENSIONS:
        return False
    parts = set(Path(path).parts)
    if parts & SKIP_DIR_PARTS:
        return False
    return True


def _score(file_record: dict) -> tuple:
    """Higher score = read first. Entry files and dependency files always win."""
    is_entry = bool(file_record.get("is_entry_file"))
    is_dep = bool(file_record.get("is_dependency_file"))
    size = file_record.get("size_bytes") or 0
    # Prefer entry/dependency files, then mid-sized source files (very large
    # generated files are usually noise, very tiny files rarely matter).
    mid_size_bonus = -abs(size - 4000)
    return (is_entry, is_dep, mid_size_bonus)


def build_project_context(
    metadata: dict,
    tree: dict | None,
    files: list[dict],
    project_dir: Path,
    max_files: int = 40,
    max_file_chars: int = 6000,
    max_total_chars: int = 70000,
) -> ProjectContext:
    relevant = [f for f in files if _is_relevant(f)]
    relevant.sort(key=_score, reverse=True)

    selected: list[ContextFile] = []
    total_chars = 0

    for record in relevant:
        if len(selected) >= max_files or total_chars >= max_total_chars:
            break
        rel_path = record.get("path")
        if not rel_path:
            continue
        target = (project_dir / rel_path).resolve()
        try:
            if not target.is_relative_to(project_dir.resolve()):
                continue
            if not target.exists() or not target.is_file():
                continue
            raw = target.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        remaining_budget = max_total_chars - total_chars
        char_limit = min(max_file_chars, remaining_budget)
        truncated = len(raw) > char_limit
        content = raw[:char_limit]
        total_chars += len(content)

        selected.append(
            ContextFile(
                path=rel_path,
                language=record.get("language"),
                size_bytes=record.get("size_bytes") or 0,
                content=content,
                truncated=truncated,
            )
        )

    return ProjectContext(
        project_name=metadata.get("project_name", "Unknown Project"),
        source=metadata.get("source", ""),
        input_type=metadata.get("input_type", "unknown"),
        language=metadata.get("language"),
        framework=metadata.get("framework"),
        total_files=len(files),
        total_folders=len(metadata.get("folders") or []),
        entry_files=metadata.get("entry_files") or [],
        dependency_files=metadata.get("dependencies") or [],
        languages=(metadata.get("extra") or {}).get("languages") or {},
        files=selected,
    )


def render_context_prompt(ctx: ProjectContext) -> str:
    """Render the ProjectContext into a single prompt-ready text block."""
    lines = [
        f"Project name: {ctx.project_name}",
        f"Source: {ctx.source}",
        f"Input type: {ctx.input_type}",
        f"Primary language: {ctx.language or 'Unknown'}",
        f"Framework: {ctx.framework or 'Unknown'}",
        f"Total files collected: {ctx.total_files}",
        f"Total folders: {ctx.total_folders}",
    ]
    if ctx.languages:
        lang_str = ", ".join(f"{k}: {v} bytes" for k, v in ctx.languages.items())
        lines.append(f"Language breakdown: {lang_str}")
    if ctx.entry_files:
        lines.append(f"Entry files: {', '.join(ctx.entry_files)}")
    if ctx.dependency_files:
        lines.append(f"Dependency manifests: {', '.join(ctx.dependency_files)}")

    lines.append("")
    lines.append(f"--- SOURCE FILES ({len(ctx.files)} of {ctx.total_files} included, budget-limited) ---")
    for f in ctx.files:
        marker = " [TRUNCATED]" if f.truncated else ""
        lines.append(f"\n=== FILE: {f.path} ({f.language or 'unknown'}, {f.size_bytes} bytes{marker}) ===")
        lines.append(f.content)

    return "\n".join(lines)
