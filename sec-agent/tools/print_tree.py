from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    root = Path(".")
    excluded = {".git", ".venv", "__pycache__", ".pytest_cache"}

    print(root.resolve().name)
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted([directory for directory in dirs if directory not in excluded])
        rel = Path(current).relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        prefix = "    " * depth

        if str(rel) != ".":
            print(f"{prefix}{Path(current).name}/")

        for name in sorted(files):
            print(f"{prefix}    {name}")


if __name__ == "__main__":
    main()
