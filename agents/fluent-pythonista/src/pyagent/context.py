"""Codebase ingestion and context assembly.

This module handles discovering Python files, reading their contents, building
a structural map via AST parsing, and — critically — selecting *which* code to
include in LLM prompts so that large codebases can be analyzed without
blowing token budgets.

The core strategy is a two-pass architecture:

1. **Index pass** — discover all Python files, parse each into a lightweight
   ``ModuleInfo`` with structural metadata (classes, functions, imports,
   constants).  This is cheap and runs once per session.

2. **Assembly pass** — given an operation (review, refactor, explain) and an
   optional user query, score and rank modules by relevance, then pack source
   code into the prompt within a configurable token budget.  High-priority
   files get full source; lower-priority files get structural summaries only.
"""

import ast
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from pyagent.logging import get_logger

logger = get_logger(__name__)


# ───────────────────────────────────────────────────────────────────────────
# Constants
# ───────────────────────────────────────────────────────────────────────────

# Directories to skip during file discovery.
_IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "dist",
    "build",
    "*.egg-info",
    "migrations",
}

# Filename patterns that signal low-priority or skippable files.
_LOW_PRIORITY_PATTERNS = {
    "conftest.py",
    "setup.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
}

# Rough chars-per-token ratio for budget estimation.
_CHARS_PER_TOKEN = 4

# Default token budget for assembled context.
DEFAULT_TOKEN_BUDGET = 30_000

# Maximum tokens to spend on the structural summary.
_SUMMARY_TOKEN_BUDGET = 4_000


# ───────────────────────────────────────────────────────────────────────────
# Data models
# ───────────────────────────────────────────────────────────────────────────


class FileCategory(StrEnum):
    """Classification of a Python file's role in the project."""

    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    INIT = "init"
    MIGRATION = "migration"
    GENERATED = "generated"


@dataclass(frozen=True)
class FunctionInfo:
    """Metadata for a function or method extracted from AST."""

    name: str
    lineno: int
    end_lineno: int | None
    args: list[str]
    return_annotation: str | None
    docstring: str | None
    is_async: bool

    @property
    def line_count(self) -> int:
        """Approximate line count of the function body."""
        if self.end_lineno is None:
            return 1
        return self.end_lineno - self.lineno + 1


@dataclass(frozen=True)
class ClassInfo:
    """Metadata for a class extracted from AST."""

    name: str
    lineno: int
    end_lineno: int | None
    bases: list[str]
    docstring: str | None
    methods: list[FunctionInfo]

    @property
    def line_count(self) -> int:
        """Approximate line count of the class body."""
        if self.end_lineno is None:
            return 1
        return self.end_lineno - self.lineno + 1


@dataclass(frozen=True)
class ModuleInfo:
    """Structural summary of a single Python module."""

    path: Path
    docstring: str | None
    imports: list[str]
    classes: list[ClassInfo]
    functions: list[FunctionInfo]
    constants: list[str]
    source: str
    category: FileCategory

    @property
    def line_count(self) -> int:
        """Total line count of the source."""
        return self.source.count("\n") + 1

    @property
    def token_estimate(self) -> int:
        """Rough token count for the full source."""
        return len(self.source) // _CHARS_PER_TOKEN

    @property
    def is_empty_init(self) -> bool:
        """Return True if this is a trivial ``__init__.py`` (re-exports only)."""
        if self.category != FileCategory.INIT:
            return False
        # An init file with no classes, no functions, and fewer than 20 lines
        # is likely just re-exports.
        return not self.classes and not self.functions and self.line_count < 20

    def structural_summary(self, root: Path) -> str:
        """Return a compact structural summary (no source code).

        Args:
            root: The codebase root, used for relative path display.
        """
        rel = (
            self.path.relative_to(root) if self.path.is_relative_to(root) else self.path
        )
        lines: list[str] = [f"── {rel}  [{self.category}] ({self.line_count} lines)"]

        if self.docstring:
            first_line = self.docstring.strip().split("\n")[0]
            lines.append(f"   {first_line}")

        for cls in self.classes:
            methods = ", ".join(m.name for m in cls.methods)
            bases = f"({', '.join(cls.bases)})" if cls.bases else ""
            lines.append(f"   class {cls.name}{bases} [{methods}]")

        for func in self.functions:
            prefix = "async " if func.is_async else ""
            ret = f" -> {func.return_annotation}" if func.return_annotation else ""
            args = ", ".join(func.args[:4])
            if len(func.args) > 4:
                args += ", ..."
            lines.append(f"   {prefix}def {func.name}({args}){ret}")

        for const in self.constants[:5]:
            lines.append(f"   {const}")
        if len(self.constants) > 5:
            lines.append(f"   ... and {len(self.constants) - 5} more constants")

        return "\n".join(lines)


@dataclass
class CodebaseContext:
    """Aggregated context for a codebase or subset of files."""

    root: Path
    modules: dict[Path, ModuleInfo] = field(default_factory=dict)

    @property
    def file_count(self) -> int:
        """Return the number of indexed modules."""
        return len(self.modules)

    @property
    def total_lines(self) -> int:
        """Return the total line count across all modules."""
        return sum(m.line_count for m in self.modules.values())

    @property
    def total_tokens(self) -> int:
        """Return the estimated total token count for all source."""
        return sum(m.token_estimate for m in self.modules.values())

    @property
    def source_modules(self) -> dict[Path, ModuleInfo]:
        """Return only non-test, non-migration, non-trivial-init modules."""
        return {
            p: m for p, m in self.modules.items() if m.category == FileCategory.SOURCE
        }

    @property
    def test_modules(self) -> dict[Path, ModuleInfo]:
        """Return only test modules."""
        return {
            p: m for p, m in self.modules.items() if m.category == FileCategory.TEST
        }

    def get_module(self, path: Path) -> ModuleInfo | None:
        """Retrieve module info by path, relative or absolute."""
        if path in self.modules:
            return self.modules[path]
        # Try resolving relative to root.
        resolved = (self.root / path).resolve()
        for module_path, info in self.modules.items():
            if module_path.resolve() == resolved:
                return info
        return None

    def summary(self) -> str:
        """Return a concise structural summary suitable for LLM context."""
        lines: list[str] = [
            f"Codebase: {self.root}",
            f"  {self.file_count} files, ~{self.total_lines} lines, "
            f"~{self.total_tokens} tokens\n",
        ]
        for _path, module in sorted(self.modules.items()):
            lines.append(module.structural_summary(self.root))
        return "\n".join(lines)

    def import_graph(self) -> dict[str, set[str]]:
        """Build a mapping of module name → set of imported module names.

        Useful for determining which modules are central (imported by many)
        and which are peripheral.
        """
        graph: dict[str, set[str]] = {}
        for _path, module in self.modules.items():
            module_name = module.path.stem
            deps: set[str] = set()
            for imp in module.imports:
                # Extract the top-level module name from import statements.
                if imp.startswith("from "):
                    parts = imp.split()
                    if len(parts) >= 2:
                        deps.add(parts[1].split(".")[0])
                elif imp.startswith("import "):
                    deps.add(imp.split()[1].split(".")[0])
            graph[module_name] = deps
        return graph


# ───────────────────────────────────────────────────────────────────────────
# File discovery and parsing
# ───────────────────────────────────────────────────────────────────────────


def discover_python_files(root: Path) -> list[Path]:
    """Recursively discover Python files under *root*, skipping ignored dirs.

    Args:
        root: The directory to search.

    Returns:
        A sorted list of ``.py`` file paths.
    """
    if root.is_file() and root.suffix == ".py":
        return [root]

    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in _IGNORE_DIRS for part in path.parts):
            continue
        files.append(path)

    logger.info("Discovered %d Python files under %s", len(files), root)
    return files


def classify_file(path: Path) -> FileCategory:
    """Classify a Python file based on its name and location.

    Args:
        path: Path to the ``.py`` file.

    Returns:
        A ``FileCategory`` indicating the file's role.
    """
    name = path.name
    parts_lower = [p.lower() for p in path.parts]

    if name == "__init__.py":
        return FileCategory.INIT

    if name.startswith("test_") or name.endswith("_test.py"):
        return FileCategory.TEST
    if "tests" in parts_lower or "test" in parts_lower:
        return FileCategory.TEST

    if "migrations" in parts_lower or "alembic" in parts_lower:
        return FileCategory.MIGRATION

    if name in _LOW_PRIORITY_PATTERNS:
        return FileCategory.CONFIG

    # Heuristic: files with "generated" in the name or docstring.
    if "generated" in name.lower() or "auto_generated" in name.lower():
        return FileCategory.GENERATED

    return FileCategory.SOURCE


def parse_module(path: Path) -> ModuleInfo:
    """Parse a single Python file into a ``ModuleInfo`` structure.

    Args:
        path: Path to the ``.py`` file.

    Returns:
        A ``ModuleInfo`` with structural metadata extracted via AST.
    """
    source = path.read_text(encoding="utf-8")
    category = classify_file(path)

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        logger.warning("Syntax error in %s — skipping AST analysis", path)
        return ModuleInfo(
            path=path,
            docstring=None,
            imports=[],
            classes=[],
            functions=[],
            constants=[],
            source=source,
            category=category,
        )

    docstring = ast.get_docstring(tree)
    imports = _extract_imports(tree)
    classes = [
        _parse_class(node)
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.ClassDef)
    ]
    functions = [
        _parse_function(node)
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    constants = _extract_constants(tree)

    # Override category if the docstring signals generated code.
    if docstring and "auto-generated" in docstring.lower():
        category = FileCategory.GENERATED

    return ModuleInfo(
        path=path,
        docstring=docstring,
        imports=imports,
        classes=classes,
        functions=functions,
        constants=constants,
        source=source,
        category=category,
    )


def build_context(root: Path) -> CodebaseContext:
    """Discover and parse all Python files under *root*.

    Args:
        root: The project root directory (or a single file).

    Returns:
        A ``CodebaseContext`` containing parsed module info for every file.
    """
    ctx = CodebaseContext(root=root if root.is_dir() else root.parent)
    files = discover_python_files(root)

    for path in files:
        try:
            ctx.modules[path] = parse_module(path)
        except Exception:
            logger.exception("Failed to parse %s", path)

    logger.info(
        "Built context: %d modules, ~%d lines, ~%d tokens from %s",
        ctx.file_count,
        ctx.total_lines,
        ctx.total_tokens,
        root,
    )
    return ctx


# ───────────────────────────────────────────────────────────────────────────
# Context assembly — the smart part
# ───────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScoredModule:
    """A module with a computed priority score for context inclusion."""

    module: ModuleInfo
    score: float
    reasons: list[str]


def score_modules(
    context: CodebaseContext,
    *,
    query: str = "",
    include_tests: bool = False,
) -> list[ScoredModule]:
    """Score and rank all modules by relevance for inclusion in a prompt.

    Scoring factors (all additive):
    - **Category bonus**: source files score higher than tests, configs, etc.
    - **Import centrality**: files imported by many others score higher.
    - **Complexity signal**: files with more classes/functions score higher
      (they contain more logic worth reviewing).
    - **Query relevance**: if the user provided a query, files whose names,
      docstrings, or class/function names match query terms score higher.
    - **Size penalty**: extremely large files get a slight penalty to favor
      files that fit in budget.
    - **Empty init penalty**: trivial ``__init__.py`` files are deprioritized.

    Args:
        context: The full codebase context.
        query: Optional user query or instructions to bias relevance.
        include_tests: Whether to include test files in scoring.

    Returns:
        A list of ``ScoredModule`` objects, sorted by descending score.
    """
    import_graph = context.import_graph()

    # Count how many modules import each module (reverse dependency count).
    import_counts: dict[str, int] = {}
    for _module_name, deps in import_graph.items():
        for dep in deps:
            import_counts[dep] = import_counts.get(dep, 0) + 1

    query_terms = _tokenize_query(query) if query else []

    scored: list[ScoredModule] = []
    for _path, module in context.modules.items():
        if module.category == FileCategory.TEST and not include_tests:
            continue
        if module.category == FileCategory.MIGRATION:
            continue
        if module.category == FileCategory.GENERATED:
            continue

        score = 0.0
        reasons: list[str] = []

        # Category bonus.
        match module.category:
            case FileCategory.SOURCE:
                score += 10.0
                reasons.append("source file")
            case FileCategory.CONFIG:
                score += 5.0
                reasons.append("config file")
            case FileCategory.TEST:
                score += 3.0
                reasons.append("test file")
            case FileCategory.INIT:
                if module.is_empty_init:
                    score += 0.5
                    reasons.append("trivial __init__")
                else:
                    score += 4.0
                    reasons.append("non-trivial __init__")

        # Import centrality — how many other modules depend on this one.
        module_name = module.path.stem
        dependents = import_counts.get(module_name, 0)
        if dependents > 0:
            centrality_bonus = min(dependents * 2.0, 10.0)
            score += centrality_bonus
            reasons.append(f"imported by {dependents} modules")

        # Complexity signal.
        num_definitions = len(module.classes) + len(module.functions)
        if num_definitions > 0:
            complexity_bonus = min(num_definitions * 0.5, 5.0)
            score += complexity_bonus
            reasons.append(f"{num_definitions} definitions")

        # Query relevance.
        if query_terms:
            relevance = _query_relevance(module, query_terms, context.root)
            if relevance > 0:
                score += relevance
                reasons.append(f"query match (+{relevance:.1f})")

        # Size penalty for very large files (>500 lines).
        if module.line_count > 500:
            penalty = min((module.line_count - 500) / 500, 3.0)
            score -= penalty
            reasons.append(f"size penalty (-{penalty:.1f})")

        scored.append(ScoredModule(module=module, score=score, reasons=reasons))

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


def assemble_context(
    context: CodebaseContext,
    *,
    query: str = "",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    include_tests: bool = False,
) -> str:
    """Assemble an LLM-ready context string within a token budget.

    Uses a priority-based packing strategy:

    1. Always include the structural summary (capped at ``_SUMMARY_TOKEN_BUDGET``).
    2. Score and rank all modules.
    3. Pack full source for the highest-priority modules until the budget is
       spent.
    4. Remaining modules get structural summaries only (already included in
       step 1).

    Args:
        context: The full codebase context.
        query: Optional query to bias file selection.
        token_budget: Maximum approximate tokens for the assembled context.
        include_tests: Whether to include test files.

    Returns:
        A formatted string containing the structural summary followed by
        full source for the highest-priority files.
    """
    # Step 1: Structural summary.
    summary = context.summary()
    summary_tokens = len(summary) // _CHARS_PER_TOKEN
    if summary_tokens > _SUMMARY_TOKEN_BUDGET:
        # Truncate the summary if the codebase is enormous.
        max_chars = _SUMMARY_TOKEN_BUDGET * _CHARS_PER_TOKEN
        summary = summary[:max_chars] + "\n... (summary truncated)"
        summary_tokens = _SUMMARY_TOKEN_BUDGET

    remaining_budget = token_budget - summary_tokens

    # Step 2: Score and rank.
    scored = score_modules(context, query=query, include_tests=include_tests)

    # Step 3: Pack full source for top-priority modules.
    full_source_sections: list[str] = []
    included_files: list[str] = []

    for scored_module in scored:
        module = scored_module.module
        source_tokens = module.token_estimate

        if source_tokens > remaining_budget:
            # If the file is too big for the remaining budget but we haven't
            # included anything yet, try to include a truncated version.
            if not full_source_sections and remaining_budget > 500:
                max_chars = remaining_budget * _CHARS_PER_TOKEN
                truncated = module.source[:max_chars]
                rel = (
                    module.path.relative_to(context.root)
                    if module.path.is_relative_to(context.root)
                    else module.path
                )
                full_source_sections.append(
                    f"# ── {rel} (truncated, {module.line_count} lines total) ──\n"
                    f"{truncated}\n# ... truncated ..."
                )
                included_files.append(str(rel))
                remaining_budget = 0
            continue

        rel = (
            module.path.relative_to(context.root)
            if module.path.is_relative_to(context.root)
            else module.path
        )
        full_source_sections.append(
            f"# ── {rel} ({module.line_count} lines) ──\n{module.source}"
        )
        included_files.append(str(rel))
        remaining_budget -= source_tokens

        if remaining_budget <= 0:
            break

    # Step 4: Assemble.
    parts: list[str] = [
        "## Codebase Structure\n",
        summary,
    ]

    if full_source_sections:
        parts.append(f"\n\n## Full Source ({len(included_files)} files)\n")
        parts.extend(full_source_sections)

    skipped = context.file_count - len(included_files)
    if skipped > 0:
        parts.append(
            f"\n\n({skipped} additional files included in structural summary above)"
        )

    assembled = "\n\n".join(parts)
    assembled_tokens = len(assembled) // _CHARS_PER_TOKEN

    logger.info(
        "Assembled context: %d/%d files with full source, ~%d tokens (budget: %d)",
        len(included_files),
        context.file_count,
        assembled_tokens,
        token_budget,
    )
    return assembled


def assemble_single_file(
    context: CodebaseContext,
    target: Path,
) -> str:
    """Assemble context for a single-file operation.

    Includes the target file's full source plus structural summaries of
    related files (those that import or are imported by the target).

    Args:
        context: The full codebase context.
        target: Path to the target file.

    Returns:
        A formatted context string.
    """
    module = context.get_module(target)
    if module is None:
        raise FileNotFoundError(f"Module not found in context: {target}")

    rel = (
        target.relative_to(context.root)
        if target.is_relative_to(context.root)
        else target
    )

    parts: list[str] = [
        f"## Target File: {rel}\n",
        f"```python\n{module.source}\n```",
    ]

    # Find related modules (files that import this one or are imported by it).
    import_graph = context.import_graph()
    target_name = target.stem
    target_deps = import_graph.get(target_name, set())

    # Modules that this file imports.
    related: list[str] = []
    for dep in target_deps:
        for _path, mod in context.modules.items():
            if mod.path.stem == dep:
                related.append(mod.structural_summary(context.root))
                break

    # Modules that import this file.
    for mod_name, deps in import_graph.items():
        if target_name in deps and mod_name != target_name:
            for _path, mod in context.modules.items():
                if mod.path.stem == mod_name:
                    related.append(mod.structural_summary(context.root))
                    break

    if related:
        parts.append("\n## Related Modules\n")
        parts.append("\n".join(related))

    return "\n\n".join(parts)

def batch_files(
    context: CodebaseContext,
    *,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    include_tests: bool = False,
) -> list[list[ModuleInfo]]:
    """Group all refactorable modules into token-budget-constrained batches.

    Unlike ``assemble_context``, this function includes **all** source files
    rather than only the highest-priority subset.  Files are sorted by score
    (highest first) so the most important modules appear in early batches.

    Each batch contains files whose combined token estimate fits within
    ``token_budget``.  A file that exceeds the budget on its own is placed in
    a batch by itself.

    Args:
        context: The full codebase context.
        token_budget: Maximum approximate tokens per batch.
        include_tests: Whether to include test files in the batches.

    Returns:
        A list of batches, each batch being a list of ``ModuleInfo`` objects.
        Returns an empty list if there are no refactorable files.
    """
    scored = score_modules(context, include_tests=include_tests)

    batches: list[list[ModuleInfo]] = []
    current_batch: list[ModuleInfo] = []
    current_tokens = 0

    for scored_module in scored:
        module = scored_module.module
        module_tokens = module.token_estimate

        # Files larger than the budget get their own batch.
        if module_tokens > token_budget:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            batches.append([module])
            continue

        # Start a new batch if adding this file would overflow the current one.
        if current_tokens + module_tokens > token_budget and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(module)
        current_tokens += module_tokens

    if current_batch:
        batches.append(current_batch)

    logger.info(
        "Batched %d modules into %d batches (budget: %d tokens/batch)",
        sum(len(b) for b in batches),
        len(batches),
        token_budget,
    )
    return batches


# ───────────────────────────────────────────────────────────────────────────
# Private helpers
# ───────────────────────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-z_][a-z0-9_]*", re.IGNORECASE)


def _extract_imports(tree: ast.Module) -> list[str]:
    """Extract import statements as strings."""
    imports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(a.name for a in node.names)
            imports.append(f"from {module} import {names}")
    return imports


def _parse_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
    """Extract function metadata from an AST node."""
    args = [a.arg for a in node.args.args if a.arg != "self"]
    return_ann = ast.unparse(node.returns) if node.returns else None

    return FunctionInfo(
        name=node.name,
        lineno=node.lineno,
        end_lineno=node.end_lineno,
        args=args,
        return_annotation=return_ann,
        docstring=ast.get_docstring(node),
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )


def _parse_class(node: ast.ClassDef) -> ClassInfo:
    """Extract class metadata from an AST node."""
    bases = [ast.unparse(b) for b in node.bases]
    methods = [
        _parse_function(n)
        for n in node.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    return ClassInfo(
        name=node.name,
        lineno=node.lineno,
        end_lineno=node.end_lineno,
        bases=bases,
        docstring=ast.get_docstring(node),
        methods=methods,
    )


def _extract_constants(tree: ast.Module) -> list[str]:
    """Extract module-level UPPER_CASE assignments as constant names."""
    constants: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
    return constants


def _tokenize_query(query: str) -> list[str]:
    """Extract lowercase keyword tokens from a query string."""
    stopwords = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "my",
        "your",
        "his",
        "her",
        "our",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "when",
        "where",
        "why",
        "and",
        "or",
        "but",
        "not",
        "no",
        "if",
        "then",
        "than",
        "so",
        "for",
        "with",
        "from",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "review",
        "refactor",
        "explain",
        "check",
        "fix",
        "code",
        "file",
    }
    words = _WORD_RE.findall(query.lower())
    return [w for w in words if w not in stopwords]


def _query_relevance(module: ModuleInfo, terms: list[str], root: Path) -> float:
    """Score a module's relevance to a set of query terms.

    Matches against filename, docstring, class names, and function names.
    """
    score = 0.0
    rel_path = str(
        module.path.relative_to(root)
        if module.path.is_relative_to(root)
        else module.path
    ).lower()

    for term in terms:
        # Filename match (strongest signal).
        if term in rel_path:
            score += 5.0

        # Docstring match.
        if module.docstring and term in module.docstring.lower():
            score += 2.0

        # Class name match.
        for cls in module.classes:
            if term in cls.name.lower():
                score += 3.0
            for method in cls.methods:
                if term in method.name.lower():
                    score += 1.5

        # Function name match.
        for func in module.functions:
            if term in func.name.lower():
                score += 2.0

    return score
