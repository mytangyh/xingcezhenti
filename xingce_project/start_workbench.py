#!/usr/bin/env python3
"""Portable, loopback-only launcher. No provider credentials or Node required."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Backend release-management endpoints import the canonical package name.
sys.path.insert(0, str(ROOT.parent))

def check_release(releases):
    from pipeline.release import digest, validate_release
    releases = Path(releases).resolve()
    pointer = json.loads((releases / 'current.json').read_text(encoding='utf-8'))
    version = pointer['version']
    if not version or Path(version).name != version or '\\' in version or version.startswith('.'):
        raise ValueError('Unsafe release version')
    path = (releases / pointer['path']).resolve()
    if path.parent != releases or path.name != version or path.is_symlink():
        raise ValueError('Release pointer escapes releases directory')
    if digest(path / 'manifest.json') != pointer.get('manifest_sha256'):
        raise ValueError('Current pointer manifest hash mismatch')
    manifest = validate_release(path)
    if manifest['version'] != version:
        raise ValueError('Manifest version differs from pointer')
    if not (ROOT / 'apps/workbench/frontend/dist/index.html').is_file():
        raise ValueError('Frontend missing; run npm ci && npm run build in apps/workbench/frontend (see README.md)')
    return manifest

def main():
    parser = argparse.ArgumentParser(description='行测私人学习工作台（仅本机访问）')
    parser.add_argument('--check', action='store_true', help='校验内容包后退出，不启动服务、不创建个人数据')
    parser.add_argument('--releases', type=Path, default=ROOT / 'releases')
    parser.add_argument('--userdata', type=Path, default=ROOT / 'userdata')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be in 1..65535')
    try:
        manifest = check_release(args.releases)
    except (OSError, ValueError, KeyError) as exc:
        print(f'数据校验失败：{exc}', file=sys.stderr)
        return 2
    print(json.dumps({'release': manifest['version'], 'integrity': 'passed', 'counts': manifest['counts']}, ensure_ascii=False))
    if args.check:
        return 0
    os.environ['XINGCE_RELEASES'] = str(args.releases.resolve())
    os.environ['XINGCE_USERDATA'] = str(args.userdata.resolve())
    try:
        import uvicorn
        from xingce_project.apps.workbench.backend.app import app
    except ImportError as exc:
        print(f'缺少运行依赖：{exc}。请按 DELIVERY_README.md 安装官方 requirements。', file=sys.stderr)
        return 3
    print(f'打开 http://127.0.0.1:{args.port} ；退出请按 Ctrl+C。')
    uvicorn.run(app, host='127.0.0.1', port=args.port, workers=1, reload=False)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
