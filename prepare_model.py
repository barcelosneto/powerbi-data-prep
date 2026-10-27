"""Prepara fatos e dimensões CSV a partir de movimentos fictícios. Biblioteca padrão."""
import argparse
import csv
import hashlib
import json
import logging
import re
import tempfile
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

logger = logging.getLogger(__name__)
FIELDS = ["movement_id", "date", "product", "category", "amount"]


def read_movements(source):
    """Generator: valida e entrega um registro por vez, sem materializar a origem."""
    with Path(source).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";", strict=True)
        if reader.fieldnames != FIELDS:
            raise ValueError("Cabeçalho esperado: " + ";".join(FIELDS))
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Quantidade de campos inválida na linha {reader.line_num}")
            values = {key: value.strip() for key, value in row.items()}
            if any(not value for value in values.values()):
                raise ValueError(f"Campo vazio na linha {reader.line_num}")
            if not values["movement_id"].isascii() or not values["movement_id"].isdigit():
                raise ValueError("ID deve ser um inteiro positivo")
            identifier = int(values["movement_id"])
            if not 0 < identifier <= 2**63 - 1:
                raise ValueError("ID fora do intervalo Int64 positivo")
            day = date.fromisoformat(values["date"])
            if day.isoformat() != values["date"]:
                raise ValueError("Data deve usar AAAA-MM-DD")
            for key in ("product", "category"):
                if len(values[key]) > 120 or values[key][0] in "=+-@\t\r\n":
                    raise ValueError("Nome vazio, longo ou com prefixo de fórmula")
            try:
                if len(values["amount"]) > 32 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", values["amount"]):
                    raise InvalidOperation
                amount = Decimal(values["amount"])
                if not amount.is_finite() or amount < 0:
                    raise InvalidOperation
                cents = amount * 100
                if cents != cents.to_integral_value() or cents > 2**63 - 1:
                    raise InvalidOperation
            except InvalidOperation as error:
                raise ValueError("Valor deve ser finito, não negativo e ter no máximo duas casas decimais") from error
            yield {"movement_id": identifier, "day": day, "product": values["product"],
                   "category": values["category"], "amount_cents": int(cents)}


def digest(source):
    result = hashlib.sha256()
    with Path(source).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            result.update(chunk)
    return result.hexdigest()


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError("Escolha uma pasta de saída nova para preservar resultados anteriores")
    initial_hash = digest(source)
    categories, products, ids = set(), set(), set()
    first = last = None
    count = total = 0
    for row in read_movements(source):
        if row["movement_id"] in ids:
            raise ValueError("ID de movimento duplicado")
        ids.add(row["movement_id"])
        categories.add(row["category"])
        products.add((row["product"], row["category"]))
        first = min(first or row["day"], row["day"])
        last = max(last or row["day"], row["day"])
        count += 1
        total += row["amount_cents"]
    if not count:
        raise ValueError("A origem não contém movimentos")
    if (last - first).days > 3660:
        raise ValueError("Exemplo limitado a uma dimensão de datas de até 3.661 dias")
    category_keys = {name: i for i, name in enumerate(sorted(categories), 1)}
    product_keys = {value: i for i, value in enumerate(sorted(products), 1)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        temporary = Path(folder)
        write_csv(temporary / "dim_category.csv", ["category_key", "category"],
                  ({"category_key": key, "category": name} for name, key in category_keys.items()))
        write_csv(temporary / "dim_product.csv", ["product_key", "product"],
                  ({"product_key": key, "product": value[0]} for value, key in product_keys.items()))
        days = (first + timedelta(days=i) for i in range((last-first).days + 1))
        write_csv(temporary / "dim_date.csv", ["date_key", "date", "year", "month"],
                  ({"date_key": int(day.strftime("%Y%m%d")), "date": day.isoformat(),
                    "year": day.year, "month": day.month} for day in days))
        def facts():
            for row in read_movements(source):
                yield {"movement_id": row["movement_id"], "date_key": int(row["day"].strftime("%Y%m%d")),
                       "product_key": product_keys[(row["product"], row["category"])],
                       "category_key": category_keys[row["category"]], "amount_cents": row["amount_cents"]}
        write_csv(temporary / "fact_movement.csv",
                  ["movement_id", "date_key", "product_key", "category_key", "amount_cents"], facts())
        if digest(source) != initial_hash:
            raise ValueError("A origem mudou durante o processamento; execute novamente")
        summary = {"rows": count, "amount_cents": total, "categories": len(categories),
                   "products": len(products), "source_sha256": initial_hash,
                   "date_start": first.isoformat(), "date_end": last.isoformat(),
                   "grain": "um registro por movimento", "data": "fictitious sample when using amostra.csv"}
        (temporary / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        # Rename na mesma unidade; a pasta final só aparece após gerar e conferir tudo.
        temporary.rename(destination)
    logger.info("Modelo preparado: %s movimentos; total de %s centavos", count, total)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", type=Path)
    parser.add_argument("saida", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    prepare(args.entrada, args.saida)


if __name__ == "__main__":
    main()
