"""Create two portfolio SVG figures from executed report metrics."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).parent


def figure(title, rows, path):
    content = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="580" viewBox="0 0 1000 580">',
               '<rect width="1000" height="580" fill="#101d30"/>',
               f'<text x="55" y="65" fill="white" font-family="Arial" font-size="30">{html.escape(title)}</text>',
               '<text x="55" y="105" fill="#a6bdd6" font-family="Arial" font-size="18">Synthetic YOLO detection sample · measured pipeline results</text>']
    for i, (label, value) in enumerate(rows):
        y = 160 + i*62
        content.append(f'<text x="55" y="{y+24}" fill="#e5edf8" font-family="Arial" font-size="20">{html.escape(label)}</text>')
        content.append(f'<rect x="410" y="{y}" width="{max(3, value*24)}" height="34" rx="5" fill="#39c3bd"/>')
        content.append(f'<text x="{430+max(3,value*24)}" y="{y+25}" fill="white" font-family="Arial" font-size="21">{value}</text>')
    content.append('<text x="55" y="545" fill="#a6bdd6" font-family="Arial" font-size="17">Original files preserved • Valid pairs copied • Seed 42</text></svg>')
    path.write_text('\n'.join(content), encoding='utf-8')


if __name__ == '__main__':
    report = json.loads((ROOT/'sample_output'/'report.json').read_text())
    folder = ROOT/'portfolio'
    folder.mkdir(exist_ok=True)
    figure('YOLO Dataset Audit & Preparation Pipeline', [('Input images', report['images_found']), ('Accepted image / label pairs', report['valid_pairs']), ('Excluded images', report['excluded_images']), ('Issues (including orphan label)', len(report['issues']))], folder/'audit-summary.svg')
    figure('Training-ready dataset: splits & class balance', [(f'{s.title()} images', len(v)) for s, v in report['splits'].items()]+list(report['class_instances'].items()), folder/'split-and-classes.svg')
