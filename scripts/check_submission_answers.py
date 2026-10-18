"""Character count for the five IBM Z Datathon submission form answers.

Reads docs/submission/SUBMISSION_FORM_ANSWERS.md, splits it on the '## ' form
headings, and prints the character count of each answer body against the
1024-character limit enforced by the submission form.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LIMIT = 1024
DOC = Path(__file__).resolve().parents[1] / "docs" / "submission" / "SUBMISSION_FORM_ANSWERS.md"


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    # Answers start at each numbered form heading.
    sections = re.split(r"^## \d+\. ", text, flags=re.MULTILINE)[1:]
    worst = 0
    for raw in sections:
        title, _, body = raw.partition("\n")
        body = body.split("\n---", 1)[0].strip().strip("-").strip()
        count = len(body)
        worst = max(worst, count)
        flag = "OK  " if count <= LIMIT else "OVER"
        print(f"{flag} {count:5d}/{LIMIT}  {title}")
    print(f"\nmax={worst}  limit={LIMIT}  margin={LIMIT - worst}")
    return 0 if worst <= LIMIT else 1


if __name__ == "__main__":
    sys.exit(main())
