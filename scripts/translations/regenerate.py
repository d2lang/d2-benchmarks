#!/usr/bin/env python3
"""Regenerate all three translations from frozen semantic maps into a NEW folder.

No network, D2 install, Java, browser or Graphviz is required. The source maps
contain D2 compiler-expanded IDs, attributes, parent relationships and arrows.
Use export.go when rebuilding those maps from a different D2 compiler/input.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,default=Path(__file__).resolve().parents[2]/'corpus')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Output already exists; choose a new directory')
    args.output.mkdir(parents=True)
    scripts=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='d2-bench-translations-') as tmp:
        tmp=Path(tmp);graphs=tmp/'compiled';graphs.mkdir();fixtures=tmp/'fixtures';fixtures.mkdir()
        (fixtures/'REAL_WORLD.md').write_text('See corpus/PROVENANCE.md.\n')
        (fixtures/'real_world_licenses').mkdir()
        for mapping_path in sorted((args.corpus/'semantic').glob('*.mapping.json')):
            m=json.loads(mapping_path.read_text());objects=sorted(m['objects'],key=lambda o:o['mermaid_id'])
            compiled_objects=[{'id':o['d2_id'],'parent':o['parent_d2_id'],'children':[c['d2_id'] for c in objects if c['parent_d2_id']==o['d2_id']],'attributes':o['source_attributes']} for o in objects]
            compiled_edges=[{'id':e['d2_id'],'source':e['source_d2_id'],'target':e['target_d2_id'],'source_arrow':e['source_arrow_token'],'target_arrow':e['target_arrow_token'],'attributes':e['source_attributes'],'source_arrowhead':e['source_arrowhead'],'target_arrowhead':e['target_arrowhead']} for e in m['edges']]
            graph={'source':m['fixture']+'.d2','root_attributes':m['root_attributes'],'config':m['source_config'],'objects':compiled_objects,'edges':compiled_edges}
            (graphs/(m['fixture']+'.d2.graph.json')).write_text(json.dumps(graph))
            shutil.copyfile(args.corpus/'d2'/(m['fixture']+'.d2'),fixtures/(m['fixture']+'.d2'))
        subprocess.run([sys.executable,str(scripts/'mermaid_from_compiler.py'),str(graphs),str(fixtures),str(tmp/'mermaid')],check=True,stdout=subprocess.DEVNULL)
        (args.output/'mermaid').mkdir()
        for p in (tmp/'mermaid').glob('*.mmd'):shutil.copyfile(p,args.output/'mermaid'/p.name)
    subprocess.run([sys.executable,str(scripts/'graphviz.py'),'--source',str(args.corpus/'semantic'),'--output',str(args.output/'graphviz')],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(scripts/'plantuml.py'),str(args.corpus/'semantic'),str(args.output/'plantuml')],check=True,stdout=subprocess.DEVNULL)
    manifest=json.loads((args.corpus/'manifest.json').read_text());checks=[]
    for fixture in manifest['fixtures']:
        for kind,ext in [('mermaid','mmd'),('graphviz','dot'),('plantuml','puml')]:
            output=args.output/kind/(fixture['id']+'.'+ext)
            actual=hashlib.sha256(output.read_bytes()).hexdigest();expected=fixture['inputs'][kind]['sha256']
            checks.append({'fixture':fixture['id'],'kind':kind,'sha256':actual,'matches_frozen':actual==expected})
    report={'schema_version':1,'valid':all(c['matches_frozen'] for c in checks),'checks':checks}
    (args.output/'regeneration-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'valid':report['valid'],'inputs_checked':len(checks)},indent=2))
    raise SystemExit(not report['valid'])


if __name__=='__main__':main()
