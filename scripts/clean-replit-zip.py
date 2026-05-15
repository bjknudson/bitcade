#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from pathlib import PurePosixPath


EXCLUDED_DIRS = {".git", ".agents", ".local", "node_modules"}
IGNORED_NAMES = {".ds_store", "thumbs.db"}


def should_keep(name: str) -> bool:
    parts = PurePosixPath(name).parts
    if not parts:
        return False
    lowered = [part.lower() for part in parts]
    if lowered[-1] in IGNORED_NAMES:
        return False
    return not any(part in EXCLUDED_DIRS for part in lowered)


def clean_zip(source: str, target: str) -> None:
    kept = 0
    skipped = 0
    with zipfile.ZipFile(source) as input_zip, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output_zip:
        for info in input_zip.infolist():
            if not should_keep(info.filename):
                skipped += 1
                continue
            output_zip.writestr(info, input_zip.read(info.filename))
            kept += 1
    print(f"Wrote {target}")
    print(f"Kept {kept} entries; skipped {skipped} entries.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove Replit workspace baggage from a zip before Bitcade upload.")
    parser.add_argument("source", help="Downloaded Replit zip")
    parser.add_argument("target", help="Cleaned zip to write")
    args = parser.parse_args()
    clean_zip(args.source, args.target)


if __name__ == "__main__":
    main()
