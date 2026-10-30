import json
import sys


def main() -> None:
    _ = sys.stdin.read()
    payload = {
        "injectSteps": [
            {
                "ephemeralMessage": (
                    "[AROVA DEV FACTOR ACTIVE — ARGON BLUEPRINT MODE] "
                    "1) Read docs/FLASH_EXECUTION_PLAYBOOK.md and docs/PROJECT_STATUS.md before writing code; follow exact Argon file paths, signatures, and formulas. "
                    "2) Ponytail + ponytail-review active on every change (zero mock data, minimal diff). "
                    "3) Obsidian Main Brain (docs/PROJECT_STATUS.md, DEVELOPMENT_LOG.md, TECHNICAL_DECISIONS.md, KNOWN_ISSUES.md) must stay synced after each feature. "
                    "4) TinyFish connector ready for external benchmark/metadata lookups while keeping video indexing 100% local-first. "
                    "5) Run pytest/vitest and create an atomic git commit after every verified feature."
                )
            }
        ]
    }
    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    main()
