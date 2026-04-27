"""Entry point — accepts user input from terminal and prints agent output as JSON."""

import json
from agent.agent import run


def main() -> None:
    print("Agent ready. Type 'exit' to quit.\n")

    while True:
        try:
            instruction = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if instruction.lower() in {"exit", "quit"}:
            print("Exiting.")
            break

        result = run(instruction)
        print(json.dumps(result, indent=2))
        print()


if __name__ == "__main__":
    main()
