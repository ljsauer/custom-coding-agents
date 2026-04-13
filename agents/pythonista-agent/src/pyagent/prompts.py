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
- Explain the tradeoff for each change.
- Preserve behavior — if a change alters semantics, call it out.
- Replace the original code with your final refactor recommendations. 
- Provide the user with an overview of the changes (they can see the diff themselves). \
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
