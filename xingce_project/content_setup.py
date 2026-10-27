"""Local diagnostics and bounded ZIP import; never downloads content."""
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

def diagnose(root):
    root=Path(root)
    checks=[]
    pointer=root/'current.json'
    if not pointer.is_file():
        return [{'ok':False,'item':'current.json','action':'缺少内容指针；请从可信私有内容包导入 releases。公开源码不带真实练习内容。'}]
    try:
        data=json.loads(pointer.read_text(encoding='utf-8'));version=data['version']
        if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*',version):raise ValueError('非法版本名')
        release=root/version
        for name in ['manifest.json','content.sqlite','questions.jsonl','occurrences.jsonl','papers.jsonl','annotations.jsonl']:
            checks.append({'ok':(release/name).is_file(),'item':name,'action':'保留可信包内完整 releases 布局，不要只复制数据库。'})
    except (OSError,ValueError,KeyError,TypeError) as exc:
        checks.append({'ok':False,'item':'current.json','action':str(exc)})
    return checks

def import_zip(archive, root):
    from pipeline.release import validate_release, import_release, activate_release
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    # Extract only an allowlisted subtree; source and personal files are never restored.
    with tempfile.TemporaryDirectory(prefix='.import-',dir=root) as temp, zipfile.ZipFile(archive) as z:
        base=Path(temp);total=0
        for entry in z.infolist():
            name=entry.filename;parts=PurePosixPath(name).parts
            if '\\' in name or name.startswith('/') or any(':' in p for p in parts) or '..' in parts or stat.S_ISLNK(entry.external_attr>>16):
                raise ValueError('不安全 ZIP 路径或符号链接')
            if not name.startswith('xingce_project/releases/'):continue
            rel=parts[2:]
            if not rel:continue
            total+=entry.file_size
            if total>4*1024**3:raise ValueError('解压大小超过4GiB边界')
            target=base.joinpath(*rel)
            if entry.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(entry) as src, target.open('xb') as dest:shutil.copyfileobj(src,dest)
        pointer=json.loads((base/'current.json').read_text(encoding='utf-8'));version=pointer['version']
        if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*',version):raise ValueError('非法版本')
        source=base/version
        if not source.is_dir() or (root/version).exists():raise ValueError('包缺少当前版本，或同版本已存在（禁止覆盖）')
        manifest=validate_release(source)
        if manifest['version']!=version:raise ValueError('manifest版本不符')
        from pipeline.release import digest
        if pointer.get('manifest_sha256')!=digest(source/'manifest.json'):raise ValueError('指针哈希不符')
        import_release(source,root,activate=False)
        activate_release(root,version)
        return version
