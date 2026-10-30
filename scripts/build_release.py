#!/usr/bin/env python3
"""Build a portable source ZIP, materializing reviewed in-repository skill links."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', 'node_modules', '__pycache__', 'data', 'outputs', 'work', 'trader', 'memory', 'releases', 'RELEASE-MANIFEST.json'}


def walk(directory):
    for path in sorted(directory.iterdir()):
        if path.name in EXCLUDED or path.name == '.env' or path.name.startswith('.env.') and path.name != '.env.example':
            continue
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError(f'External symlink refused: {path}')
        if path.is_dir():
            yield from walk(path)
        elif path.is_file() and not any(s in path.name for s in ('.sqlite', '.db', '.pyc')):
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.destination.resolve().is_relative_to(ROOT):
        raise ValueError('Build the release archive outside the source tree')
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with ZipFile(args.destination, 'w', compression=ZIP_DEFLATED) as archive:
        for path in walk(ROOT):
            relative = path.relative_to(ROOT).as_posix()
            content = path.read_bytes()
            archive.writestr(f'master-agent-system-v0.4/{relative}', content)
            manifest[relative] = hashlib.sha256(content).hexdigest()
        archive.writestr('master-agent-system-v0.4/RELEASE-MANIFEST.json', json.dumps({
            'version': '0.4.0', 'sha256': manifest,
            'skill_links': 'Materialized as ordinary files for portable ZIP extraction',
            'excluded': 'Credentials, databases, operational outputs, dependencies and Git history',
        }, indent=2) + '\n')
    print(json.dumps({'archive': str(args.destination), 'files': len(manifest),
                      'sha256': hashlib.sha256(args.destination.read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
