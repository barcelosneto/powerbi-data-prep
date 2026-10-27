import csv
import tempfile
import unittest
from pathlib import Path
from prepare_model import FIELDS, prepare, read_movements


class ModelTests(unittest.TestCase):
    def source(self, folder, rows):
        path = Path(folder) / "input.csv"
        path.write_text(";".join(FIELDS) + "\n" + rows, encoding="utf-8")
        return path

    def test_grain_total_and_referential_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.source(folder, "1;2026-10-01;Caderno;Papelaria;25.50\n2;2026-10-03;Suporte;Acessórios;90.00\n")
            original = source.read_bytes()
            output = Path(folder) / "model"
            summary = prepare(source, output)
            self.assertEqual(summary["amount_cents"], 11550)
            self.assertEqual(summary["rows"], 2)
            def read(name):
                with (output / name).open(encoding="utf-8-sig", newline="") as stream:
                    return list(csv.DictReader(stream))
            facts = read("fact_movement.csv")
            self.assertEqual(len(read("dim_date.csv")), 3)
            for field, filename in (("date_key", "dim_date.csv"), ("product_key", "dim_product.csv"), ("category_key", "dim_category.csv")):
                keys = {row[field] for row in read(filename)}
                self.assertTrue(all(row[field] in keys for row in facts))
            self.assertEqual(source.read_bytes(), original)

    def test_generator_is_lazy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.source(folder, "1;2026-10-01;A;B;1\n2;invalid;A;B;1\n")
            rows = read_movements(source)
            self.assertEqual(next(rows)["movement_id"], 1)
            with self.assertRaises(ValueError):
                next(rows)

    def test_invalid_values_leave_no_output(self):
        for amount in ("NaN", "Infinity", "-1", "1.001", "abc"):
            with self.subTest(amount=amount), tempfile.TemporaryDirectory() as folder:
                source = self.source(folder, f"1;2026-10-01;A;B;{amount}\n")
                output = Path(folder) / "out"
                with self.assertRaises(ValueError):
                    prepare(source, output)
                self.assertFalse(output.exists())

    def test_duplicate_id(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.source(folder, "1;2026-10-01;A;B;1\n1;2026-10-02;A;B;2\n")
            with self.assertRaises(ValueError):
                prepare(source, Path(folder) / "out")

    def test_preserve_existing_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                prepare(Path(folder) / "absent.csv", Path(folder))

    def test_empty_and_formula_prefix(self):
        for rows in ("", "1;2026-10-01;=FORMULA;B;1\n"):
            with self.subTest(rows=rows), tempfile.TemporaryDirectory() as folder:
                source = self.source(folder, rows)
                with self.assertRaises(ValueError):
                    prepare(source, Path(folder) / "out")
