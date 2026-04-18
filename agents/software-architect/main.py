from agent import ArchAgent
from memory import list_sessions


def pick_session() -> tuple[str, str | None]:
    """Ask the user whether to start a new session or resume one."""
    print("\n=== Architecture Agent ===")
    print("Commands: 'new', 'resume', 'list'\n")

    choice = input("Start new session or resume? [new]: ").strip().lower() or "new"

    if choice == "list":
        sessions = list_sessions()
        if not sessions:
            print("No saved sessions.")
        else:
            for s in sessions:
                print(f"  {s['id']} | project={s['project']} | turns={s['turns']}")
        return pick_session()

    if choice == "resume":
        session_id = input("Session ID: ").strip()
        return "default", session_id

    project = input("Project name [default]: ").strip() or "default"
    return project, None


def main():
    project, resume_id = pick_session()
    agent = ArchAgent(project=project, resume_id=resume_id)

    print("\nReady. Special commands:")
    print("  :decide <text>  — log an architectural decision")
    print("  :quit           — save and exit\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSession saved.")
            break

        if not user_input:
            continue

        if user_input.lower() == ":quit":
            print("Session saved.")
            break

        if user_input.startswith(":decide "):
            decision = user_input[len(":decide "):].strip()
            agent.log_decision(decision)
            continue

        response = agent.chat(user_input)
        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    main()
