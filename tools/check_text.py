#!/usr/bin/env python3
"""Fail when repository text contains em/en dashes or banned phrases."""

import argparse
import re
import sys
from pathlib import Path

TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {"LICENSE", ".gitignore", ".gitattributes"}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
BANNED_PHRASES = (
    "comprehensive",
    "seamless",
    "robust",
    "leverage",
    "delve",
    "cutting-edge",
    "state-of-the-art",
    "game-changer",
    "unlock",
    "elevate",
    "effortless",
    "streamline",
    "harness",
    "empower",
    "revolutionize",
    "in today's",
    "it's important to note",
    "furthermore",
    "moreover",
)
BANNED_PATTERN = re.compile(
    r"\b(?:%s)\b" % "|".join(re.escape(phrase) for phrase in BANNED_PHRASES),
    re.IGNORECASE,
)
DASHES = {"\u2013": "en dash", "\u2014": "em dash"}
SELF = Path(__file__).resolve()


def iter_text_files(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() == SELF:
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def check_file(path):
    problems = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return problems
    for number, line in enumerate(text.splitlines(), start=1):
        for character, label in DASHES.items():
            if character in line:
                problems.append((path, number, label))
        for match in BANNED_PATTERN.finditer(line):
            problems.append((path, number, "banned phrase %r" % match.group(0).lower()))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Files or directories to scan (default: repository root)")
    args = parser.parse_args(argv)

    roots = [Path(item) for item in args.paths] or [SELF.parent.parent]
    files = []
    for root in roots:
        if root.is_file():
            files.append(root)
        else:
            files.extend(iter_text_files(root))

    problems = []
    for path in files:
        problems.extend(check_file(path))

    for path, number, message in problems:
        try:
            display = path.relative_to(SELF.parent.parent)
        except ValueError:
            display = path
        print("%s:%d: %s" % (display, number, message))

    if problems:
        print("check_text: %d issue(s) in %d file(s)" % (len(problems), len({p for p, _, _ in problems})))
        return 1
    print("check_text: %d file(s) checked, no issues" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
