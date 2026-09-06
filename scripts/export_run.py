#!/usr/bin/env python3
"""Package a run and regenerated reports in a deterministic portable archive."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.report import generate


def redact(value, prefixes):
    """Replace supplied path prefixes in metadata keys and string values."""
    if isinstance(value, str):
        for prefix, token in sorted(prefixes, key=lambda item: len(item[0]), reverse=True):
            value = value.replace(prefix, token)
        return value
    if isinstance(value, dict):
        return {redact(k, prefixes): redact(v, prefixes) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, prefixes) for v in value]
    return value


def export(source: Path, destination: Path, prefixes: list[tuple[str, str]], baseline: str = 'd2-dagre') -> dict:
    source, destination = source.resolve(), destination.resolve()
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite {destination}')
    if destination.is_relative_to(source):
        raise ValueError('Put the archive outside its source run directory')
    for name in ('run.json', 'raw.jsonl'):
        if not (source / name).is_file():
            raise ValueError(f'Missing {name}')
    if any(not prefix or not token for prefix, token in prefixes):
        raise ValueError('Redaction prefixes and replacement tokens must be nonempty')
    # Only expected run artifacts are copied; no executable caches or unrelated
    # files beside a run can accidentally enter the archive.
    with tempfile.TemporaryDirectory(prefix='d2-benchmark-export-') as tmp:
        root = Path(tmp) / 'benchmark-run'
        root.mkdir()
        for name in ('inputs', 'config', 'renders'):
            src = source / name
            if src.exists():
                if any(p.is_symlink() for p in [src, *src.rglob('*')]):
                    raise ValueError(f'Symlinks are not accepted in exported {name}')
                shutil.copytree(src, root / name)
        for name in ('run.json', 'environment.json'):
            if (source / name).exists():
                value = redact(json.loads((source / name).read_text()), prefixes)
                if name == 'run.json':
                    value['publication'] = {
                        'source_run_json_sha256': hashlib.sha256((source / 'run.json').read_bytes()).hexdigest(),
                        'source_raw_jsonl_sha256': hashlib.sha256((source / 'raw.jsonl').read_bytes()).hexdigest(),
                        'path_tokens': [token for _, token in prefixes],
                        'changes': 'Only supplied host path prefixes were replaced in JSON metadata. Input and rendered file bytes are unchanged. Reports were regenerated from the exported records.',
                    }
                (root / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        with (root / 'raw.jsonl').open('w') as out:
            for line in (source / 'raw.jsonl').read_text().splitlines():
                if line.strip():
                    out.write(json.dumps(redact(json.loads(line), prefixes), ensure_ascii=False) + '\n')
        summary = generate(root, baseline=baseline)
        (root / 'README.txt').write_text(
            'Open index.html in a local browser. report.md, summary.csv, and summary.json summarize raw.jsonl.\n'
            'Inputs and rendered assets retain their original bytes and hashes. run.json records the source revision and publication transformations.\n'
            'Path tokens, when present, replace only explicitly selected host path prefixes. They are not executable filesystem paths.\n'
            'To repeat the experiment, check out the captured benchmark repository revision, run scripts/setup.py, and use the settings recorded in run.json.\n'
            'This is one machine/session; see its environment and the repository methodology before interpreting ratios.\n')
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(root.rglob('*')) if p.is_file()}
        (root / 'SHA256SUMS.json').write_text(json.dumps(hashes, indent=2) + '\n')
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Stable ordering, timestamps and ownership make repeat exports identical.
        with destination.open('xb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode='w') as archive:
                    for path in sorted(root.rglob('*')):
                        info = archive.gettarinfo(str(path), arcname=str(Path('benchmark-run') / path.relative_to(root)))
                        info.uid = info.gid = info.mtime = 0
                        info.uname = info.gname = ''
                        info.mode = 0o755 if path.is_dir() else 0o644
                        if path.is_file():
                            with path.open('rb') as stream:
                                archive.addfile(info, stream)
                        else:
                            archive.addfile(info)
    return {'archive': str(destination),
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'run_id': summary['run_id'], 'status': summary['status']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--redact-prefix', action='append', default=[], metavar='PATH=TOKEN',
                        help='replace this host path prefix in JSON records; repeatable, longest prefix first')
    parser.add_argument('--baseline', default='d2-dagre')
    args = parser.parse_args()
    prefixes = []
    for entry in args.redact_prefix:
        if '=' not in entry:
            parser.error('--redact-prefix requires PATH=TOKEN')
        prefixes.append(tuple(entry.split('=', 1)))
    try:
        print(json.dumps(export(args.run_dir, args.archive, prefixes, args.baseline), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, f'error: {error}\n')


if __name__ == '__main__':
    main()
