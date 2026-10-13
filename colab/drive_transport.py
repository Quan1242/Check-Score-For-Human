"""Shared by generated notebook cells; stdlib only, testable without Colab."""
import hashlib
import json
from pathlib import Path


def load_drive_job(root, task):
    root = Path(root)
    request = json.loads((root/'request.json').read_text(encoding='utf-8'))
    if request['task'] != task or root.name != request['job_id']:
        raise ValueError('Sai notebook hoặc sai thư mục lượt chạy')
    names = request['manifest']
    if not isinstance(names, list) or not 1 <= len(names) <= 20 or len(names) != len(set(names)):
        raise ValueError('Manifest không hợp lệ')
    for name in names:
        if not isinstance(name, str) or not name or '/' in name or '\\' in name or ':' in name or name in {'.', '..'}:
            raise ValueError('Tên mẫu không hợp lệ')
        path = root/'assets'/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != request['sha256'].get(name):
            raise ValueError(f'{name}: chờ Drive đồng bộ đủ dữ liệu rồi chạy lại')
    return request


def publish_drive_result(root, request, bundle, timing, environment):
    root = Path(root)
    if root.name != request['job_id'] or bundle['task'] != request['task']:
        raise ValueError('Sai lượt chạy hoặc tác vụ')
    if sorted(s['asset_name'] for s in bundle['samples']) != sorted(request['manifest']):
        raise ValueError('Kết quả thiếu/trùng/thừa mẫu')
    if (root/'result.ready.json').exists():
        raise ValueError('Lượt này đã xuất kết quả. Tạo lượt mới trong ứng dụng để chạy lại.')
    raw = json.dumps(bundle, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')
    if len(raw) > 32*1024*1024:
        raise ValueError('Kết quả vượt 32 MiB')
    outputs = {'predictions.json': raw,
               'timing.json': json.dumps(timing, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8'),
               'environment.txt': environment.encode('utf-8')}
    for name, data in outputs.items():
        temporary = root/(name+'.tmp')
        temporary.write_bytes(data)
        temporary.replace(root/name)
    receipt = {'job_id': request['job_id'], 'sha256': hashlib.sha256(raw).hexdigest()}
    temporary = root/'result.ready.tmp'
    temporary.write_text(json.dumps(receipt), encoding='utf-8')
    temporary.replace(root/'result.ready.json')
    return receipt
