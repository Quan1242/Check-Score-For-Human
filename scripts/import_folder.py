"""Upload assets and M49 bundles without extra dependencies.

python scripts/import_folder.py --project PROJECT_ID --data data/pilot
Directory layout: assets/*, ground_truth/*.json, ai/*.json.
"""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def request(url, data=None, content_type=None):
    req = Request(url, data=data, headers={'Content-Type': content_type} if content_type else {})
    try:
        with urlopen(req, timeout=120) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f'{exc.code}: {exc.read().decode("utf-8", errors="replace")}') from exc


def upload(url, path):
    if path.stat().st_size > 32*1024*1024:
        raise ValueError(f'Tệp quá 32 MiB: {path.name}')
    boundary = uuid4().hex
    if any(c in path.name for c in '\r\n"'):
        raise ValueError('Tên file chứa ký tự không hỗ trợ trong multipart')
    header = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    body = header.encode() + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    return request(url, body, f'multipart/form-data; boundary={boundary}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default='http://127.0.0.1:8000/api')
    parser.add_argument('--project', required=True)
    parser.add_argument('--data', required=True, type=Path)
    parser.add_argument('--skip-existing-assets', action='store_true', help='Skip by filename; does not compare file content')
    args = parser.parse_args()
    root = args.data.resolve()
    if not root.is_dir():
        parser.error('Thư mục dữ liệu không tồn tại')
    base = f'{args.api.rstrip("/")}/projects/{args.project}'
    known = {a['name'] for a in request(base+'/assets')}
    for folder, endpoint in [('assets', 'assets'), ('ground_truth', 'imports/ground_truth'), ('ai', 'imports/ai')]:
        for path in sorted((root/folder).glob('*')):
            if not path.is_file():
                continue
            if folder != 'assets' and path.suffix.lower() != '.json':
                continue
            if folder == 'assets' and args.skip_existing_assets and path.name in known:
                print(f'SKIP {path.name} (đã có tên này)')
                continue
            result = upload(base+'/'+endpoint, path)
            print(f'OK {folder}/{path.name}: {result.get("id")}')


if __name__ == '__main__':
    main()
