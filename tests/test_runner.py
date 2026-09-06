import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zlib

from benchmarks.runner import clean_environment, command_for, image_info, invoke, load_toolchain, run, select_fixtures


def png_chunk(kind, payload):
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)


class WorkloadSelectionTests(unittest.TestCase):
    def test_size_selection_excludes_real_world_and_preserves_each_scale(self):
        fixtures = [dict(id=f'basic_{n}', category='basic', counts={'leaf_nodes': n}) for n in (2, 10, 100)]
        fixtures.append(dict(id='real', category='real-world', counts={'leaf_nodes': 10}))
        args = SimpleNamespace(fixtures=None, category=None, nodes=None)
        self.assertEqual(select_fixtures(fixtures, args), fixtures)
        args.nodes = [2, 10]
        self.assertEqual([f['id'] for f in select_fixtures(fixtures, args)], ['basic_2', 'basic_10'])
        args.nodes, args.category = None, ['real-world']
        self.assertEqual([f['id'] for f in select_fixtures(fixtures, args)], ['real'])
        args.nodes = [10]
        with self.assertRaisesRegex(ValueError, 'no fixtures match'):
            select_fixtures(fixtures, args)

    def test_unknown_fixture_or_size_is_not_silently_omitted(self):
        fixtures = [dict(id='basic', category='basic', counts={'leaf_nodes': 2})]
        with self.assertRaisesRegex(ValueError, 'unknown fixtures'):
            select_fixtures(fixtures, SimpleNamespace(fixtures=['basic', 'missing']))
        with self.assertRaisesRegex(ValueError, 'unsupported basic node counts'):
            select_fixtures(fixtures, SimpleNamespace(fixtures=None, nodes=[2, 100]))


class OutputValidationTests(unittest.TestCase):
    def test_truncated_and_crc_corrupt_png_are_rejected(self):
        png = (b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
               + png_chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00')) + png_chunk(b'IEND', b''))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.png'
            path.write_bytes(png)
            self.assertEqual(image_info(path)['pixels'], 1)
            path.write_bytes(png[:-1])
            with self.assertRaises(ValueError):
                image_info(path)
            damaged = bytearray(png)
            damaged[29] ^= 1
            path.write_bytes(damaged)
            with self.assertRaisesRegex(ValueError, 'CRC'):
                image_info(path)

    def test_svg_units_and_error_diagrams(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.svg'
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="72pt" height="36pt" viewBox="0 0 72 36"/>')
            info = image_info(path)
            self.assertEqual((info['width_css_px'], info['height_css_px']), (96, 48))
            self.assertNotIn('bytes', info)
            self.assertNotIn('gzip9_bytes', info)
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" data-diagram-type="ERROR"/>')
            with self.assertRaisesRegex(ValueError, 'error diagram'):
                image_info(path)
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 NaN 5"/>')
            with self.assertRaises(ValueError):
                image_info(path)


class ProcessTests(unittest.TestCase):
    def test_arguments_with_spaces_and_shell_metacharacters_are_literal(self):
        marker = '$(touch unexpected); hello with spaces'
        result = invoke([sys.executable, '-c', 'import sys; print(sys.argv[1])', marker], clean_environment(), 5)
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['stdout'].strip(), marker)

    def test_launch_failure_is_a_record(self):
        result = invoke(['/nonexistent/d2-benchmarks-test'], clean_environment(), 5)
        self.assertIsNone(result['returncode'])
        self.assertIn('launch_error', result)

    @unittest.skipUnless(os.name == 'posix', 'POSIX process groups')
    def test_timeout_terminates_descendant(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'escaped'
            child = 'import time,pathlib; time.sleep(1); pathlib.Path(' + repr(str(marker)) + ').write_text("bad")'
            parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); time.sleep(5)'
            result = invoke([sys.executable, '-c', parent], clean_environment(), .1)
            self.assertTrue(result['timeout'])
            self.assertNotEqual(result['returncode'], 0)
            time.sleep(1.1)
            self.assertFalse(marker.exists(), 'timed-out child must not keep rendering')

    def test_png_flags_match_css_density(self):
        for density in (2.0, .5):
            src, out, config = Path('/tmp/a'), Path('/tmp/b.png'), Path('/tmp/config')
            for kind, expected in (
                ('d2', ['--scale', str(density/2)]),
                ('mermaid', ['-s', str(density)]),
                ('graphviz', ['-Gdpi=' + str(96*density)]),
                ('plantuml', ['-Sdpi=' + str(int(96*density))]),
            ):
                command = command_for({'kind': kind, 'argv': ['tool']}, src, out, 'png', density, config)
                for arg in expected:
                    self.assertIn(arg, command)

    def test_tool_ids_cannot_escape_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'toolchain.json'
            path.write_text(json.dumps({'schema_version': 1, 'tools': {'../escape': {'kind': 'd2'}}}))
            with self.assertRaisesRegex(ValueError, 'invalid tool ID'):
                load_toolchain(path)


class SessionTests(unittest.TestCase):
    def test_failed_jobs_remain_recorded_and_existing_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'corpus/d2').mkdir(parents=True)
            (root / 'config').mkdir()
            (root / 'benchmarks').mkdir()
            (root / 'corpus/d2/sample.d2').write_text('a -> b')
            fixture = {'id': 'sample', 'title': 'Sample', 'png_density': 2, 'primary_png': True,
                       'inputs': {'d2': {'path': 'd2/sample.d2'}}, 'counts': {'leaf_nodes': 2, 'groups': 0, 'edges': 1}}
            (root / 'corpus/manifest.json').write_text(json.dumps({'schema_version': 1, 'fixtures': [fixture]}))
            program = root / 'fake renderer.py'
            program.write_text('import pathlib,sys,os\n'
                               'if "fail" in sys.argv: raise SystemExit(3)\n'
                               'pathlib.Path(sys.argv[-1]).write_text(\'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><!--\'+str(os.getpid())+\'--></svg>\')\n')
            tools = {name: {'kind': 'd2', 'argv': [sys.executable, str(program), flag],
                            'version_argv': [sys.executable, '--version']}
                     for name, flag in [('d2-good', 'pass'), ('d2-bad', 'fail')]}
            config = root / 'tools.json'
            config.write_text(json.dumps({'schema_version': 1, 'tools': tools}))
            args = SimpleNamespace(toolchain=config, tools=list(tools), formats=['svg'], fixtures=None,
                                   output=root/'result', label='test', seed=1, warmups=1, repetitions=2, timeout=5)
            with patch('benchmarks.runner.ROOT', root), patch('benchmarks.corpus.validate_corpus', return_value={'errors': []}), patch('benchmarks.corpus.validate_svg', return_value={'errors': []}):
                output, code = run(args)
                self.assertEqual(code, 1)
                rows = [json.loads(line) for line in (output / 'raw.jsonl').read_text().splitlines()]
                self.assertEqual(len(rows), 6)
                self.assertEqual(sum(r['warmup'] for r in rows), 2)
                self.assertEqual(sum(r['success'] for r in rows), 3)
                self.assertEqual(len({r['image']['sha256'] for r in rows if r['success']}), 3, 'each render must use a fresh process')
                self.assertEqual(json.loads((output / 'run.json').read_text())['status'], 'failed')
                before = (output / 'raw.jsonl').read_bytes()
                with self.assertRaises(FileExistsError):
                    run(args)
                self.assertEqual((output / 'raw.jsonl').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
