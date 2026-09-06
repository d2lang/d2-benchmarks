"""Offline corpus integrity and semantic validation; no renderer is launched."""
from __future__ import annotations

import collections
import hashlib
import html
import json
from pathlib import Path
import re


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corpus_dir(root: Path) -> Path:
    root = Path(root)
    return root if (root / 'manifest.json').is_file() else root / 'corpus'


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def _relative(root, name):
    path = Path(name)
    _check(not path.is_absolute() and '..' not in path.parts, f'Unsafe corpus path: {name}')
    result = (root / path).resolve()
    _check(result.is_relative_to(root.resolve()), f'Corpus path escapes root: {name}')
    return result


def _mermaid_label(text):
    text = text.replace('<br/>', '\n')
    text = re.sub(r'#(\d+|quot);', lambda m: '"' if m[1] == 'quot' else chr(int(m[1])), text)
    return '' if text == '\u00a0' else text


def _plantuml_label(text):
    text = re.sub(r'</?(?:b|i|u|plain)>|<(?:color|size):[^>]+>|</(?:color|size)>', '', text)
    return '\n'.join('' if line == '\u00a0' else line for line in html.unescape(text.replace('\\n', '\n')).split('\n'))


def _dot_attrs(text):
    pattern = r'(\w+)=("(?:\\.|[^"\\])*")'
    attrs = {m[1]: json.loads(m[2]) for m in re.finditer(pattern, text)}
    leftover = re.sub(pattern, '', text).replace(',', '').strip()
    _check(not leftover, 'Unrecognized DOT attribute syntax: ' + leftover)
    return attrs


def _audit_source(kind, text, mapping, translated):
    expected_objects = {o['mermaid_id']: o for o in mapping['objects']}
    expected_edges = mapping['edges']
    objects, edges, stack = {}, [], []
    if kind == 'mermaid':
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith(('%%', 'flowchart ', 'direction ', 'style ', 'linkStyle ')):
                continue
            if line == 'end':
                _check(bool(stack), 'Unbalanced Mermaid group')
                stack.pop(); continue
            group = re.fullmatch(r'subgraph (n\d+)\["([^"]*)"\]', line)
            if group:
                ident, label = group.groups()
                _check(ident not in objects, 'Duplicate Mermaid object ' + ident)
                objects[ident] = ('group', stack[-1] if stack else None, _mermaid_label(label))
                stack.append(ident); continue
            edge = re.fullmatch(r'(n\d+)\s+(<-->|-->|---)(?:\|"([^"]*)"\|)?\s+(n\d+)', line)
            if edge:
                a, arrow, label, b = edge.groups()
                edges.append((a, b, arrow, _mermaid_label(label or ''))); continue
            node = re.fullmatch(r'(n\d+)(?:\[|\[\(|\(\()"([^"]*)"(?:\]|\)\]|\)\))', line)
            if not node:
                node = re.fullmatch(r'(n\d+)@\{ shape: h-cyl, label: "([^"]*)" \}', line)
            _check(node is not None, 'Unrecognized Mermaid source statement: ' + line)
            ident, label = node.groups()
            _check(ident not in objects, 'Duplicate Mermaid object ' + ident)
            objects[ident] = ('node', stack[-1] if stack else None, _mermaid_label(label))
        expected = [(e['mermaid_start_id'], e['mermaid_end_id'], e['mermaid_arrow'], e['translated_label']) for e in expected_edges]
    elif kind == 'plantuml':
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith(("'", '@startuml', '@enduml', 'skinparam ', 'top to bottom direction', 'left to right direction')):
                continue
            if line == '}':
                _check(bool(stack), 'Unbalanced PlantUML group'); stack.pop(); continue
            node = re.fullmatch(r'(?:rectangle|database|queue|person) "([^"]*)" as (n\d+)(?: #[^{}]+)?( \{)?', line)
            if node:
                label, ident, group = node.groups()
                _check(ident not in objects, 'Duplicate PlantUML object ' + ident)
                objects[ident] = ('group' if group else 'node', stack[-1] if stack else None, _plantuml_label(label))
                if group: stack.append(ident)
                continue
            edge = re.fullmatch(r'(n\d+)\s+(<?-)(?:\[[^]]*\])?(-?>?)\s+(n\d+)(?: : (.*))?', line)
            _check(edge is not None, 'Unrecognized PlantUML source statement: ' + line)
            a, left, right, b, label = edge.groups()
            edges.append((a, b, left.startswith('<'), right.endswith('>'), _plantuml_label(label or '')))
        expected = [(e['source_mermaid_id'], e['target_mermaid_id'], e['source_visible_arrow'], e['target_visible_arrow'], e['translated_label']) for e in expected_edges]
    elif kind == 'graphviz':
        ids = {o['d2_id']: ('cluster_' if o['kind'] == 'group' else 'node_') + o['mermaid_id'] for o in mapping['objects']}
        nodes = {}; clusters = {}; dot_edges = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith('//') or line == 'digraph diagram {': continue
            if line == '}':
                if stack: stack.pop()
                continue
            group = re.fullmatch(r'subgraph (cluster_n\d+) \{', line)
            if group:
                ident = group[1]
                _check(ident not in clusters, 'Duplicate DOT cluster')
                clusters[ident] = {'parent': stack[-1] if stack else None}
                stack.append(ident); continue
            defaults = re.fullmatch(r'(graph|node|edge) \[(.*)\];', line)
            if defaults:
                attrs = _dot_attrs(defaults[2])
                if defaults[1] == 'graph' and stack: clusters[stack[-1]].update(attrs)
                continue
            edge = re.fullmatch(r'((?:node|proxy)_n\d+) -> ((?:node|proxy)_n\d+) \[(.*)\];', line)
            if edge:
                dot_edges.append((edge[1], edge[2], _dot_attrs(edge[3]))); continue
            node = re.fullmatch(r'((?:node|proxy)_n\d+) \[(.*)\];', line)
            _check(node is not None, 'Unrecognized DOT statement: ' + line)
            _check(node[1] not in nodes, 'Duplicate DOT node')
            nodes[node[1]] = dict(_dot_attrs(node[2]), parent=stack[-1] if stack else None)
        groups = {o['d2_id'] for o in mapping['objects'] if o['kind'] == 'group'}
        endpoint_groups = {e[k] for e in expected_edges for k in ('source_d2_id', 'target_d2_id') if e[k] in groups}
        proxies = {'proxy_' + o['mermaid_id']: o['d2_id'] for o in mapping['objects'] if o['d2_id'] in endpoint_groups}
        _check(set(clusters) == {ids[o] for o in groups}, 'DOT cluster set differs')
        _check(set(nodes) == {ids[o['d2_id']] for o in mapping['objects'] if o['kind'] == 'node'} | set(proxies), 'DOT nodes/proxies differ')
        for ident, obj in expected_objects.items():
            actual = (clusters if obj['kind'] == 'group' else nodes)[ids[obj['d2_id']]]
            _check(actual['label'] == obj['translated_label'], 'DOT object label differs: ' + ident)
            _check(actual['parent'] == ids.get(obj['parent_d2_id']), 'DOT containment differs: ' + ident)
        for ident, group in proxies.items():
            p = nodes[ident]
            _check(p['style'] == 'invis' and p['label'] == '' and p['parent'] == ids[group], 'DOT representative is visible or in wrong group')
            _check(float(p['width']) <= .011 and float(p['height']) <= .011, 'DOT representative too large')
        _check(len(dot_edges) == len(expected_edges), 'DOT edge count differs')
        for (a,b,attrs), edge in zip(dot_edges, expected_edges):
            for actual_id, logical, group_attr in [(a,edge['source_d2_id'],'ltail'), (b,edge['target_d2_id'],'lhead')]:
                target = ('proxy_' + ids[logical].split('_',1)[1]) if logical in groups else ids[logical]
                _check(actual_id == target, 'DOT endpoint differs')
                _check(attrs.get(group_attr) == (ids[logical] if logical in groups else None), 'DOT logical group endpoint differs')
            _check(attrs['label'] == edge['translated_label'], 'DOT edge label differs')
            _check(attrs['arrowtail'] == ('normal' if edge['source_visible_arrow'] else 'none'), 'DOT source arrow differs')
            _check(attrs['arrowhead'] == ('normal' if edge['target_visible_arrow'] else 'none'), 'DOT target arrow differs')
        return {'objects':len(expected_objects),'edges':len(expected_edges),'synthetic_nodes':len(proxies)}
    else:
        raise ValueError('Unsupported translated source kind: ' + kind)
    _check(not stack, 'Unclosed group')
    _check(set(objects) == set(expected_objects), kind + ' object identity differs')
    for ident, obj in expected_objects.items():
        _check(objects[ident] == (obj['kind'],obj['parent_mermaid_id'],obj['translated_label']), kind + ' object label/kind/containment differs: ' + ident)
    _check(edges == expected, kind + ' edge identity/order/label/direction differs')
    return {'objects':len(objects),'edges':len(edges),'synthetic_nodes':0}


def validate_corpus(root: Path) -> dict:
    """Validate frozen hashes and semantic contents without external executables.

    Accept repository root or its corpus directory. Errors are returned as a
    list, rather than raised, so CLI/report callers can display all failures.
    """
    root = corpus_dir(root)
    errors, cases = [], []
    try:
        manifest = json.loads((root / 'manifest.json').read_text())
        _check(manifest['schema_version'] == 1, 'Unsupported corpus schema')
        fixtures = manifest['fixtures']
        _check(bool(fixtures) and len({f['id'] for f in fixtures}) == len(fixtures), 'Expected nonempty, unique fixtures')
        def check_file(entry):
            path = _relative(root,entry['path'])
            _check(sha256(path) == entry['sha256'], 'SHA-256 mismatch: ' + entry['path'])
            return path
        for entry in manifest['licenses']: check_file(entry)
        verification=json.loads(check_file(manifest['source_verification']).read_text())
        verified={entry['url']:entry['sha256'] for entry in verification['files']}
        for entry in manifest['licenses']:
            if entry.get('origin') == 'generated':
                _check('url' not in entry, 'Generated license must not claim upstream verification')
            else:
                _check(verified.get(entry['url'])==entry['sha256'], 'License verification record differs')
        for document in ('provenance','license_notice'):
            _check(_relative(root,manifest[document]).is_file(), 'Missing corpus documentation')
        for kind,ext in [('d2','d2'),('mermaid','mmd'),('graphviz','dot'),('plantuml','puml')]:
            _check({p.stem for p in (root/kind).glob('*.'+ext)} == {f['id'] for f in fixtures}, 'Incomplete/extra '+kind+' fixture set')
        _check({p.name[:-13] for p in (root/'semantic').glob('*.mapping.json')} == {f['id'] for f in fixtures}, 'Incomplete/extra semantic fixture set')
        for fixture in fixtures:
            try:
                _check(fixture['category'] in ('basic', 'real-world'), 'Unknown workload category')
                mapping_path = check_file(fixture['semantic'])
                m = json.loads(mapping_path.read_text())
                _check(m['fixture'] == fixture['id'], 'Semantic fixture identity differs')
                objects = {o['d2_id']:o for o in m['objects']}
                _check(len(objects) == len(m['objects']), 'Duplicate semantic object')
                _check(len({o['mermaid_id'] for o in m['objects']}) == len(objects), 'Duplicate generated object ID')
                for obj in objects.values():
                    _check(obj['kind'] in ('node','group'), 'Unknown semantic object kind')
                    _check(obj['parent_mermaid_id'] == (objects[obj['parent_d2_id']]['mermaid_id'] if obj['parent_d2_id'] else None), 'Generated parent ID differs from semantic parent')
                    parent = obj['parent_d2_id']; visited = {obj['d2_id']}
                    while parent:
                        _check(parent in objects and parent not in visited, 'Invalid/cyclic parent')
                        _check(objects[parent]['kind'] == 'group', 'Parent is not a group')
                        visited.add(parent);parent=objects[parent]['parent_d2_id']
                    _check(not obj['source_attributes'].get('icon'), 'Runtime image dependency in D2 attributes')
                    _check(obj['source_shape'] != 'image', 'Runtime image shape dependency')
                _check(len({e['d2_id'] for e in m['edges']}) == len(m['edges']), 'Duplicate semantic edge ID')
                for edge in m['edges']:
                    _check(edge['source_d2_id'] in objects and edge['target_d2_id'] in objects, 'Missing edge endpoint')
                counts = {'leaf_nodes':sum(o['kind']=='node' for o in objects.values()),'groups':sum(o['kind']=='group' for o in objects.values()),'edges':len(m['edges'])}
                _check(counts == fixture['counts'], 'Semantic counts differ')
                _check(fixture['png_density'] == (.5 if fixture['id']=='tpmjs_architecture' else 2.0), 'Unexpected raster density')
                _check(fixture['primary_png'] == (fixture['id']!='tpmjs_architecture'), 'Unexpected PNG aggregate membership')
                inputs = {kind:check_file(entry) for kind,entry in fixture['inputs'].items()}
                _check(set(inputs) == {'d2','mermaid','graphviz','plantuml'}, 'Missing source format')
                _check(sha256(inputs['d2']) == m['source_sha256'], 'D2 source not tied to semantic mapping')
                _check(sha256(inputs['mermaid']) == m['mermaid_sha256'], 'Mermaid source not tied to semantic mapping')
                translations={kind:json.loads(check_file(entry).read_text()) for kind,entry in fixture['translations'].items()}
                for kind,translated in translations.items():
                    translated_objects={o['d2_id']:o for o in translated['objects']}
                    _check(set(translated_objects)==set(objects), kind+' mapping identities differ')
                    for ident,obj in objects.items():
                        actual=translated_objects[ident]
                        _check((actual['parent_d2_id'],actual['kind'],actual['label' if kind=='graphviz' else 'translated_label']) == (obj['parent_d2_id'],obj['kind'],obj['translated_label']),kind+' mapping object semantics differ')
                    _check(len(translated['edges'])==len(m['edges']),kind+' mapping edge count differs')
                    for actual,edge in zip(translated['edges'],m['edges']):
                        _check(all(actual[k]==edge[k] for k in ('index','d2_id','source_d2_id','target_d2_id','source_visible_arrow','target_visible_arrow')),kind+' mapping edge semantics differ')
                        _check(actual['label' if kind=='graphviz' else 'translated_label']==edge['translated_label'],kind+' mapping edge label differs')
                audits={kind:_audit_source(kind,inputs[kind].read_text(),m,translations.get(kind)) for kind in ('mermaid','graphviz','plantuml')}
                for kind,path in inputs.items():
                    text=path.read_text()
                    if kind=='d2':
                        _check(not re.search(r'(?m)^\s*[^#\n]*(?:icon\s*:|shape\s*:\s*image\b)', text), 'D2 runtime image directive')
                        _check(not re.search(r'(?m)^\s*(?:\.\.\.)?@',text), 'D2 runtime import')
                    elif kind=='graphviz':_check(not re.search(r'\b(?:image|shapefile)\s*=',text),'Graphviz external image')
                    elif kind=='plantuml':_check(not re.search(r'(?mi)^\s*!|<img\b|\[\[https?://',text),'PlantUML runtime include/image')
                    elif kind=='mermaid':_check(not re.search(r'(?mi)^\s*(?:click|accTitle|accDescr)\s|@\{[^}]*\bimg\s*:',text),'Mermaid runtime directive')
                source=fixture['source']
                if source.get('kind') == 'generated':
                    _check(fixture['category'] == 'basic', 'Generated source category differs')
                    check_file(source['generator'])
                    _check(source['model'] == 'balanced-binary-tree', 'Unknown generated graph model')
                    _check(source['nodes'] == counts['leaf_nodes'] and counts['groups'] == 0 and
                           counts['edges'] == source['nodes'] - 1, 'Generated graph dimensions differ')
                    _check('url' not in source and 'revision' not in source,
                           'Generated source must not claim upstream verification')
                else:
                    _check(fixture['category'] == 'real-world', 'Upstream source category differs')
                    _check(re.fullmatch(r'[0-9a-f]{40}',source['revision']) is not None,'Upstream revision is not pinned')
                    _check(verified.get(source['url'])==source['original_sha256'],'Upstream source verification differs')
                _check(source['license'] in ('MIT','Apache-2.0'),'Unrecognized source license')
                for license_path in fixture['source']['license_files']:
                    _check(any(e['path']==license_path for e in manifest['licenses']), 'Missing fixture license')
                cases.append({'id':fixture['id'],'category':fixture['category'],'counts':counts,'source_audits':audits})
            except (KeyError, ValueError, OSError, TypeError) as exc:
                errors.append(fixture['id']+': '+str(exc))
        totals={key:sum(case['counts'][key] for case in cases) for key in ('leaf_nodes','groups','edges')}
    except (KeyError, ValueError, OSError, TypeError) as exc:
        errors.append(str(exc));totals={}
    return {'schema_version':1,'valid':not errors,'errors':errors,'fixtures':cases,'totals':totals,'network_required':False}


def validate_svg(path: Path, fixture_id: str, kind: str, corpus_root: Path) -> dict:
    """Render audit; imported lazily to keep offline corpus checks lightweight."""
    from .svg_validation import validate_svg as audit
    return audit(path,fixture_id,kind,corpus_dir(corpus_root))
