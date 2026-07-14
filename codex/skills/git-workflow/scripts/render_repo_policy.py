#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render or check a generated repository workflow policy.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-label", default="dotfiles/policies/development-workflow.md")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    source = Path(args.source).read_text()
    digest = hashlib.sha256(source.encode()).hexdigest()
    rendered = (
        f"<!-- GENERATED FILE: DO NOT EDIT. source={args.source_label} sha256={digest} -->\n\n"
        f"{source}"
    )
    output = Path(args.output)

    if args.check:
        if not output.is_file() or output.read_text() != rendered:
            raise SystemExit(f"generated policy is stale: {output}")
        print(f"generated policy is current: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered)
    print(f"generated policy updated: {output}")


if __name__ == "__main__":
    main()
