#!/usr/bin/env python3
"""Install the pinned public benchmark tools into this checkout, without sudo."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime'


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def download(spec: dict, cache: Path) -> Path:
    filename = Path(urllib.parse.urlparse(spec['url']).path).name
    path = cache / 'downloads' / spec['sha256'] / filename
    if path.is_file() and digest(path) == spec['sha256']:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    for attempt in range(3):
        try:
            request = urllib.request.Request(spec['url'], headers={'User-Agent': 'd2-benchmarks-setup/1'})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as out:
                shutil.copyfileobj(response, out, 1024 * 1024)
            actual = digest(temporary)
            if actual != spec['sha256']:
                raise RuntimeError(f"SHA-256 mismatch for {spec['url']}: {actual}")
            temporary.replace(path)
            return path
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError('unreachable')


def under(root: Path, path: Path) -> None:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Archive entry escapes destination: {path}')


def extract(archive: Path, destination: Path, marker: str) -> None:
    """Keep permissions and internal symlinks, including the macOS Chrome bundle."""
    if (destination / '.archive-sha256').is_file():
        if (destination / '.archive-sha256').read_text().strip() != marker:
            raise RuntimeError(f'{destination} contains a different pinned archive; use a fresh --tools-dir')
        return
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zipped:
            for entry in zipped.infolist():
                path = destination / entry.filename
                under(destination, path)
                mode = entry.external_attr >> 16
                if entry.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                elif stat.S_ISLNK(mode):
                    target = zipped.read(entry).decode('utf-8')
                    under(destination, path.parent / target)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.unlink(missing_ok=True)
                    path.symlink_to(target)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(entry) as src, path.open('wb') as out:
                        shutil.copyfileobj(src, out)
                    if mode & 0o777:
                        path.chmod(mode & 0o777)
    else:
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                under(destination, destination / member.name)
                if member.issym():
                    under(destination, (destination / member.name).parent / member.linkname)
                if member.islnk():
                    under(destination, destination / member.linkname)
                if member.isdev() or member.isfifo():
                    raise ValueError('Device/FIFO entries are not supported')
            tar.extractall(destination, filter='data')
    (destination / '.archive-sha256').write_text(marker + '\n')


def run(argv: list[str | Path], *, env: dict, cwd: Path, log: Path) -> str:
    command = [str(x) for x in argv]
    print('+ ' + ' '.join(command[:5]) + (' …' if len(command) > 5 else ''), flush=True)
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with log.open('a') as stream:
        stream.write(json.dumps({'command': command, 'cwd': str(cwd), 'returncode': proc.returncode}) + '\n')
        stream.write(proc.stdout + '\n')
    if proc.returncode:
        raise RuntimeError(f'Command failed ({proc.returncode}); see {log}\n{proc.stdout[-5000:]}')
    return proc.stdout.strip()


def validate_mermaid_browser(source: str, browser_variant: str, executable: Path) -> str:
    """Match mmdc's actual default launch mode, not merely a Chromium version."""
    try:
        section = source.split('let puppeteerConfig =', 1)[1].split('if (puppeteerConfigFile)', 1)[0]
    except IndexError as exc:
        raise RuntimeError('Cannot identify the pinned Mermaid CLI launch defaults; review browser selection.') from exc
    section = re.sub(r'/\*.*?\*/', '', section, flags=re.S)
    match = re.search(r'headless\s*:\s*(["\'])shell\1\s*[,}]', section)
    if not match or browser_variant != 'chrome-headless-shell' or executable.name != 'chrome-headless-shell':
        raise RuntimeError('Mermaid default/browser mismatch: mmdc must use headless="shell" with Chrome Headless Shell.')
    return 'shell'


def setup_state() -> dict:
    target = {('Darwin', 'arm64'): 'osx-arm64', ('Linux', 'x86_64'): 'linux-64'}.get((platform.system(), platform.machine()))
    if target is None:
        raise RuntimeError('Supported setup targets: macOS arm64 and Linux x86_64 (Ubuntu 24.04 CI).')
    native_lock_path = RUNTIME / 'locks' / (target + '.json')
    lock_files = [RUNTIME / 'pins.json', native_lock_path, RUNTIME / 'package.json', RUNTIME / 'package-lock.json']
    lock_hashes = {str(p.relative_to(ROOT)): digest(p) for p in lock_files}
    fingerprint = hashlib.sha256(json.dumps(lock_hashes, sort_keys=True).encode()).hexdigest()
    return {'platform': target, 'fingerprint': fingerprint, 'lock_hashes': lock_hashes}


def ready(tools: Path, state: dict) -> bool:
    """Only reuse an installation that finished all setup checks with these pins."""
    try:
        manifest = json.loads((tools / 'setup-manifest.json').read_text())
        if (manifest.get('platform') != state['platform'] or
                manifest.get('lock_hashes') != state['lock_hashes'] or
                manifest.get('toolchain_sha256') != digest(tools / 'toolchain.json')):
            return False
        toolchain = json.loads((tools / 'toolchain.json').read_text())
        for entry in toolchain['tools'].values():
            if not os.access(entry['argv'][0], os.X_OK):
                return False
            for argument in entry['argv']:
                if Path(argument).is_absolute() and not Path(argument).is_file():
                    return False
            browser = entry.get('env', {}).get('PUPPETEER_EXECUTABLE_PATH')
            if browser and not os.access(browser, os.X_OK):
                return False
        return bool(toolchain['tools'])
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return False


def ensure_installed(tools: Path) -> None:
    if sys.version_info < (3, 11, 9):
        raise RuntimeError('Python 3.11.9+ is required (3.12+ recommended).')
    if ready(tools, setup_state()):
        print(f'Reusing pinned tools: {tools}', flush=True)
    else:
        install(tools, tools / 'cache')


def install(tools: Path, cache: Path) -> None:
    pins = json.loads((RUNTIME / 'pins.json').read_text())
    state = setup_state()
    target, fingerprint, lock_hashes = state['platform'], state['fingerprint'], state['lock_hashes']
    target_pins = pins['platforms'][target]
    native_lock_path = RUNTIME / 'locks' / (target + '.json')
    native = json.loads(native_lock_path.read_text())['packages']
    tools.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    marker = tools / 'setup-lock.json'
    if marker.exists() and json.loads(marker.read_text()) != {'platform': target, 'fingerprint': fingerprint}:
        raise RuntimeError('Tool pins changed. Choose a fresh --tools-dir or remove this generated tools directory first.')
    (tools / 'setup-manifest.json').unlink(missing_ok=True)
    marker.write_text(json.dumps({'platform': target, 'fingerprint': fingerprint}, indent=2) + '\n')
    log = tools / 'setup.log'
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('D2_', 'CONDA_', 'MAMBA_', 'npm_config_', 'NPM_CONFIG_')) or key in (
            'JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'NODE_OPTIONS', 'NODE_PATH',
            'GOPRIVATE', 'GONOPROXY', 'GONOSUMDB', 'GOFLAGS', 'GOWORK', 'GOROOT'):
            env.pop(key)
    env.update(PUPPETEER_SKIP_DOWNLOAD='true', npm_config_cache=str(cache / 'npm'),
               npm_config_userconfig=str(tools / 'npmrc'), npm_config_update_notifier='false',
               GOCACHE=str(cache / 'go-build'), GOPATH=str(cache / 'go'), GOTOOLCHAIN='local',
               GOPROXY='https://proxy.golang.org', GOSUMDB='sum.golang.org',
               CGO_ENABLED='0', GOTELEMETRY='off', GOWORK='off', XDG_CACHE_HOME=str(cache / 'xdg'),
               MAMBA_ROOT_PREFIX=str(tools / 'mamba'), CONDA_PKGS_DIRS=str(cache / 'conda'))
    (tools / 'npmrc').write_text('audit=false\nfund=false\nupdate-notifier=false\n')
    named = dict(target_pins, **pins['common'])
    specs = list(named.values()) + native
    print(f'Verifying {len(specs)} pinned downloads for {target}…', flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        paths = list(pool.map(lambda spec: download(spec, cache), specs))
    archives = dict(zip(named, paths[:len(named)]))
    native_archives = []
    for spec, downloaded in zip(native, paths[len(named):]):
        # Keep the platform in the file URL: libmamba uses it when deciding to
        # re-sign relocated Mach-O binaries on Apple Silicon.
        local = cache / 'native-archives' / spec['subdir'] / downloaded.name
        local.parent.mkdir(parents=True, exist_ok=True)
        if not local.is_file() or digest(local) != spec['sha256']:
            shutil.copyfile(downloaded, local)
        native_archives.append(local)
    for name in ['go', 'node', 'micromamba', 'chrome', 'd2_source']:
        extract(archives[name], tools / name, named[name]['sha256'])
    java_env = tools / 'native'
    # Installing into an initialized empty prefix avoids micromamba create's user-level
    # ~/.conda/environments.txt registration. No shell initialization is performed.
    (java_env / 'conda-meta').mkdir(parents=True, exist_ok=True)
    (java_env / 'conda-meta/history').touch(exist_ok=True)
    explicit = tools / 'native-explicit.txt'
    explicit.write_text('@EXPLICIT\n' + '\n'.join(path.as_uri() + '#' + spec['md5']
                                                  for path, spec in zip(native_archives, native)) + '\n')
    run([tools / 'micromamba/bin/micromamba', '--no-rc', '--root-prefix', tools / 'mamba',
         'install', '--yes', '--offline', '--prefix', java_env, '--file', explicit], env=env, cwd=tools, log=log)
    dot = java_env / 'bin/dot'
    java_home = java_env / 'lib/jvm'
    java = java_home / 'bin/java'
    if not java.exists():
        java = java_env / 'bin/java'
        java_home = java.resolve().parent.parent
    go = tools / 'go' / target_pins['go']['root'] / 'bin/go'
    node_root = tools / 'node' / target_pins['node']['root']
    node = node_root / 'bin/node'
    chrome = tools / 'chrome' / target_pins['chrome']['executable']
    env.update(PATH=str(node_root / 'bin') + os.pathsep + env.get('PATH', ''),
               GRAPHVIZ_DOT=str(dot), JAVA_HOME=str(java_home), PUPPETEER_EXECUTABLE_PATH=str(chrome))
    npm_dir = tools / 'mermaid'
    npm_dir.mkdir(exist_ok=True)
    for name in ['package.json', 'package-lock.json']:
        shutil.copyfile(RUNTIME / name, npm_dir / name)
    run([node, node_root / 'lib/node_modules/npm/bin/npm-cli.js', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'],
        env=env, cwd=npm_dir, log=log)
    mermaid_browser_mode = validate_mermaid_browser(
        (npm_dir / 'node_modules/@mermaid-js/mermaid-cli/src/index.js').read_text(),
        pins['versions']['browser_variant'], chrome)
    source = tools / 'd2_source' / ('d2-' + pins['versions']['d2_revision'])
    binary = tools / 'bin/d2'
    binary.parent.mkdir(exist_ok=True)
    run([go, 'build', '-trimpath', '-ldflags=-s -w', '-o', binary, '.'], env=env, cwd=source, log=log)
    jar = tools / 'plantuml.jar'
    shutil.copyfile(archives['plantuml'], jar)
    cli = npm_dir / 'node_modules/@mermaid-js/mermaid-cli/src/cli.js'
    common = {'runtime_lock_sha256': fingerprint, 'setup_platform': target}
    definitions = {
        'd2-dagre': {'kind': 'd2', 'argv': [str(binary), '--layout', 'dagre'], 'version_argv': [str(binary), '--version'], 'env': {},
                     'provenance': dict(common, source='https://github.com/d2lang/d2', revision=pins['versions']['d2_revision'],
                                        go=pins['versions']['go'], build='CGO_ENABLED=0 go build -trimpath -ldflags="-s -w"', binary_sha256=digest(binary))},
        'mermaid-dagre': {'kind': 'mermaid', 'argv': [str(node), str(cli)], 'version_argv': [str(node), str(cli), '--version'],
                           'env': {'PUPPETEER_EXECUTABLE_PATH': str(chrome), 'PUPPETEER_CACHE_DIR': str(cache / 'puppeteer')},
                           'provenance': dict(common, node=pins['versions']['node'], mermaid_cli=pins['versions']['mermaid_cli'],
                                              mermaid=pins['versions']['mermaid'], puppeteer=pins['versions']['puppeteer'],
                                              chrome=pins['versions']['chrome'], chrome_archive_sha256=target_pins['chrome']['sha256'],
                                              browser_variant=pins['versions']['browser_variant'], headless_mode=mermaid_browser_mode,
                                              npm_lock_sha256=digest(RUNTIME / 'package-lock.json'))},
        'graphviz-dot': {'kind': 'graphviz', 'argv': [str(dot), '-Kdot'], 'version_argv': [str(dot), '-V'],
                         'env': {'XDG_CACHE_HOME': str(cache / 'xdg')},
                         'provenance': dict(common, source='https://graphviz.org/', version=pins['versions']['graphviz'],
                                            binary_sha256=digest(dot), native_lock_sha256=digest(native_lock_path),
                                            png_backend='cairo', svg_backend='svg')},
        'plantuml-dot': {'kind': 'plantuml',
                         'argv': [str(java), '-Djava.awt.headless=true', '-DPLANTUML_LIMIT_SIZE=32768', '-jar', str(jar), '-charset', 'UTF-8'],
                         'version_argv': [str(java), '-jar', str(jar), '-version'],
                         'env': {'GRAPHVIZ_DOT': str(dot), 'JAVA_HOME': str(java_home), 'XDG_CACHE_HOME': str(cache / 'xdg')},
                         'provenance': dict(common, source='https://plantuml.com/', version=pins['versions']['plantuml'],
                                            jar_sha256=digest(jar), java=pins['versions']['java'], graphviz=pins['versions']['graphviz'])},
    }
    toolchain = {'schema_version': 1, 'tools': definitions}
    (tools / 'toolchain.json').write_text(json.dumps(toolchain, indent=2) + '\n')
    versions = {}
    for tool, entry in definitions.items():
        tool_env = dict(env, **entry['env'])
        versions[tool] = run(entry['version_argv'], env=tool_env, cwd=tools, log=log)
    versions['java'] = run([java, '-version'], env=env, cwd=tools, log=log)
    versions['node'] = run([node, '--version'], env=env, cwd=tools, log=log)
    versions['chrome'] = run([chrome, '--version'], env=env, cwd=tools, log=log)
    versions['go'] = run([go, 'version'], env=env, cwd=tools, log=log)
    versions['plantuml_testdot'] = run([java, '-Djava.awt.headless=true', '-jar', jar, '-testdot'], env=env, cwd=tools, log=log)
    assert pins['versions']['graphviz'] in versions['graphviz-dot']
    assert pins['versions']['plantuml'] in versions['plantuml-dot']
    assert pins['versions']['mermaid_cli'] in versions['mermaid-dagre']
    assert pins['versions']['chrome'] in versions['chrome']
    smoke = tools / 'smoke'
    smoke.mkdir(exist_ok=True)
    inputs = {'d2': 'a: Hello\nb: World\na -> b\n', 'mmd': 'flowchart TB\na[Hello] --> b[World]\n',
              'dot': 'digraph G { a [label="Hello"]; b [label="World"]; a -> b; }\n',
              'puml': '@startuml\nrectangle "Hello" as a\nrectangle "World" as b\na --> b\n@enduml\n'}
    for suffix, content in inputs.items():
        (smoke / ('smoke.' + suffix)).write_text(content)
    graphviz_backends = {}
    for fmt in ['svg', 'png']:
        for tool, entry in definitions.items():
            out_dir = smoke / tool
            out_dir.mkdir(exist_ok=True)
            output = out_dir / ('smoke.' + fmt)
            argv = entry['argv'][:]
            if entry['kind'] == 'd2':
                argv += [str(smoke / 'smoke.d2'), str(output)]
            elif entry['kind'] == 'mermaid':
                argv += ['-i', str(smoke / 'smoke.mmd'), '-o', str(output), '-c', str(ROOT / 'config/mermaid-dagre.json')]
            elif entry['kind'] == 'graphviz':
                argv += ['-v', '-T' + fmt, str(smoke / 'smoke.dot'), '-o', str(output)]
            else:
                argv += ['-t' + fmt, '-o', str(out_dir), str(smoke / 'smoke.puml')]
            diagnostics = run(argv, env=dict(env, **entry['env']), cwd=tools, log=log)
            if entry['kind'] == 'graphviz':
                expected_backend = 'Using device: png:cairo' if fmt == 'png' else 'Using render: svg:'
                assert expected_backend in diagnostics, f'Unexpected Graphviz {fmt} backend: {diagnostics}'
                graphviz_backends[fmt] = sorted({line.strip() for line in diagnostics.splitlines()
                                                if line.startswith(('Using render:', 'Using device:'))})
            assert output.is_file() and output.stat().st_size > 100, f'Missing smoke output: {output}'
    installed = []
    for record in (java_env / 'conda-meta').glob('*.json'):
        package = json.loads(record.read_text())
        installed.append({key: package.get(key) for key in ['name', 'version', 'build', 'sha256']})
    for package in native:
        actual = next(p for p in installed if p['name'] == package['name'])
        assert actual['version'] == package['version'] and actual['build'] == package['build']
        assert actual['sha256'] == package['sha256']
    manifest = {'schema_version': 1, 'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'platform': target, 'pins': pins, 'lock_hashes': lock_hashes, 'versions': versions,
                'toolchain_sha256': digest(tools / 'toolchain.json'),
                'installed_native_packages': installed, 'graphviz_backends': graphviz_backends,
                'mermaid_browser': {'variant': pins['versions']['browser_variant'], 'headless_mode': mermaid_browser_mode,
                                    'default_verified_from': '@mermaid-js/mermaid-cli/src/index.js'},
                'smoke': 'All four tools rendered SVG and PNG successfully.',
                'font_note': 'Native font and rendering dependencies are pinned in the platform lock. System fonts and macOS CoreText/Linux Fontconfig can still change glyph metrics; record the host OS with each run.',
                'scope': 'Task-local executables and caches; no shell initialization, sudo, global package install, or user conda environment registration.'}
    (tools / 'setup-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Ready: {tools / "toolchain.json"}\nNext: python3 -m benchmarks doctor', flush=True)


def main() -> None:
    if sys.version_info < (3, 11, 9):
        raise SystemExit('Python 3.11.9+ is required (3.12+ recommended).')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools-dir', type=Path, default=ROOT / '.tools')
    parser.add_argument('--cache-dir', type=Path, help='Optional reusable task-local download/build cache')
    args = parser.parse_args()
    tools = args.tools_dir.resolve()
    cache = (args.cache_dir or tools / 'cache').resolve()
    try:
        install(tools, cache)
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == '__main__':
    main()
