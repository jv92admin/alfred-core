"""Quickstart runner — minimal multi-turn conversation loop.

Usage:
    python scripts/runner.py

Requires:
    - .env file with OPENAI_API_KEY and domain-specific vars
    - Domain package installed (pip install -e .)
    - alfredagain >= 2.1.0 installed

Tip: Set ALFRED_USE_ADVANCED_MODELS=false in .env for cheaper dev runs.
     Set ALFRED_LOG_PROMPTS=1 to log all LLM prompts to prompt_logs/.
"""

import asyncio

# --- Domain registration ---
# This import triggers _register() in your domain's __init__.py,
# which calls register_domain() with your DomainConfig singleton.
# Without this import, core has no domain and will fail.
import alfred_DOMAIN  # noqa: F401  # TODO: rename to your package

from alfred.graph.workflow import run_alfred
from alfred.memory import initialize_conversation


async def main():
    # Create empty conversation context.
    # This dict carries entity refs, turn history, and reasoning summaries
    # across turns. Pass it back into run_alfred() for multi-turn coherence.
    conversation = initialize_conversation()

    # TODO: replace with a real user ID from your auth system.
    # For dev, any string works — it scopes DB queries via user_owned_tables.
    user_id = "dev-user-123"

    print("Alfred is ready. Type 'quit' to exit.\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input.strip():
            continue

        try:
            response, conversation = await run_alfred(
                user_message=user_input,
                user_id=user_id,
                conversation=conversation,  # Pass back for multi-turn
            )
            print(f"\nAlfred: {response}\n")
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
