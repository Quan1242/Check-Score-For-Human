"""Select a reproducible 20-image demo plus 3 pilot images from preclassified candidates.

Input JSON: {"easy": ["a.jpg", ...], "medium": [...], "hard": [...]}.
Classify candidates before looking at AI results. This script does not download data.
"""
import argparse
import json
import random
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwrites an existing run')
    parser.add_argument('--seed', type=int, default=49)
    args = parser.parse_args()
    buckets = json.loads(args.candidates.read_text(encoding='utf-8-sig'))
    quotas = {'easy': 6, 'medium': 8, 'hard': 6}
    if not isinstance(buckets, dict) or set(buckets) != set(quotas):
        parser.error('Cần đúng ba nhóm easy, medium, hard')
    seen, main_names, pilot, strata = set(), [], [], {}
    rng = random.Random(args.seed)
    root = args.images.resolve()
    for difficulty, count in quotas.items():
        names = buckets[difficulty]
        if not isinstance(names, list) or len(names) < count+1:
            parser.error(f'{difficulty}: cần ít nhất {count+1} ảnh, gồm 1 ảnh pilot')
        for name in names:
            if not isinstance(name, str) or not name or '/' in name or '\\' in name or Path(name).suffix.lower() not in ('.jpg', '.jpeg', '.png'):
                parser.error('Chỉ nhận tên file ảnh, không nhận đường dẫn')
            path = (root/name).resolve()
            if name in seen or path.parent != root or not path.is_file():
                parser.error(f'Ảnh thiếu/trùng/ngoài thư mục: {name}')
            seen.add(name)
        chosen = rng.sample(sorted(names), count+1)
        pilot.append(chosen.pop())
        main_names.extend(chosen)
        strata.update({name: difficulty for name in chosen})
    rng.shuffle(main_names)
    # Each image gets both modes, balanced for order. Break before round 2.
    first = [{'asset_name': name, 'mode': 'manual' if i < 10 else 'assisted'} for i, name in enumerate(main_names)]
    second = [{'asset_name': r['asset_name'], 'mode': 'assisted' if r['mode'] == 'manual' else 'manual'} for r in first]
    rng.shuffle(first)
    rng.shuffle(second)
    if args.output.exists():
        parser.error('Output đã tồn tại; chọn thư mục mới để giữ lần chọn trước')
    args.output.mkdir(parents=True)
    for folder, names in [('main', main_names), ('pilot', pilot)]:
        destination = args.output/folder
        (destination/'assets').mkdir(parents=True)
        for name in names:
            shutil.copy2(root/name, destination/'assets'/name)
        (destination/'manifest.json').write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding='utf-8')
    protocol = dict(seed=args.seed, quotas=quotas, strata=strata, round_1=first, round_2=second,
                    note='Pilot excluded. Freeze before AI inference. Same annotator in both rounds.')
    (args.output/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output/'candidates.json').write_text(json.dumps(buckets, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Đã chuẩn bị 20 ảnh chính và 3 ảnh pilot tại {args.output}. Không dùng lại pilot để báo cáo chính.')


if __name__ == '__main__':
    main()
