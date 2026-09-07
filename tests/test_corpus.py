"""Corruption checks that exercise semantic validation beyond file checksums."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from benchmarks.corpus import validate_corpus, validate_svg

ROOT = Path(__file__).resolve().parents[1]


class CorpusTests(unittest.TestCase):
    def test_checked_in_corpus_is_complete(self):
        result=validate_corpus(ROOT)
        self.assertEqual(result['errors'],[])
        self.assertEqual(result['totals'],{'leaf_nodes':458,'groups':140,'edges':304})
        self.assertEqual(len(result['fixtures']),13)

    def test_generated_definitions_match_frozen_graphs(self):
        manifest=json.loads((ROOT/'corpus/manifest.json').read_text())
        basics=[f for f in manifest['fixtures'] if f['category']=='basic']
        self.assertEqual({f['counts']['leaf_nodes'] for f in basics},{2,10,100})
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'generated'
            subprocess.run([sys.executable,str(ROOT/'corpus/generators/basic.py'),
                            '--output',str(output)],check=True)
            for fixture in basics:
                n=fixture['counts']['leaf_nodes']
                self.assertEqual((output/(fixture['id']+'.d2')).read_bytes(),
                                 (ROOT/'corpus'/fixture['inputs']['d2']['path']).read_bytes())
                mapping=json.loads((ROOT/'corpus'/fixture['semantic']['path']).read_text())
                self.assertEqual(mapping['root_attributes']['direction']['value'],'down')
                self.assertEqual([(o['d2_id'],o['translated_label'],o['source_shape'],o['parent_d2_id'])
                                  for o in mapping['objects']],
                                 [(f'n{i:03d}',f'Node {i:03d}','rectangle','') for i in range(n)])
                self.assertEqual([(e['source_d2_id'],e['target_d2_id'],e['source_visible_arrow'],
                                   e['target_visible_arrow'],e['translated_label']) for e in mapping['edges']],
                                 [(f'n{(i-1)//2:03d}',f'n{i:03d}',False,True,'') for i in range(1,n)])

    def test_all_translations_regenerate_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'translations'
            subprocess.run([sys.executable,str(ROOT/'scripts/translations/regenerate.py'),
                            '--output',str(output)],check=True,stdout=subprocess.DEVNULL)
            report=json.loads((output/'regeneration-check.json').read_text())
            self.assertTrue(report['valid'])
            self.assertEqual(len(report['checks']),39)

    def test_changed_file_does_not_pass_as_frozen_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus=Path(tmp)/'corpus';shutil.copytree(ROOT/'corpus',corpus)
            path=corpus/'graphviz/fulcro_rad.dot'
            path.write_text(path.read_text()+'\n// modified\n')
            result=validate_corpus(corpus)
            self.assertTrue(any('SHA-256 mismatch' in e for e in result['errors']))

    def test_all_fixtures_require_primary_png_at_two_times_density(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus=Path(tmp)/'corpus';shutil.copytree(ROOT/'corpus',corpus)
            manifest_path=corpus/'manifest.json';original=manifest_path.read_text()
            for ident in ('basic_002','tpmjs_architecture'):
                for field,value,error in [('png_density',.5,'Unexpected raster density'),
                                          ('primary_png',False,'Unexpected PNG aggregate membership')]:
                    with self.subTest(fixture=ident,field=field):
                        manifest=json.loads(original)
                        fixture=next(f for f in manifest['fixtures'] if f['id']==ident)
                        fixture[field]=value;manifest_path.write_text(json.dumps(manifest))
                        result=validate_corpus(corpus)
                        self.assertTrue(any(ident in e and error in e for e in result['errors']),result)

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
