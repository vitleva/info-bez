import unittest

from analyzer import SAMPLES, analyze


class Cases(unittest.TestCase):
    def test_samples(self):
        misses = []
        for sample in SAMPLES:
            result = analyze(sample["text"])
            blob = f"{result['headline']} {result['detail']} {result.get('approximate') or ''}"
            ok = result["status"] == sample["expect"] and sample["law"][:6].lower() in blob.lower()
            if not ok:
                misses.append(f"#{sample['id']} {result['status']} {result['headline']}")
        self.assertEqual(misses, [])

    def test_empty(self):
        with self.assertRaises(ValueError):
            analyze("   ")

    def test_several_laws(self):
        result = analyze(SAMPLES[1]["text"])
        self.assertGreaterEqual(len(result["laws"]), 2)


if __name__ == "__main__":
    unittest.main()
