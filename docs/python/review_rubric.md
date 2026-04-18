# Review Rubric

This document defines the scoring criteria, severity levels, and prioritization
framework the agent uses when reviewing Python code. It ensures reviews are
consistent, actionable, and focused on what matters most.

---

## 1. Severity Levels

Every finding is assigned a severity level. These levels determine priority and
whether the finding blocks approval.

### Critical

**Definition:** Bugs, security vulnerabilities, data loss risks, or correctness
issues that will cause failures in production.

**Examples:**
- SQL injection via string interpolation
- Hardcoded secrets (API keys, passwords, tokens)
- Race conditions in shared mutable state
- Unhandled exceptions that crash the application
- Mutable default arguments causing shared state bugs
- Incorrect logic that produces wrong results

**Action:** Must be fixed before merge. No exceptions.

---

### Major

**Definition:** Significant design or maintainability issues that will cause
problems at scale, impede future development, or violate core standards.

**Examples:**
- Missing type annotations on public functions
- God classes or God modules (>400 lines, multiple responsibilities)
- Dictionary-driven development (passing `dict[str, Any]` as domain data)
- Bare `except:` or `except Exception:` without re-raise
- Sync I/O inside async functions
- Missing error handling on I/O operations
- Circular imports
- No logging (print-driven development)

**Action:** Should be fixed before merge. Exceptions require explicit
justification and a follow-up ticket.

---

### Minor

**Definition:** Style issues, non-idiomatic code, or minor deviations from
standards that do not affect correctness or significantly impact
maintainability.

**Examples:**
- Legacy type syntax (`Optional[X]` instead of `X | None`)
- `os.path` instead of `pathlib`
- `str.format()` instead of f-strings
- Missing trailing commas on multi-line structures
- Commented-out code
- Overly generic variable names (`data`, `result`, `temp`)
- Magic numbers in non-critical paths

**Action:** Should be fixed, but should not block merge. Can be batched
into a cleanup pass.

---

### Suggestion

**Definition:** Recommendations for improved design, performance, or
readability that go beyond the minimum standard. These are opinions, not
requirements.

**Examples:**
- "Consider extracting this into a separate module for testability."
- "A generator expression would avoid building the full list in memory."
- "This could benefit from the Strategy pattern for extensibility."
- "Consider using `functools.cache` here for repeated calls."

**Action:** At the author's discretion. No obligation to implement.

---

## 2. Review Dimensions

Each review evaluates code across the following dimensions. Not every dimension
applies to every review — the agent focuses on what is relevant.

### 2.1 Correctness

- Does the code do what it claims to do?
- Are edge cases handled?
- Are error conditions addressed?
- Are invariants maintained?

### 2.2 Type Safety

- Are all public function signatures fully annotated?
- Are types specific (not `Any` without justification)?
- Does the code use modern type syntax?
- Would `ty` pass without errors?

### 2.3 Security

- Are inputs validated before use?
- Are secrets externalized (not in source code)?
- Are SQL queries parameterized?
- Are file paths sanitized?
- Are permissions appropriate?

### 2.4 Design

- Does each module/class have a single responsibility?
- Are dependencies injected rather than hardcoded?
- Is the code testable in isolation?
- Is inheritance depth reasonable (≤2 levels)?
- Are abstractions at the right level?

### 2.5 Pythonic Idiom

- Does the code use language features appropriately (comprehensions, generators,
  context managers, unpacking)?
- Does it follow PEP 8 naming conventions?
- Does it use the standard library where applicable (`itertools`, `functools`,
  `collections`, `pathlib`)?
- Does it avoid reinventing existing tools?

### 2.6 Error Handling

- Are exceptions specific (not bare `except`)?
- Are custom exceptions used for domain errors?
- Do error messages include enough context to diagnose the problem?
- Are resources cleaned up in `finally` blocks or context managers?

### 2.7 Documentation

- Do public functions and classes have docstrings?
- Do docstrings describe *what* and *why*, not *how*?
- Are complex algorithms or non-obvious decisions explained?
- Is the module's purpose clear from its docstring?

### 2.8 Performance

- Are there obvious O(n²) operations on large collections?
- Are database queries inside loops (N+1 problem)?
- Are large data structures built when a generator would suffice?
- Is there sync I/O in an async context?

**Note:** The agent flags performance issues only when they are *obvious* or
*likely to matter at expected scale*. Premature optimization concerns are
suggestions, not findings.

---

## 3. Review Output Format

The agent structures its review output as follows:

### 3.1 Summary

A brief (2–3 sentence) assessment of the overall code quality and the most
important finding.

### 3.2 Findings

Each finding includes:

- **Severity:** Critical | Major | Minor | Suggestion
- **Location:** File and line range (or function/class name)
- **Pattern:** Named anti-pattern or violated standard (referencing the
  relevant doc)
- **Description:** What the issue is and why it matters
- **Recommendation:** Concrete fix, with a code example when helpful

### 3.3 Positive Observations

If the code does something particularly well — clean abstractions, good use
of language features, thorough error handling — the review notes it. Good
practices should be reinforced, not just bad practices flagged.

---

## 4. Prioritization Framework

When a review produces many findings, the agent prioritizes output as follows:

1. **Critical findings first.** Always.
2. **Major findings grouped by dimension** (correctness before style).
3. **Minor findings summarized** — not itemized individually unless the list
   is short. "There are 12 instances of legacy type syntax; run
   `ruff check --select UP --fix` to auto-migrate."
4. **Suggestions last**, and only the most impactful 2–3. Do not overwhelm
   the author with a list of 15 "nice-to-have" changes.

---

## 5. Review Principles

### 5.1 Be Specific

"This could be improved" is not a finding. Every finding must say *what* is
wrong, *why* it matters, and *what to do instead*.

### 5.2 Be Proportional

A 20-line utility script does not need the same scrutiny as a core service
module. Scale the review's depth and tone to the code's impact and context.

### 5.3 Assume Good Intent

The author made their choices for reasons. The review should address the code,
not the author. "This function mixes I/O and business logic" is good.
"The author clearly doesn't understand separation of concerns" is not.

### 5.4 Teach, Don't Just Flag

When flagging a pattern, briefly explain the principle behind the standard.
Link to the relevant doc section. The goal is to transfer knowledge, not just
enforce rules.

### 5.5 Distinguish Fact from Preference

Standards from the docs are enforceable. Personal preferences that go beyond
the documented standards are labeled as suggestions and marked accordingly.
The agent does not smuggle opinions in as requirements.
