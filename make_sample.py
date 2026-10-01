"""Generate original synthetic PNG images and deliberate annotation errors."""
from pathlib import Path
import struct
import zlib


def png(path, cls):
    width = height = 128
    color = (35, 160, 210) if cls == 0 else (235, 145, 45)
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(color if 32 <= x < 96 and 32 <= y < 96 else (245, 247, 250))
    def chunk(kind, data):
        return struct.pack('!I', len(data))+kind+data+struct.pack('!I', zlib.crc32(kind+data))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))+chunk(b'IDAT', zlib.compress(rows))+chunk(b'IEND', b''))


def generate(root):
    root = Path(root)
    if root.exists():
        raise FileExistsError(root)
    for folder in ('images', 'labels'):
        (root / folder).mkdir(parents=True)
    for i in range(12):
        png(root / 'images' / f'item_{i:02}.png', i % 2)
        (root / 'labels' / f'item_{i:02}.txt').write_text(f'{i%2} 0.5 0.5 0.5 0.5\n')
    faults = {'bad_class': '9 0.5 0.5 0.5 0.5', 'bad_box': '0 0.9 0.5 0.5 0.5',
              'bad_format': '1 0.5 0.5', 'nonfinite': '0 nan 0.5 0.2 0.2', 'background': ''}
    for name, label in faults.items():
        png(root / 'images' / f'{name}.png', 0)
        (root / 'labels' / f'{name}.txt').write_text(label)
    png(root / 'images' / 'missing_label.png', 0)
    (root / 'labels' / 'missing_image.txt').write_text('0 0.5 0.5 0.5 0.5\n')


if __name__ == '__main__':
    generate(Path(__file__).parent / 'sample_input')
