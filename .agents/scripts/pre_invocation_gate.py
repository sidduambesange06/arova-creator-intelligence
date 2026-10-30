import json
import sys


def main() -> None:
    _ = sys.stdin.read()
    payload = {
        "injectSteps": [
            {
                "ephemeralMessage": (
                    "[AROVA DEV FACTOR ACTIVE] "
                    "1) Ponytail + ponytail-review active on every change (zero mock data, minimal diff). "
                    "2) Obsidian Main Brain (docs/PROJECT_STATUS.md, DEVELOPMENT_LOG.md, TECHNICAL_DECISIONS.md, KNOWN_ISSUES.md) must stay synced after each feature. "
                    "3) TinyFish connector ready for external benchmark/metadata lookups while keeping video indexing 100% local-first. "
                    "4) Make an atomic git commit after every verified feature."
                )
            }
        ]
    }
    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    main()
