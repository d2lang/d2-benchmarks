"""Corruption checks that exercise semantic validation beyond file checksums."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from benchmarks.corpus import validate_corpus, validate_svg

ROOT = Path(__file__).resolve().parents[1]


class CorpusTests(unittest.TestCase):
    def test_checked_in_corpus_is_complete(self):
        result=validate_corpus(ROOT)
        self.assertEqual(result['errors'],[])
        self.assertEqual(result['totals'],{'leaf_nodes':346,'groups':140,'edges':195})
        self.assertEqual(len(result['fixtures']),10)

    def test_changed_file_does_not_pass_as_frozen_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus=Path(tmp)/'corpus';shutil.copytree(ROOT/'corpus',corpus)
            path=corpus/'graphviz/fulcro_rad.dot'
            path.write_text(path.read_text()+'\n// modified\n')
            result=validate_corpus(corpus)
            self.assertTrue(any('SHA-256 mismatch' in e for e in result['errors']))

    def test_rehashed_translation_cannot_drop_parallel_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus=Path(tmp)/'corpus';shutil.copytree(ROOT/'corpus',corpus)
            path=corpus/'mermaid/lion_reader_frontend.mmd'
            lines=path.read_text().splitlines()
            removed=[line for line in lines if 'n010 -->' in line and line.endswith('n007')]
            self.assertEqual(len(removed),2)
            lines.remove(removed[1]);path.write_text('\n'.join(lines)+'\n')
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            # Simulate a deliberate fixture refresh whose checksums were
            # updated, but whose translation accidentally collapsed an edge.
            manifest_path=corpus/'manifest.json';manifest=json.loads(manifest_path.read_text())
            fixture=next(f for f in manifest['fixtures'] if f['id']=='lion_reader_frontend')
            fixture['inputs']['mermaid']['sha256']=digest(path)
            semantic=corpus/fixture['semantic']['path'];mapping=json.loads(semantic.read_text())
            mapping['mermaid_sha256']=digest(path);semantic.write_text(json.dumps(mapping))
            fixture['semantic']['sha256']=digest(semantic);manifest_path.write_text(json.dumps(manifest))
            result=validate_corpus(corpus)
            self.assertTrue(any('mermaid edge identity/order/label/direction differs' in e for e in result['errors']),result)

    def test_svg_error_and_empty_content_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.svg'
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" data-diagram-type="ERROR"><text>Syntax Error</text></svg>')
            result=validate_svg(path,'fulcro_rad','plantuml',ROOT/'corpus')
            self.assertFalse(result['valid'])
            self.assertIn('PlantUML error SVG',result['errors'])
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            for kind in ('d2','mermaid','graphviz','plantuml'):
                self.assertFalse(validate_svg(path,'fulcro_rad',kind,ROOT/'corpus')['valid'],kind)


if __name__=='__main__':unittest.main()
