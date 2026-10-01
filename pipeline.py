"""Audit a flat YOLO detection dataset and copy valid pairs into seeded splits."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
import shutil

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}


def audit(source, names):
    source = Path(source)
    issues, valid, counts = [], [], Counter()
    for folder in ('images', 'labels'):
        if not (source / folder).is_dir():
            issues.append({'file': folder, 'reason': 'missing_directory'})
    images = sorted(p for p in (source / 'images').glob('*') if p.suffix.lower() in EXTENSIONS)
    labels = sorted((source / 'labels').glob('*.txt'))
    stems = Counter(p.stem for p in images)
    for label in labels:
        if label.stem not in stems:
            issues.append({'file': label.name, 'reason': 'missing_image'})
    for img in images:
        label = source / 'labels' / (img.stem + '.txt')
        if stems[img.stem] > 1:
            issues.append({'file': img.name, 'reason': 'ambiguous_image_stem'})
            continue
        if not label.is_file():
            issues.append({'file': img.name, 'reason': 'missing_label'})
            continue
        local, bad = Counter(), False
        try:
            lines = label.read_text(encoding='utf-8').splitlines()
        except (UnicodeError, OSError):
            issues.append({'file': label.name, 'reason': 'unreadable_label'})
            continue
        for number, line in enumerate(lines, 1):
            try:
                fields = line.split()
                if len(fields) != 5:
                    raise ValueError('expected_five_fields')
                cls = int(fields[0])
                if not 0 <= cls < len(names):
                    raise ValueError('invalid_class_id')
                x, y, w, h = map(float, fields[1:])
                if not all(math.isfinite(v) for v in (x, y, w, h)):
                    raise ValueError('nonfinite_coordinate')
                if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    raise ValueError('invalid_normalized_box')
                if x-w/2 < -1e-9 or y-h/2 < -1e-9 or x+w/2 > 1+1e-9 or y+h/2 > 1+1e-9:
                    raise ValueError('box_outside_image')
                local[cls] += 1
            except ValueError as exc:
                bad = True
                issues.append({'file': label.name, 'line': number, 'reason': str(exc)})
        if not bad:
            valid.append((img, label))
            counts.update(local)
    return valid, {'images_found': len(images), 'labels_found': len(labels),
                   'valid_pairs': len(valid), 'excluded_images': len(images)-len(valid),
                   'background_images': sum(not p[1].read_text().strip() for p in valid),
                   'class_instances': {name: counts[i] for i, name in enumerate(names)},
                   'issues': issues, 'issue_counts': dict(Counter(i['reason'] for i in issues))}


def prepare(source, output, names, ratios=(.7, .2, .1), seed=42):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not names or len(set(names)) != len(names):
        raise ValueError('Class names must be nonempty and unique')
    if len(ratios) != 3 or any(not math.isfinite(r) or r < 0 for r in ratios) or not math.isclose(sum(ratios), 1):
        raise ValueError('Three nonnegative split ratios must sum to 1')
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('Input and output directories must not overlap')
    if output.exists():
        raise FileExistsError('Output already exists; choose a new folder')
    pairs, report = audit(source, names)
    if any(i['reason'] == 'missing_directory' for i in report['issues']) or not pairs:
        raise ValueError('Input needs images/ and labels/ and at least one valid pair')
    random.Random(seed).shuffle(pairs)
    # Largest remainder allocation keeps counts close to requested ratios.
    exact = [len(pairs)*r for r in ratios]
    sizes = [math.floor(n) for n in exact]
    for i in sorted(range(3), key=lambda i: exact[i]-sizes[i], reverse=True)[:len(pairs)-sum(sizes)]:
        sizes[i] += 1
    report.update(seed=seed, requested_ratios=list(ratios), splits={})
    offset = 0
    for split, size in zip(('train', 'val', 'test'), sizes):
        for folder in ('images', 'labels'):
            (output / folder / split).mkdir(parents=True, exist_ok=True)
        selected = pairs[offset:offset+size]
        offset += size
        for img, label in selected:
            shutil.copy2(img, output / 'images' / split / img.name)
            shutil.copy2(label, output / 'labels' / split / label.name)
        report['splits'][split] = [img.name for img, _ in selected]
    yaml = 'path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n'
    yaml += ''.join(f'  {i}: {json.dumps(name, ensure_ascii=False)}\n' for i, name in enumerate(names))
    (output / 'dataset.yaml').write_text(yaml, encoding='utf-8')
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['# Dataset validation summary', '', f"Images found: {report['images_found']}",
             f"Labels found: {report['labels_found']}", f"Valid pairs copied: {len(pairs)}",
             f"Excluded images: {report['excluded_images']}", f"Background images: {report['background_images']}", '',
             '## Splits', *[f'- {s}: {len(v)} images' for s, v in report['splits'].items()], '',
             '## Class instances (accepted images)', *[f'- {n}: {v}' for n, v in report['class_instances'].items()], '',
             '## Issues', *[f'- {v}' for v in report['issues']]]
    (output / 'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--classes', required=True, nargs='+')
    parser.add_argument('--ratios', type=float, nargs=3, default=(.7, .2, .1))
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    result = prepare(args.input, args.output, args.classes, args.ratios, args.seed)
    print(json.dumps({k: v for k, v in result.items() if k not in ('issues', 'splits')}, indent=2))
