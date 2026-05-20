import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.backfill_normalized_texts import main as backfill_normalized_texts


def main() -> None:
    sys.argv = [sys.argv[0], "--target", "lineup"]
    backfill_normalized_texts()


if __name__ == "__main__":
    main()
