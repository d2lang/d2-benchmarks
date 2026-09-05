"""Portable post-render SVG checks, with no external process or network access.

These are version-sensitive structural checks against the frozen semantic graph.
A new renderer's serialization may require updating an adapter; unsupported
output must fail visibly instead of silently weakening the comparison.
"""
from __future__ import annotations
import base64
import collections
import hashlib
import html
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def local(tag): return tag.rsplit('}',1)[-1]
def normal(text): return re.sub(r'\s+',' ',text.replace('\u00a0',' ')).strip()
def text_content(element):
    out=element.text or ''
    for child in element:
        out+= ('\n' if local(child.tag)=='br' else text_content(child)) + (child.tail or '')
    return out

def visible_text(element): return ' '.join(''.join(x.itertext()) for x in element.iter() if local(x.tag)=='text')
def finite_path(element): return bool(element.get('d')) and not re.search(r'NaN|Infinity|undefined',element.get('d',''))
def fail(errors, condition, text):
    if not condition:errors.append(text)


def d2(svg,m,errors):
    objects={o['d2_id'] for o in m['objects']};edges={e['d2_id'] for e in m['edges']};counts=collections.Counter()
    for element in svg.iter():
        if local(element.tag)!='g':continue
        for token in element.get('class','').split():
            try:ident=html.unescape(base64.b64decode(token,altchars=b'-_',validate=True).decode())
            except (ValueError,UnicodeError):continue
            if ident not in objects|edges:continue
            counts[ident]+=1
            if ident in edges:
                paths=[p for p in element.iter() if local(p.tag)=='path' and 'connection' in p.get('class','').split()]
                fail(errors, bool(paths) and all(finite_path(p) for p in paths), 'Missing/invalid D2 connection path: '+ident)
    for ident in objects|edges:fail(errors,counts[ident]==1,f'D2 wrapper multiplicity {ident}: {counts[ident]} != 1')
    return ['D2 semantic object/edge wrapper identities and multiplicity','finite D2 connection paths']


def mermaid(svg,m,errors):
    nodes=[];groups=[];edges=[];labels={};edge_labels={};edge_ids=[];edge_details=[]
    def label(element,kind):
        wanted='cluster-label' if kind=='group' else 'label'
        for child in element.iter():
            if wanted in child.get('class','').split():return normal(text_content(child))
        return ''
    for element in svg.iter():
        classes=element.get('class','').split();ident=element.get('id','')
        for kind,cls,regex,bucket in [('node','node',r'flowchart-(n\d+)-',nodes),('group','cluster',r'-(n\d+)$',groups)]:
            if cls in classes:
                match=re.search(regex,ident)
                if not match:errors.append('Unrecognized Mermaid object id: '+ident);continue
                bucket.append(match[1]);labels[match[1]]=label(element,kind)
        if 'label' in classes and element.get('data-id','').startswith('L_'):
            edge_labels[element.get('data-id')]=normal(text_content(element))
        if element.get('data-edge')=='true':
            eid=element.get('data-id','');edge_ids.append(eid)
            match=re.fullmatch(r'L_(n\d+)_(n\d+)_(\d+)',eid)
            if match:
                item=(match[1],match[2],bool(element.get('marker-start')),bool(element.get('marker-end')))
                edges.append(item);edge_details.append((eid,item))
            else:errors.append('Unrecognized Mermaid edge id: '+eid)
            fail(errors,finite_path(element),'Invalid Mermaid route: '+eid)
    fail(errors, sorted(nodes)==sorted(o['mermaid_id'] for o in m['objects'] if o['kind']=='node'),'Mermaid leaf identities/multiplicity differ')
    fail(errors, sorted(groups)==sorted(o['mermaid_id'] for o in m['objects'] if o['kind']=='group'),'Mermaid group identities/multiplicity differ')
    expected=[];expected_labeled=[]
    for edge in m['edges']:
        a,b=edge['mermaid_start_id'],edge['mermaid_end_id'];sa,ta=edge['source_visible_arrow'],edge['target_visible_arrow']
        if sa and not ta:sa,ta=False,True
        expected.append((a,b,sa,ta));expected_labeled.append((a,b,sa,ta,normal(edge['translated_label'])))
    fail(errors,collections.Counter(edges)==collections.Counter(expected),'Mermaid endpoint/multiplicity/arrow mismatch')
    fail(errors,len(edge_ids)==len(set(edge_ids)),'Duplicate Mermaid edge id')
    actual_labeled=[(*item,edge_labels.get(eid,'')) for eid,item in edge_details]
    fail(errors,collections.Counter(actual_labeled)==collections.Counter(expected_labeled),'Mermaid rendered edge labels/endpoints/arrows differ')
    for obj in m['objects']:fail(errors,labels.get(obj['mermaid_id'],'')==normal(obj['translated_label']),'Mermaid rendered object label differs: '+obj['d2_id'])
    return ['Mermaid object/edge identities and multiplicity','Mermaid object/edge plaintext labels','Mermaid endpoint arrows and finite routes']


def graphviz(svg,m,translated,errors):
    groups=[x for x in svg.iter() if local(x.tag)=='g'];by_id={x.get('id'):x for x in groups if x.get('id')}
    object_ids={o['dot_id'] for o in translated['objects']};edge_ids={e['dot_id'] for e in translated['edges']}
    fail(errors,{x.get('id') for x in groups if x.get('class') in ('node','cluster')}==object_ids,'Graphviz object identities differ')
    fail(errors,{x.get('id') for x in groups if x.get('class')=='edge'}==edge_ids,'Graphviz edge identities differ')
    fail(errors,len([x for x in groups if x.get('class') in ('node','cluster')])==len(object_ids),'Graphviz object multiplicity differs')
    fail(errors,len([x for x in groups if x.get('class')=='edge'])==len(edge_ids),'Graphviz edge multiplicity differs')
    for proxy in translated['synthetic_nodes']:fail(errors,proxy['dot_id'] not in by_id,'Visible Graphviz endpoint proxy')
    for obj in translated['objects']+translated['edges']:
        ident=obj['dot_id'];element=by_id.get(ident)
        if element is None:errors.append('Missing Graphviz element '+ident);continue
        texts=[''.join(x.itertext()).replace('\u00a0',' ') for x in element.iter() if local(x.tag)=='text']
        expected=[x.replace('\u00a0',' ') for x in obj['label'].split('\n') if x]
        fail(errors,texts==expected,'Graphviz rendered text differs: '+ident)
        if ident in edge_ids:
            title=next((x.text for x in element if local(x.tag)=='title'),'')
            fail(errors,title==obj['actual_source']+'->'+obj['actual_target'],'Graphviz rendered endpoints differ: '+ident)
            paths=[x for x in element.iter() if local(x.tag)=='path']
            fail(errors,bool(paths) and all(finite_path(x) for x in paths),'Graphviz route invalid: '+ident)
            arrow_count=sum(local(x.tag)=='polygon' for x in element.iter())
            fail(errors,arrow_count==int(obj['source_visible_arrow'])+int(obj['target_visible_arrow']),'Graphviz enabled arrow geometry differs: '+ident)
    return ['Graphviz object/edge identities and multiplicity','Graphviz exact rendered plaintext labels','Graphviz endpoint proxies absent from SVG','Graphviz endpoints, enabled arrow geometry and finite routes']


def plantuml(svg,m,translated,errors,source):
    fail(errors,svg.get('data-diagram-type')=='DESCRIPTION','PlantUML output is not a deployment diagram')
    entities=[x for x in svg.iter() if x.get('class') in ('entity','cluster')];links=[x for x in svg.iter() if x.get('class')=='link']
    objects={o['plantuml_id']:o for o in translated['objects']}
    by_alias={x.get('data-qualified-name','').split('.')[-1]:x for x in entities}
    id_alias={x.get('id'):x.get('data-qualified-name','').split('.')[-1] for x in entities}
    fail(errors,set(by_alias)==set(objects) and len(entities)==len(objects),'PlantUML entity identities/multiplicity differ')
    fail(errors,len(links)==len(translated['edges']),'PlantUML edge count differs')
    for ident,obj in objects.items():
        element=by_alias.get(ident)
        if element is None:continue
        parts=element.get('data-qualified-name','').split('.');parent=parts[-2] if len(parts)>1 else None
        fail(errors,parent==obj['parent_plantuml_id'],'PlantUML containment differs: '+ident)
        kind='group' if element.get('class')=='cluster' else 'node'
        fail(errors,kind==obj['kind'],'PlantUML entity kind differs: '+ident)
        fail(errors,normal(visible_text(element))==normal(obj['translated_label']),'PlantUML rendered object label differs: '+ident)
    edge_lines=[i for i,line in enumerate(source.splitlines()) if re.match(r'n\d+\s+[<-]',line)]
    fail(errors,len(edge_lines)==len(translated['edges']),'PlantUML source edge count differs')
    by_line={int(x.get('data-source-line','-1')):x for x in links}
    fail(errors,len(by_line)==len(links),'PlantUML duplicate rendered link source identity')
    for line,edge in zip(edge_lines,translated['edges']):
        element=by_line.get(line)
        if element is None:errors.append('PlantUML missing edge source line '+str(line));continue
        fail(errors,[id_alias.get(element.get('data-entity-1')),id_alias.get(element.get('data-entity-2'))]==[edge['source_plantuml_id'],edge['target_plantuml_id']],'PlantUML edge endpoints differ: '+str(line))
        fail(errors,normal(visible_text(element))==normal(edge['translated_label']),'PlantUML rendered edge label differs: '+str(line))
        polygons=[x for x in element.iter() if local(x.tag)=='polygon']
        transparent=(edge['source_attributes'].get('style',{}).get('stroke') or {}).get('value')=='transparent'
        expected=0 if transparent else int(edge['source_visible_arrow'])+int(edge['target_visible_arrow'])
        fail(errors,len(polygons)==expected,'PlantUML painted arrow count differs: '+str(line))
        paths=[x for x in element.iter() if local(x.tag)=='path']
        # PlantUML omits the painted route for its transparent layout-only link.
        fail(errors,transparent or (bool(paths) and all(finite_path(x) for x in paths)),'PlantUML invalid route: '+str(line))
        if expected==1 and len(polygons)==1 and paths:
            nums=lambda text:[float(x) for x in re.findall(r'[-+]?(?:\d*\.)?\d+(?:[eE][-+]?\d+)?',text)]
            points=nums(paths[0].get('d',''));poly=nums(polygons[0].get('points',''))
            if points and poly:
                center=(sum(poly[::2])/(len(poly)/2),sum(poly[1::2])/(len(poly)/2))
                fail(errors,(math.dist(center,points[:2])<math.dist(center,points[-2:]))==edge['source_visible_arrow'],'PlantUML arrow at incorrect endpoint: '+str(line))
    return ['PlantUML entity/edge identities and multiplicity','PlantUML immediate containment','PlantUML rendered plaintext labels','PlantUML endpoint arrows and finite painted routes']


def validate_svg(path: Path, fixture_id: str, kind: str, corpus_root: Path) -> dict:
    errors=[];checks=[];result={'fixture':fixture_id,'kind':kind,'errors':errors,'checks':checks}
    try:
        root=Path(corpus_root);kind=kind.split('-')[0]
        content=Path(path).read_bytes();result['sha256']=hashlib.sha256(content).hexdigest()
        svg=ET.fromstring(content)
        fail(errors,local(svg.tag)=='svg','Output is not SVG')
        fail(errors,svg.get('data-diagram-type')!='ERROR','PlantUML error SVG')
        m=json.loads((root/'semantic'/(fixture_id+'.mapping.json')).read_text())
        if kind=='d2':checks.extend(d2(svg,m,errors))
        elif kind=='mermaid':checks.extend(mermaid(svg,m,errors))
        elif kind in ('graphviz','plantuml'):
            translated=json.loads((root/'semantic'/kind/(fixture_id+'.mapping.json')).read_text())
            if kind=='graphviz':checks.extend(graphviz(svg,m,translated,errors))
            else:checks.extend(plantuml(svg,m,translated,errors,(root/'plantuml'/(fixture_id+'.puml')).read_text()))
        else:errors.append('Unsupported SVG kind: '+kind)
    except (OSError,ValueError,KeyError,TypeError,ET.ParseError) as exc:errors.append(str(exc))
    result['valid']=not errors
    return result
