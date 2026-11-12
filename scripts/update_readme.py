#!/usr/bin/env python3
"""Rewrite README's shell catalog from olnm.py's help lines (tests fail when the two differ)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import olnm  # noqa: E402

START, END = "<!-- shell-catalog:start -->\n", "<!-- shell-catalog:end -->"


def catalog() -> str:
    """One `### section` table per section, in file order."""
    blocks = []
    for section in olnm._sections():
        rows = [f"| `{e['name']}` | {(e['emoji'] + ' ' + e['desc']).replace('|', chr(92) + '|')} |"
                for e in olnm.entries() if e["section"] == section]
        blocks.append("\n".join([f"### {section}", "", "| 関数 | 説明 |", "|---|---|", *rows]))
    return "\n\n".join(blocks) + "\n"


def updated(readme: str) -> str:
    head, rest = readme.split(START)
    return head + START + catalog() + END + rest.split(END)[1]


if __name__ == "__main__":
    path = ROOT / "README.md"
    path.write_text(updated(path.read_text()))
