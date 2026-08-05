import argparse
import csv
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from app.core.config import get_settings
from app.synthetic.generator import FIELD_ORDER
from app.synthetic.validation import validate_dataset


def read_csv_dataset(input_dir: Path) -> dict[str, list[dict[str, Any]]]:
    dataset = {}
    for table_name in FIELD_ORDER:
        input_path = input_dir / f"{table_name}.csv"
        if not input_path.is_file():
            raise FileNotFoundError(f"Required dataset file not found: {input_path}")
        with input_path.open(encoding="utf-8", newline="") as input_file:
            reader = csv.DictReader(input_file)
            if reader.fieldnames != FIELD_ORDER[table_name]:
                raise ValueError(f"Unexpected columns in {input_path}: {reader.fieldnames}")
            dataset[table_name] = list(reader)
    return dataset


def load_dataset(input_dir: Path) -> dict[str, int]:
    """Load all structured files atomically into empty canonical tables."""
    dataset = read_csv_dataset(input_dir)
    validate_dataset(dataset)
    settings = get_settings()
    counts: dict[str, int] = {}

    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    ) as connection:
        with connection.cursor() as cursor:
            occupied = []
            for table_name in FIELD_ORDER:
                cursor.execute(
                    sql.SQL("SELECT EXISTS (SELECT 1 FROM {} LIMIT 1)").format(
                        sql.Identifier(table_name)
                    )
                )
                if cursor.fetchone()[0]:
                    occupied.append(table_name)
            if occupied:
                raise RuntimeError(
                    "Load refused because target tables are not empty: " + ", ".join(occupied)
                )

            for table_name, rows in dataset.items():
                columns = FIELD_ORDER[table_name]
                copy_statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    sql.Identifier(table_name),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                )
                with cursor.copy(copy_statement) as copy:
                    for row in rows:
                        copy.write_row([row[column] or None for column in columns])
                counts[table_name] = len(rows)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and load synthetic CSV data")
    parser.add_argument("--input", type=Path, default=Path("data/generated/1x"))
    args = parser.parse_args()

    counts = load_dataset(args.input)
    for table_name, count in counts.items():
        print(f"{table_name}: {count} loaded")


if __name__ == "__main__":
    main()
