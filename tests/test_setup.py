"""Check archive safety and frozen setup inputs without installing tools."""
import io
import json
from pathlib import Path
import runpy
import stat
import tarfile
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SETUP = runpy.run_path(str(ROOT / 'scripts/setup.py'))


class SetupTests(unittest.TestCase):
    def test_only_reuse_completed_setup_with_current_pins_and_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            tools = Path(folder)
            executable = tools / 'tool'
            executable.write_text('#!/bin/sh\nexit 0\n')
            executable.chmod(0o755)
            config = tools / 'toolchain.json'
            config.write_text(json.dumps({'tools': {'tool': {'argv': [str(executable)]}}}))
            state = {'platform': 'test', 'lock_hashes': {'runtime/pins.json': 'original'}}
            # A config can exist before setup smoke checks finish.
            self.assertFalse(SETUP['ready'](tools, state))
            manifest = {'platform': state['platform'], 'lock_hashes': state['lock_hashes'],
                        'toolchain_sha256': SETUP['digest'](config)}
            (tools / 'setup-manifest.json').write_text(json.dumps(manifest))
            self.assertTrue(SETUP['ready'](tools, state))
            self.assertFalse(SETUP['ready'](tools, dict(state, lock_hashes={'runtime/pins.json': 'changed'})))
            config.write_text(config.read_text() + '\n')
            self.assertFalse(SETUP['ready'](tools, state))
            config.write_text(config.read_text().rstrip('\n'))
            executable.unlink()
            self.assertFalse(SETUP['ready'](tools, state))

    def test_pins_cover_both_native_targets(self):
        pins = json.loads((ROOT / 'runtime/pins.json').read_text())
        self.assertEqual(set(pins['platforms']), {'osx-arm64', 'linux-64'})
        for platform, archives in pins['platforms'].items():
            packages = json.loads((ROOT / 'runtime/locks' / (platform + '.json')).read_text())['packages']
            self.assertEqual(len(packages), len({p['name'] for p in packages}))
            for entry in list(archives.values()) + list(pins['common'].values()) + packages:
                self.assertRegex(entry['sha256'], r'^[0-9a-f]{64}$')
                self.assertTrue(entry['url'].startswith('https://'))
            selected = {p['name']: p['version'] for p in packages}
            self.assertEqual(selected['graphviz'], pins['versions']['graphviz'])
            self.assertEqual(selected['openjdk'], pins['versions']['java'])

    def test_npm_tool_versions_are_frozen(self):
        pins = json.loads((ROOT / 'runtime/pins.json').read_text())['versions']
        lock = json.loads((ROOT / 'runtime/package-lock.json').read_text())['packages']
        for package, version in [('mermaid', pins['mermaid']), ('puppeteer', pins['puppeteer']),
                                 ('@mermaid-js/mermaid-cli', pins['mermaid_cli'])]:
            self.assertEqual(lock['node_modules/' + package]['version'], version)
        self.assertTrue(all(p.get('integrity') for name, p in lock.items() if name))

    def test_browser_variant_matches_mermaid_default(self):
        source = 'let puppeteerConfig = ({ headless: "shell", }); if (puppeteerConfigFile) {}'
        self.assertEqual(SETUP['validate_mermaid_browser'](source, 'chrome-headless-shell', Path('/bin/chrome-headless-shell')), 'shell')
        with self.assertRaises(RuntimeError):
            SETUP['validate_mermaid_browser'](source, 'chrome', Path('/bin/chrome'))
        # A stale comment must not conceal a changed active launch mode.
        changed = 'let puppeteerConfig = ({ /* headless: "shell", */ headless: true, }); if (puppeteerConfigFile) {}'
        with self.assertRaises(RuntimeError):
            SETUP['validate_mermaid_browser'](changed, 'chrome-headless-shell', Path('/bin/chrome-headless-shell'))

    def test_browser_archives_are_headless_shell(self):
        pins = json.loads((ROOT / 'runtime/pins.json').read_text())
        self.assertEqual(pins['versions']['browser_variant'], 'chrome-headless-shell')
        for platform in pins['platforms'].values():
            self.assertIn('/chrome-headless-shell-', platform['chrome']['url'])
            self.assertEqual(Path(platform['chrome']['executable']).name, 'chrome-headless-shell')

    def test_tar_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); archive = base / 'bad.tar'
            with tarfile.open(archive, 'w') as out:
                info = tarfile.TarInfo('../escape'); info.size = 1
                out.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                SETUP['extract'](archive, base / 'target', 'test')
            self.assertFalse((base / 'escape').exists())

    def test_zip_preserves_executable_and_internal_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); archive = base / 'good.zip'; dest = base / 'target'
            with zipfile.ZipFile(archive, 'w') as out:
                binary = zipfile.ZipInfo('bundle/bin/tool'); binary.external_attr = (stat.S_IFREG | 0o755) << 16
                out.writestr(binary, b'#!/bin/sh\nexit 0\n')
                link = zipfile.ZipInfo('bundle/tool'); link.external_attr = (stat.S_IFLNK | 0o777) << 16
                out.writestr(link, 'bin/tool')
            SETUP['extract'](archive, dest, 'test')
            self.assertEqual((dest / 'bundle/bin/tool').stat().st_mode & 0o777, 0o755)
            self.assertTrue((dest / 'bundle/tool').is_symlink())
            self.assertEqual((dest / 'bundle/tool').read_bytes(), b'#!/bin/sh\nexit 0\n')

    def test_zip_rejects_external_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); archive = base / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as out:
                link = zipfile.ZipInfo('link'); link.external_attr = (stat.S_IFLNK | 0o777) << 16
                out.writestr(link, '../escape')
            with self.assertRaises(ValueError):
                SETUP['extract'](archive, base / 'target', 'test')


if __name__ == '__main__':
    unittest.main()
