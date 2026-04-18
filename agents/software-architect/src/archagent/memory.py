import json
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / ".arch_agent" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def new_session(project: str = "default") -> dict:
    return {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "project": project,
        "created": datetime.now().isoformat(),
        "history": [],
        "decisions": [],
    }


def save_session(session: dict) -> None:
    path = SESSIONS_DIR / f"{session['id']}.json"
    path.write_text(json.dumps(session, indent=2))


def load_session(session_id: str) -> dict:
    path = SESSIONS_DIR / f"{session_id}.json"
    return json.loads(path.read_text())


def list_sessions(project: str | None = None) -> list[dict]:
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        data = json.loads(path.read_text())
        if project and data["project"] != project:
            continue
        sessions.append(
            {
                "id": data["id"],
                "project": data["project"],
                "created": data["created"],
                "turns": len(data["history"]) // 2,
            }
        )
    return sessions


def get_project_decisions(project: str) -> list[dict]:
    """Load all logged decisions across sessions for a given project."""
    decisions = []
    for path in SESSIONS_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        if data["project"] == project:
            decisions.extend(data["decisions"])
    return sorted(decisions, key=lambda d: d["timestamp"])


def log_decision(session: dict, decision: str) -> None:
    session["decisions"].append(
        {"timestamp": datetime.now().isoformat(), "decision": decision}
    )


def build_decision_block(decisions: list[dict]) -> str:
    if not decisions:
        return ""
    lines = "\n".join(f"- {d['decision']}" for d in decisions)
    return f"\n\n## Prior Architectural Decisions (this project)\n{lines}"
