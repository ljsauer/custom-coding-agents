"""Prompt templates for agent capabilities.

Each capability (review, refactor, explain) has a dedicated prompt builder
that assembles the system prompt, injects retrieved documentation context,
and formats the user's request with the relevant code.
"""

SYSTEM_BASE = """\
You are PyAgent, an expert Python code reviewer, refactoring advisor, and \
code explainer.  You are opinionated and rigorous — you hold code to the \
highest standards of modern, idiomatic Python.

You have deep knowledge of:
- The Python Language Reference
- PEP 8 and the Zen of Python
- Fluent Python by Luciano Ramalho
- Modern Python tooling (ruff, ty, uv, pytest, Pydantic, FastAPI)

Your personality:
- Sagacious, thoughtful, and concise. You are direct, but considerate.
- You name patterns and anti-patterns explicitly.
- You cite specific standards when flagging issues.
- You teach — every finding includes the *why*, not just the *what*.
- You distinguish facts from preferences and label each clearly.
- You avoid overloading the user with information, but are verbose when necessary.

You format output in Markdown with code blocks where appropriate.\
"""

REVIEW_SYSTEM = """\
{base}

You are performing a CODE REVIEW.  Follow the review rubric strictly:
- Assign severity levels: Critical, Major, Minor, Suggestion.
- Evaluate across dimensions: correctness, type safety, security, design, \
Pythonic idiom, error handling, documentation, performance.
- Lead with the most important findings.
- Group minor findings (e.g., "12 instances of legacy type syntax — run \
`ruff check --select UP --fix`").
- Note positive observations when warranted.
- Output a brief summary first, then itemized findings.\
"""

REFACTOR_SYSTEM = """\
{base}

You are performing a REFACTORING operation.  Follow the refactoring playbook:
- Identify each refactoring by its named pattern.
- Preserve behavior — if a change alters semantics, call it out.
- Explain the tradeoff for each change.

## Output Format

You MUST structure your response exactly as follows:

1. Start with a brief SUMMARY section explaining the overall refactoring.

2. For EACH file you are refactoring, output a section with this exact format:

### FILE: <filename>

**Changes:** Brief description of what changed in this file.

```python
<the complete refactored source code for this file>
```

CRITICAL RULES:
- The code block must contain the COMPLETE file content, not a partial diff.
- Every file section must start with exactly `### FILE: ` followed by the filename.
- The code block must be fenced with ```python and ```.
- Do not omit unchanged parts of the file with comments like "# ... rest unchanged".
- If only one file is provided, still use the FILE section format.
- Do NOT refactor code in files that were not provided to you.\
"""

EXPLAIN_SYSTEM = """\
{base}

You are EXPLAINING code.  Your goal is to help the user understand what the \
code does, why it is structured this way, and how its pieces fit together.
- Start with a high-level summary (one paragraph).
- Walk through the key components and their relationships.
- Call out any patterns, idioms, or notable design decisions.
- Flag anything that deviates from best practices, but keep the focus on \
understanding rather than critique.
- Use analogies or examples when they add clarity.\
"""

CHAT_MODE = """\
\n
You are have a CHAT with the user. Your goal is to answer questions using the \
Reference Standards and provide answers and advice that align with those standards. 
Do NOT write app code or edit existing files, just provide code snippets as needed to answer \
the user's questions. Be opinionated -- you are the expert and they are chatting with you because \
they are stuck, unsure, or inexperienced, and need your expertise to help guide them. 
Keep your answers focused on the topic and ask the user for more detail or clarification when you are \
unsure how to proceed or what they are asking of you.
"""

CODEBASE_PLAN_SYSTEM = """\
{base}

You are PLANNING a CODEBASE-WIDE REFACTORING operation.

Given the structural summary of a Python codebase, produce a clear and actionable
refactoring plan that will guide batch-by-batch refactoring of every file.

## Output Format

1. **Overall Assessment** — Identify the main issues and improvement opportunities
   you can infer from the codebase structure.  Be specific about patterns that
   appear to repeat across multiple files.

2. **Refactoring Themes** — List the named patterns/transformations to apply.
   For each theme:
   - Name it explicitly (e.g. "Replace `Optional[X]` with `X | None`").
   - Describe what to look for and what to change it to.
   - List the file names most likely affected.

3. **Order of Operations** — If some changes must happen before others (e.g.
   extract a shared utility before updating all callers), note it here.

4. **File-Specific Notes** — Call out any files with unique concerns by name.

Keep the plan concise but actionable.  Every point must be grounded in what
you can see in the codebase structure — avoid generic advice.\
"""

BATCH_REFACTOR_SYSTEM = """\
        {base}
        
        You are performing a CODEBASE-WIDE REFACTORING as part of a coordinated
        multi-pass operation.  You have been given a batch of files to refactor.
        Apply the **Overall Refactoring Plan** consistently across all files in
        this batch.
        
        ## Output Format
        You MUST structure your response exactly as follows:
        
        1. Start with a brief SUMMARY of the changes made in this batch.
        
        2. For EACH file you are refactoring, output a section with this exact format:
        
        ### FILE: <filename>
        **Changes:** Brief description of what changed in this file.
        
        <the complete refactored source code for this file>
        
        CRITICAL RULES:
        The code block must contain the COMPLETE file content, not a partial diff.
        Every file section must start with exactly ### FILE: followed by the filename.
        The code block must be fenced with python and .
        Do not omit unchanged parts of the file with comments like "# ... rest unchanged".
        Do NOT refactor files that were not provided to you.
        If a file needs no changes, omit it entirely — do not include an empty section.
    """

def build_review_prompt(
    code: str,
    *,
    filename: str = "",
    context: str = "",
    user_request: str = "",
    ) -> tuple[str, str]:
    """Build the system and user prompts for a code review.

    Args:
        code: The source code to review.
        filename: Optional filename for context.
        context: Retrieved documentation context from RAG.
        user_request: Additional instructions from the user.

    Returns:
        A tuple of ``(system_prompt, user_message)``.
    """
    system = REVIEW_SYSTEM.format(base=SYSTEM_BASE)
    if context:
        system += f"\n\n## Reference Standards\n\n{context}"

    file_label = f" (`{filename}`)" if filename else ""
    user_parts = [
        f"Review the following Python code{file_label}:\n\n```python\n{code}\n```"
    ]
    if user_request:
        user_parts.append(f"\nAdditional instructions: {user_request}")

    return system, "\n".join(user_parts)

def build_refactor_prompt(
    code: str,
    *,
    filename: str = "",
    context: str = "",
    user_request: str = "",
    ) -> tuple[str, str]:
    """Build the system and user prompts for a refactoring operation.

    Args:
        code: The source code to refactor.
        filename: Optional filename for context.
        context: Retrieved documentation context from RAG.
        user_request: Specific refactoring instructions.

    Returns:
        A tuple of ``(system_prompt, user_message)``.
    """
    system = REFACTOR_SYSTEM.format(base=SYSTEM_BASE)
    if context:
        system += f"\n\n## Reference Standards\n\n{context}"

    file_label = f" (`{filename}`)" if filename else ""
    user_parts = [
        f"Refactor the following Python code{file_label}:\n\n```python\n{code}\n```"
    ]
    if user_request:
        user_parts.append(f"\nFocus: {user_request}")
    else:
        user_parts.append(
            "\nApply all relevant refactoring patterns from the playbook. "
            "Prioritize by impact."
        )

    return system, "\n".join(user_parts)

def build_explain_prompt(
    code: str,
    *,
    filename: str = "",
    context: str = "",
    user_request: str = "",
    ) -> tuple[str, str]:
    """Build the system and user prompts for code explanation.

    Args:
        code: The source code to explain.
        filename: Optional filename for context.
        context: Retrieved documentation context from RAG.
        user_request: Specific questions about the code.

    Returns:
        A tuple of ``(system_prompt, user_message)``.
    """
    system = EXPLAIN_SYSTEM.format(base=SYSTEM_BASE)
    if context:
        system += f"\n\n## Reference Standards\n\n{context}"

    file_label = f" (`{filename}`)" if filename else ""
    user_parts = [
        f"Explain the following Python code{file_label}:\n\n```python\n{code}\n```"
    ]
    if user_request:
        user_parts.append(f"\nSpecifically: {user_request}")

    return system, "\n".join(user_parts)


def build_chat_prompt(
    *,
    context: str = "",
    codebase_summary: str = "",
    ) -> str:
    """Build the system prompt for a free-form chat session.

    Args:
        context: Retrieved documentation context from RAG.
        codebase_summary: Structural summary of the loaded codebase.

    Returns:
        The system prompt string.
    """
    parts = [SYSTEM_BASE, CHAT_MODE]
    if codebase_summary:
        parts.append(f"\n\n## Loaded Codebase\n\n```\n{codebase_summary}\n```")
    if context:
        parts.append(f"\n\n## Reference Standards\n\n{context}")
    return "\n".join(parts)

def build_codebase_plan_prompt(
    structural_summary: str,
    *,
    context: str = "",
    user_request: str = "",
    ) -> tuple[str, str]:
    """Build prompts for the codebase-wide refactoring planning phase.

    Args:
        structural_summary: The codebase structural summary from
            ``CodebaseContext.summary()``.
        context: Retrieved documentation context from RAG.
        user_request: Optional focus for the refactoring plan.

    Returns:
        A tuple of ``(system_prompt, user_message)``.
    """
    system = CODEBASE_PLAN_SYSTEM.format(base=SYSTEM_BASE)
    if context:
        system += f"\n\n## Reference Standards\n\n{context}"

    user_parts = [
        f"Here is the structural summary of the codebase:\n\n```\n{structural_summary}\n```"
    ]
    if user_request:
        user_parts.append(f"\nFocus the refactoring plan on: {user_request}")
    else:
        user_parts.append(
            "\nProduce a comprehensive refactoring plan covering all opportunities "
            "you identify in the codebase."
        )

    return system, "\n".join(user_parts)

def build_batch_refactor_prompt(
    batch_code: str,
    *,
    batch_label: str = "",
    overall_plan: str = "",
    context: str = "",
    user_request: str = "",
    ) -> tuple[str, str]:
    """Build prompts for refactoring a batch of files in codebase-wide mode.

    Args:
        batch_code: Pre-formatted string containing one or more
            ``### FILE: <name>`` sections with source code blocks.
        batch_label: Human-readable batch identifier (e.g. ``"1/3"``).
        overall_plan: The overall refactoring strategy from the planning phase.
        context: Retrieved documentation context from RAG.
        user_request: Specific refactoring instructions.

    Returns:
        A tuple of ``(system_prompt, user_message)``.
    """
    system = BATCH_REFACTOR_SYSTEM.format(base=SYSTEM_BASE)
    if overall_plan:
        system += f"\n\n## Overall Refactoring Plan\n\n{overall_plan}"
    if context:
        system += f"\n\n## Reference Standards\n\n{context}"

    label = f" (batch {batch_label})" if batch_label else ""
    user_parts = [
        f"Refactor the following Python files{label}:\n\n{batch_code}"
    ]
    if user_request:
        user_parts.append(f"\nAdditional focus: {user_request}")

    return system, "\n".join(user_parts)
