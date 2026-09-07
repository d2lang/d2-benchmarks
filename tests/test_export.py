import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts.export_run import export, redact


class ExportTests(unittest.TestCase):
    def test_redaction_covers_dictionary_keys_and_nested_values(self):
        value = {'/host/repo/bin/d2': ['/host/repo/input.d2', {'other': '/host/x'}]}
        self.assertEqual(redact(value, [('/host', '${HOST}'), ('/host/repo', '${REPO}')]),
                         {'${REPO}/bin/d2': ['${REPO}/input.d2', {'other': '${HOST}/x'}]})

    def test_archive_is_deterministic_and_preserves_source_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            source = parent / 'original'
            (source / 'renders').mkdir(parents=True)
            image = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
            (source / 'renders/a.svg').write_bytes(image)
            (source / 'run.json').write_text(json.dumps({'run_id': 'example', 'status': 'complete', 'command': ['/host/repo/d2']}))
            (source / 'raw.jsonl').write_text(json.dumps({'command': ['/host/repo/d2'], 'wall_ms': 5}) + '\n')
            review = {'schema_version': 1, 'rejected_outputs': [
                {'sha256': hashlib.sha256(image).hexdigest(), 'reason': 'Incomplete diagram'}]}
            (source / 'review.json').write_text(json.dumps(review))
            (source / 'unrelated-secret.txt').write_text('must not be copied')

            def report(root, baseline):
                (root / 'index.html').write_text('Synthetic packaging test')
                return {'run_id': 'example', 'status': 'complete'}

            a, b = parent/'a.tar.gz', parent/'b.tar.gz'
            with patch('scripts.export_run.generate', side_effect=report):
                first = export(source, a, [('/host/repo', '${REPO}')])
                second = export(source, b, [('/host/repo', '${REPO}')])
                self.assertEqual(first['sha256'], second['sha256'])
                with self.assertRaises(FileExistsError):
                    export(source, a, [])
            with tarfile.open(a) as archive:
                names = archive.getnames()
                self.assertFalse(any('unrelated-secret' in name for name in names))
                self.assertEqual(archive.extractfile('benchmark-run/renders/a.svg').read(), image)
                self.assertEqual(json.load(archive.extractfile('benchmark-run/review.json')), review)
                records = archive.extractfile('benchmark-run/raw.jsonl').read()
                self.assertNotIn(b'/host/repo', records)
                self.assertIn(b'${REPO}', records)
                hashes = json.load(archive.extractfile('benchmark-run/SHA256SUMS.json'))
                self.assertEqual(hashes['renders/a.svg'], hashlib.sha256(image).hexdigest())
                self.assertEqual(hashes['review.json'], hashlib.sha256(archive.extractfile('benchmark-run/review.json').read()).hexdigest())
            self.assertIn('/host/repo', (source / 'raw.jsonl').read_text(), 'export must not mutate source evidence')

    def test_external_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            source = parent / 'original'
            (source / 'renders').mkdir(parents=True)
            (source / 'run.json').write_text('{}')
            (source / 'raw.jsonl').write_text('{}\n')
            secret = parent / 'outside'
            secret.write_text('outside')
            (source / 'renders/a.svg').symlink_to(secret)
            with self.assertRaisesRegex(ValueError, 'Symlinks'):
                export(source, parent/'result.tar.gz', [])


if __name__ == '__main__':
    unittest.main()
