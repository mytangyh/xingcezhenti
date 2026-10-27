#!/usr/bin/env python3
"""Allowlisted private delivery; never traverse personal/assessment directories."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.release import validate_release, digest

DENIED = {'node_modules', '.npm-cache', '__pycache__', '.git', '.venv', 'userdata', 'runtime', 'sealed_assessment', 'verification_input', 'holdout', 'blind50', 'language_blind16', 'math_blind10', 'reasoning_blind22'}
SUFFIXES = {'.py', '.json', '.md', '.ts', '.tsx', '.css', '.html', '.mjs', '.mts', '.svg', '.txt', '.js'}

def safe(path):
    return not any(p in DENIED or p.startswith('.env') or 'parent_mapping' in p or 'sealed_answers' in p for p in path.parts)

def source_files():
    # Public project documentation only; private review notes are not required inputs.
    files = [ROOT / n for n in ('start_workbench.py', 'README.md', 'DELIVERY_README.md', 'VALIDATION.md') if (ROOT / n).is_file()]
    for folder in ('pipeline', 'schemas', 'taxonomies', 'apps/workbench/backend', 'apps/workbench/frontend', 'tests_backend', 'tests_pipeline', 'tests_acceptance', 'tools'):
        base = ROOT / folder
        for p in sorted(base.rglob('*')):
            rel = p.relative_to(ROOT)
            if p.is_file() and not p.is_symlink() and safe(rel) and p.suffix in SUFFIXES:
                # Test outputs and provenance rows are not code. Top-level pipeline code only;
                # frozen publication input requires an independently approved explicit inventory.
                if folder == 'pipeline' and p.parent != base:
                    continue
                if folder.startswith('tests') and p.suffix != '.py':
                    continue
                if folder == 'tools' and p.name not in ('package_delivery.py','export_study_guide.py'):
                    continue
                files.append(p)
    return sorted(set(files))

def write_zip(target, entries, extras):
    if target.exists():
        raise ValueError(f'Refusing to overwrite delivery: {target}')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for p, name in entries:
            if p.is_symlink() or not safe(Path(name)):
                raise ValueError(f'Forbidden file {name}')
            z.write(p, name)
        for name, data in extras.items():
            z.writestr(name, data)
    with zipfile.ZipFile(target) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f'ZIP CRC failed: {bad}')
        if any(not safe(Path(n)) for n in z.namelist()):
            raise ValueError('Excluded private path in ZIP')
    return {'filename':target.name,'sha256':digest(target),'bytes':target.stat().st_size,'members':len(entries)+len(extras)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--version', required=True, help='Explicit accepted current version; no inferred final version')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--approved-summary', type=Path, required=True, help='Reviewed sanitized acceptance Markdown')
    ap.add_argument('--dry-run', action='store_true')
    args=ap.parse_args()
    version=args.version
    if Path(version).name != version or '\\' in version or version.startswith('.'):
        raise ValueError('Unsafe version')
    pointer=json.loads((ROOT/'releases/current.json').read_text())
    if pointer['version'] != version or pointer['path'] != version:
        raise ValueError('Requested version is not the activated current release')
    release=ROOT/'releases'/version
    if digest(release/'manifest.json') != pointer['manifest_sha256']:
        raise ValueError('Current manifest hash mismatch')
    manifest=validate_release(release)
    if manifest['version'] != version:
        raise ValueError('Manifest version mismatch')
    if not (ROOT/'apps/workbench/frontend/dist/index.html').is_file():
        raise ValueError('Missing prebuilt dist')
    summary=args.approved_summary.read_text(encoding='utf-8')
    if not summary.strip():raise ValueError('Empty acceptance summary')
    sources=source_files()
    payload=[(release/n, f'xingce_project/releases/{version}/{n}') for n in sorted(manifest['files'])]
    payload += [(release/'manifest.json',f'xingce_project/releases/{version}/manifest.json'),(ROOT/'releases/current.json','xingce_project/releases/current.json')]
    if any(not safe(Path(name)) for _,name in payload):raise ValueError('Forbidden content path')
    record={'release':version,'manifest_sha256':pointer['manifest_sha256'],'counts':manifest['counts'],
      'human_formal_reviews':0,'human_formally_approved_cards':0,'real_user_scores':0,'external_api_calls':0,
      'source_file_count':len(sources),'content_file_count':len(payload),
      'source_files_sha256':{p.relative_to(ROOT).as_posix():digest(p) for p in sources},
      'privacy':'No personal runtime DB, sealed assessment answers or parent mappings',
      'licensing':'Source questions/images: private study only; license unconfirmed',
      'platform':'Cloud Linux tested; user Windows not actually tested',
      'offline':'Application-level external-network-denial simulation only; browser public network disconnect not tested'}
    if args.dry_run:
        print(json.dumps(record,ensure_ascii=False,indent=2));return
    args.output.mkdir(parents=True,exist_ok=True)
    extras={'xingce_project/DELIVERY_RECEIPT.json':json.dumps(record,ensure_ascii=False,indent=2),'xingce_project/DELIVERY_ACCEPTANCE.md':summary}
    outputs=[]
    outputs.append(write_zip(args.output/f'xingce-source-{version}.zip',[(p,'xingce_project/'+p.relative_to(ROOT).as_posix()) for p in sources],extras))
    outputs.append(write_zip(args.output/f'xingce-content-{version}.zip',payload,extras))
    record['archives']=outputs
    (args.output/'DELIVERY_RECEIPT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'DELIVERY_ACCEPTANCE.md').write_text(summary,encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
