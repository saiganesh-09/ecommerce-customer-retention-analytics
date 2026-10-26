"""Set up the PostgreSQL analytics database for the Olist project.

Steps performed:
  1. Run sql/00_database_setup.sql  (create schemas + raw tables)
  2. Load every raw CSV into its landing table with COPY
  3. Optionally run additional SQL scripts passed as arguments
     (e.g. 02_staging_tables.sql)

Usage:
    python scripts/setup_database.py [--scripts sql/02_staging_tables.sql ...]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import PROJECT_ROOT, RAW_DATA_DIR, RAW_TABLE_FILES, get_connection


def run_sql_file(cur, path: Path) -> None:
    """Execute all statements in a .sql file."""
    sql = path.read_text(encoding="utf-8")
    print(f"  running {path.name} ...")
    cur.execute(sql)


def copy_csv(cur, table: str, csv_path: Path) -> int:
    """Load a CSV file into a raw table using COPY ... FROM STDIN.

    Empty strings are loaded as NULL. COPY is used (rather than row-by-row
    INSERT) because the files contain up to ~100k rows and quoted text with
    embedded commas/newlines.
    """
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        cur.copy_expert(
            f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')",
            f,
        )
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scripts",
        nargs="*",
        default=[],
        help="Additional .sql files to execute after the raw load.",
    )
    args = parser.parse_args()

    # Fail fast if any expected source file is missing.
    missing = [
        name for name in RAW_TABLE_FILES.values()
        if not (RAW_DATA_DIR / name).exists()
    ]
    if missing:
        print("ERROR: missing source CSVs in data/raw/:")
        for name in missing:
            print(f"  - {name}")
        return 1

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            setup_sql = PROJECT_ROOT / "sql" / "00_database_setup.sql"
            run_sql_file(cur, setup_sql)

            print("\nLoading raw CSV files:")
            for table, filename in RAW_TABLE_FILES.items():
                path = RAW_DATA_DIR / filename
                n = copy_csv(cur, table, path)
                print(f"  {table:<28} <- {filename:<45} {n:>7,} rows")

            for script in args.scripts:
                run_sql_file(cur, PROJECT_ROOT / script)

        print("\nDatabase setup complete.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
