"""Persist and seed known-good NL to SQL examples for the Vanna agent."""

from __future__ import annotations

import json

from vanna_setup import MEMORY_STORE_PATH, ensure_memory_store


def seed_memory() -> int:
    """
    Persist the seed examples to disk and warm the in-process DemoAgentMemory.

    DemoAgentMemory is process-local, so the persistent JSON store is used to
    rehydrate examples on API startup.
    """
    seed_examples = ensure_memory_store()

    try:
        from vanna.integrations.local.agent_memory import DemoAgentMemory

        agent_memory = DemoAgentMemory(max_items=1000)
        for item in seed_examples:
            train = getattr(agent_memory, "train", None)
            if callable(train):
                train(question=item["question"], sql=item["sql"])
    except Exception:
        # The persistent store is the source of truth, so warm-up failures are non-fatal.
        pass

    MEMORY_STORE_PATH.write_text(json.dumps(seed_examples, indent=2), encoding="utf-8")
    return len(seed_examples)


def main() -> None:
    count = seed_memory()
    print(f"Seeded {count} NL-to-SQL examples into persistent memory store: {MEMORY_STORE_PATH.resolve()}")


if __name__ == "__main__":
    main()
