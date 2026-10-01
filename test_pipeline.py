import hashlib
from pathlib import Path
import tempfile
import unittest

from make_sample import generate
from pipeline import audit, prepare


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class PipelineTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp)/'raw', Path(tmp)/'ready'
            generate(source)
            original = hashes(source)
            report = prepare(source, dest, ['blue_box', 'orange_box'])
            self.assertEqual((report['images_found'], report['labels_found'], report['valid_pairs']), (18, 18, 13))
            self.assertEqual(report['excluded_images'], 5)
            self.assertEqual(report['class_instances'], {'blue_box': 6, 'orange_box': 6})
            self.assertEqual([len(v) for v in report['splits'].values()], [9, 3, 1])
            self.assertEqual(len(report['issues']), 6)
            self.assertEqual(hashes(source), original)
            found = []
            for split in ('train', 'val', 'test'):
                images = list((dest/'images'/split).glob('*.png'))
                found.extend(p.name for p in images)
                for img in images:
                    label = dest/'labels'/split/(img.stem+'.txt')
                    self.assertEqual(img.read_bytes(), (source/'images'/img.name).read_bytes())
                    self.assertEqual(label.read_bytes(), (source/'labels'/label.name).read_bytes())
            self.assertEqual(len(set(found)), 13)
            flat = Path(tmp)/'output_check'
            (flat/'images').mkdir(parents=True)
            (flat/'labels').mkdir()
            for folder in ('images', 'labels'):
                for p in (dest/folder).rglob('*'):
                    if p.is_file():
                        (flat/folder/p.name).write_bytes(p.read_bytes())
            self.assertEqual(audit(flat, ['blue_box', 'orange_box'])[1]['issues'], [])
            self.assertEqual((dest/'dataset.yaml').read_text().count('blue_box'), 1)
            second = prepare(source, Path(tmp)/'again', ['blue_box', 'orange_box'])
            self.assertEqual(report, second)
            with self.assertRaises(FileExistsError):
                prepare(source, dest, ['blue_box', 'orange_box'])
            with self.assertRaises(ValueError):
                prepare(source, source/'nested', ['blue_box', 'orange_box'])
            with self.assertRaises(ValueError):
                prepare(source, Path(tmp)/'invalid', ['blue_box'], (.5, .5, .5))

    def test_validation_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'images').mkdir()
            (root/'labels').mkdir()
            for i, text in enumerate(['0 .5 .5 0 .2', '-1 .5 .5 .2 .2', '0 1.2 .5 .2 .2', '0 .5 .5 .2 .2\ninvalid']):
                (root/'images'/f'{i}.png').write_bytes(b'placeholder')
                (root/'labels'/f'{i}.txt').write_text(text)
            pairs, report = audit(root, ['box'])
            self.assertEqual(pairs, [])
            self.assertEqual(len(report['issues']), 4)
            (root/'images'/'0.jpg').write_bytes(b'placeholder')
            self.assertIn('ambiguous_image_stem', audit(root, ['box'])[1]['issue_counts'])
            with self.assertRaises(ValueError):
                prepare(root, root.parent/(root.name+'-out'), ['box'])


if __name__ == '__main__':
    unittest.main()
