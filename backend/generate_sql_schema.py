"""Generate PostgreSQL DDL schema file from SQLAlchemy models for Supabase / PostgreSQL.

Usage:
    python -m backend.generate_sql_schema [output_file]
"""
import sys
from pathlib import Path
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy import create_mock_engine

from backend.models import Base


def generate_postgres_ddl() -> str:
    ddl_statements = [
        "-- ========================================================",
        "-- PostgreSQL / Supabase DDL Schema Export for Sales App",
        "-- Auto-generated from SQLAlchemy Models (backend/models.py)",
        "-- ========================================================",
        "",
        "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";",
        "CREATE EXTENSION IF NOT EXISTS \"pg_trgm\";",
        "",
    ]

    def dump(sql, *multiparams, **params):
        compiled = str(sql.compile(dialect=engine.dialect)).strip()
        if compiled:
            ddl_statements.append(f"{compiled};")
            ddl_statements.append("")

    engine = create_mock_engine("postgresql://", dump)

    # Sort tables by topological order to satisfy foreign key dependencies
    sorted_tables = Base.metadata.sorted_tables

    for table in sorted_tables:
        table_ddl = str(CreateTable(table).compile(dialect=engine.dialect)).strip()
        ddl_statements.append(f"-- Table: {table.name}")
        ddl_statements.append(f"{table_ddl};")
        ddl_statements.append("")

        # Add indexes for the table
        for index in table.indexes:
            idx_ddl = str(CreateIndex(index).compile(dialect=engine.dialect)).strip()
            ddl_statements.append(f"{idx_ddl};")
            ddl_statements.append("")

    return "\n".join(ddl_statements)


def main():
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("supabase_schema.sql")
    ddl = generate_postgres_ddl()
    output_path.write_text(ddl, encoding="utf-8")
    print(f"Schema successfully exported to {output_path.resolve()}")


if __name__ == "__main__":
    main()
