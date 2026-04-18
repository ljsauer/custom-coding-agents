"""File writing, backup, and diff operations for refactoring.

This module handles the safe mutation of source files: creating backups,
computing diffs for user review, and writing approved changes.  It is the
only module that performs destructive file operations.
"""

import difflib
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pyagent.logging import get_logger

logger = get_logger(__name__)

_BACKUP_DIR_NAME = ".pyagent_backup"


@dataclass(frozen=True)
class FileChange:
    """A proposed change to a single file.

    Attributes:
        path: Absolute path to the target file.
        original: The original file content.
        refactored: The proposed new content.
        explanation: Human-readable explanation of what changed and why.
    """

    path: Path
    original: str
    refactored: str
    explanation: str

    @property
    def has_changes(self) -> bool:
        """Return True if the refactored content differs from the original."""
        return self.original != self.refactored

    @property
    def diff(self) -> str:
        """Compute a unified diff between original and refactored content."""
        original_lines = self.original.splitlines(keepends=True)
        refactored_lines = self.refactored.splitlines(keepends=True)

        return "".join(
            difflib.unified_diff(
                original_lines,
                refactored_lines,
                fromfile=f"a/{self.path.name}",
                tofile=f"b/{self.path.name}",
                lineterm="",
            )
        )

    @property
    def stat_summary(self) -> str:
        """Return a short summary of lines added/removed."""
        original_lines = self.original.splitlines()
        refactored_lines = self.refactored.splitlines()

        diff_lines = list(difflib.unified_diff(original_lines, refactored_lines, n=0))
        added = sum(
            1
            for line in diff_lines
            if line.startswith("+") and not line.startswith("+++")
        )
        removed = sum(
            1
            for line in diff_lines
            if line.startswith("-") and not line.startswith("---")
        )

        return f"[green]+{added}[/green] [red]-{removed}[/red]"


@dataclass
class RefactorPlan:
    """A collection of proposed file changes from a refactoring operation.

    Attributes:
        changes: List of proposed file changes.
        summary: High-level summary of the refactoring.
    """

    changes: list[FileChange] = field(default_factory=list)
    summary: str = ""

    @property
    def files_changed(self) -> int:
        """Number of files with actual changes."""
        return sum(1 for c in self.changes if c.has_changes)

    def add_change(
        self,
        path: Path,
        original: str,
        refactored: str,
        explanation: str,
    ) -> None:
        """Add a file change to the plan.

        Args:
            path: Path to the target file.
            original: Original file content.
            refactored: Proposed new content.
            explanation: What changed and why.
        """
        self.changes.append(
            FileChange(
                path=path,
                original=original,
                refactored=refactored,
                explanation=explanation,
            )
        )


def is_git_repo(path: Path) -> bool:
    """Check if a path is inside a git repository.

    Args:
        path: Any path to check.

    Returns:
        True if the path is tracked by git.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path if path.is_dir() else path.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def has_uncommitted_changes(path: Path) -> bool:
    """Check if a file has uncommitted changes in git.

    Args:
        path: Path to the file to check.

    Returns:
        True if the file has uncommitted modifications.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", str(path)],
            cwd=path.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def create_backup(path: Path) -> Path:
    """Create a timestamped backup of a file.

    Backups are stored in a ``.pyagent_backup/`` directory next to the file.

    Args:
        path: Path to the file to back up.

    Returns:
        Path to the backup file.

    Raises:
        FileNotFoundError: If the source file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Cannot back up non-existent file: {path}")

    backup_dir = path.parent / _BACKUP_DIR_NAME
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_name = f"{path.stem}_{timestamp}{path.suffix}"
    backup_path = backup_dir / backup_name

    shutil.copy2(path, backup_path)
    logger.info("Backed up %s → %s", path.name, backup_path)
    return backup_path


def write_changes(plan: RefactorPlan, *, backup: bool = True) -> list[Path]:
    """Write all approved changes in a refactor plan to disk.

    Args:
        plan: The refactoring plan with file changes.
        backup: Whether to create backups before writing.

    Returns:
        List of paths that were written.
    """
    written: list[Path] = []

    for change in plan.changes:
        if not change.has_changes:
            logger.debug("Skipping %s — no changes", change.path)
            continue

        if backup:
            create_backup(change.path)

        change.path.write_text(change.refactored, encoding="utf-8")
        logger.info("Wrote refactored content to %s", change.path)
        written.append(change.path)

    return written


def restore_backup(path: Path) -> bool:
    """Restore the most recent backup of a file.

    Args:
        path: Path to the file to restore.

    Returns:
        True if a backup was found and restored, False otherwise.
    """
    backup_dir = path.parent / _BACKUP_DIR_NAME
    if not backup_dir.exists():
        return False

    # Find the most recent backup for this file.
    pattern = f"{path.stem}_*{path.suffix}"
    backups = sorted(backup_dir.glob(pattern), reverse=True)

    if not backups:
        return False

    latest = backups[0]
    shutil.copy2(latest, path)
    logger.info("Restored %s from %s", path.name, latest)
    return True
