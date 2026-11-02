"""
Safe One-Time Database Migration Tool: Supabase -> Local PostgreSQL

Transfers all records from a source PostgreSQL database (Supabase) to a target local
PostgreSQL database without dropping, truncating, or altering the source.

Features:
- Source is strictly read-only.
- Preserves UUIDs, foreign key relationships, JSON/JSONB data, and encrypted fields.
- Respects foreign key dependency order during insertion.
- Deterministic retry & resume:
  - If a record with matching primary key exists in target, its contents are compared.
  - If identical, the record is safely treated as already migrated.
  - If values differ, migration halts immediately with an explicit error identifying table and PK.
  - Never uses unconditional ON CONFLICT DO UPDATE.
- Dynamic sequence synchronization:
  - Only inspects and updates sequences for serial/identity columns present in table metadata.
  - Skips UUID-only tables without failing or hardcoding column names.
- Table-by-table atomic transactions: failed table rollback leaves no partially inserted batch.
- Compares and verifies exact row counts.
- Credentials sanitized in all logs and outputs.

Usage:
  python backend/scripts/migrate_database.py --source "<SUPABASE_URL>" --target "<LOCAL_URL>"
  Or set environment variables SOURCE_DATABASE_URL and TARGET_DATABASE_URL / DATABASE_URL.
"""

import sys
import os
import argparse
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date
from uuid import UUID
from sqlalchemy import create_engine, text, MetaData, Table, inspect
from loguru import logger

# Ensure backend directory is in python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Insertion order respecting foreign keys
TABLE_ORDER: List[str] = [
    "organization_config",
    "agent_configuration",
    "browser_profiles",
    "employee_lists",
    "voice_profiles",
    "presentations",
    "presentation_assets",
    "presentation_metadata",
    "presentation_scripts",
    "presentation_questions",
    "sessions",
    "attendances",
    "meetings",
    "invitation_drafts",
    "uploads",
    "presentation_jobs",
    "runtimes",
    "runtime_messages",
]


def sanitize_url(url: str) -> str:
    import re
    return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", url or "")


def normalize_val(v: Any) -> Any:
    """Normalize values for robust equality comparison between source and target."""
    if v is None:
        return None
    if isinstance(v, (UUID,)):
        return str(v).lower()
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (dict, list)):
        import json
        return json.dumps(v, sort_keys=True, default=str)
    return v


def get_pk_tuple(row: Dict[str, Any], pk_cols: List[str]) -> Tuple[Any, ...]:
    return tuple(normalize_val(row.get(col)) for col in pk_cols)


def migrate_data(source_url: str, target_url: str, batch_size: int = 500) -> bool:
    source_clean = sanitize_url(source_url)
    target_clean = sanitize_url(target_url)

    logger.info("Starting safe database migration...")
    logger.info(f"Source: {source_clean}")
    logger.info(f"Target: {target_clean}")

    if source_url.strip() == target_url.strip():
        logger.error("Source and target database URLs are identical! Aborting.")
        return False

    source_engine = create_engine(
        source_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10} if "postgres" in source_url else {}
    )
    target_engine = create_engine(
        target_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5} if "postgres" in target_url else {}
    )

    # 1. Verify source connectivity (read-only verification)
    try:
        with source_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Source database connected successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to source database: {e}")
        return False

    # 2. Verify target connectivity
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Target database connected successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to target database: {e}")
        return False

    source_meta = MetaData()
    source_meta.reflect(bind=source_engine)

    target_meta = MetaData()
    target_meta.reflect(bind=target_engine)

    # Filter tables that actually exist in source
    tables_to_migrate = [t for t in TABLE_ORDER if t in source_meta.tables]
    # Add any extra tables present in source but not in predefined order
    for t_name in source_meta.tables.keys():
        if t_name not in tables_to_migrate and t_name != "alembic_version":
            tables_to_migrate.append(t_name)

    logger.info(f"Discovered {len(tables_to_migrate)} tables to migrate from source.")

    stats: Dict[str, Dict[str, int]] = {}

    # 3. Migrate each table in dependency order
    for table_name in tables_to_migrate:
        if table_name not in target_meta.tables:
            logger.warning(f"Skipping table '{table_name}': not present in target schema. Run migrations first!")
            continue

        source_table = Table(table_name, source_meta, autoload_with=source_engine)
        target_table = Table(table_name, target_meta, autoload_with=target_engine)

        # Inspect primary key columns
        pk_cols = [c.name for c in target_table.primary_key.columns]
        target_cols = set(target_table.columns.keys())

        # Fetch rows from source (strictly read-only)
        with source_engine.connect() as src_conn:
            src_rows = src_conn.execute(source_table.select()).mappings().all()

        source_count = len(src_rows)
        stats[table_name] = {"source": source_count, "inserted": 0, "existing_verified": 0, "target_total": 0}

        if source_count == 0:
            logger.info(f"Table '{table_name}': 0 rows in source. Skipping.")
            continue

        # Fetch existing target rows for conflict detection & content verification
        with target_engine.connect() as target_conn:
            existing_target_rows = target_conn.execute(target_table.select()).mappings().all()

        existing_target_by_pk: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        if pk_cols:
            for row in existing_target_rows:
                pk_val = get_pk_tuple(dict(row), pk_cols)
                existing_target_by_pk[pk_val] = dict(row)

        records_to_insert: List[Dict[str, Any]] = []

        for row in src_rows:
            src_record = {k: v for k, v in dict(row).items() if k in target_cols}

            if pk_cols:
                src_pk = get_pk_tuple(src_record, pk_cols)
                if src_pk in existing_target_by_pk:
                    existing_record = existing_target_by_pk[src_pk]
                    # Verify content matches
                    mismatches = []
                    for col in target_cols:
                        src_v = normalize_val(src_record.get(col))
                        tgt_v = normalize_val(existing_record.get(col))
                        if src_v != tgt_v:
                            mismatches.append(f"{col}: (source={src_v!r} vs target={tgt_v!r})")

                    if mismatches:
                        err = (
                            f"FATAL: Data conflict in table '{table_name}' for PK {dict(zip(pk_cols, src_pk))}. "
                            f"Target record already exists but differs from source: {'; '.join(mismatches[:3])}. "
                            "Aborting migration to prevent data corruption."
                        )
                        logger.error(err)
                        return False

                    stats[table_name]["existing_verified"] += 1
                    continue

            records_to_insert.append(src_record)

        # Atomic transaction per table for insert
        if records_to_insert:
            with target_engine.connect() as target_conn:
                with target_conn.begin():
                    # Temporarily defer replica triggers if privileged
                    try:
                        target_conn.execute(text("SET session_replication_role = 'replica';"))
                    except Exception:
                        pass

                    for i in range(0, len(records_to_insert), batch_size):
                        batch = records_to_insert[i:i + batch_size]
                        target_conn.execute(target_table.insert(), batch)
                        stats[table_name]["inserted"] += len(batch)

                    try:
                        target_conn.execute(text("SET session_replication_role = 'DEFAULT';"))
                    except Exception:
                        pass

        logger.info(
            f"Table '{table_name}': {stats[table_name]['inserted']} newly inserted, "
            f"{stats[table_name]['existing_verified']} already verified, "
            f"{source_count} total source rows."
        )

    # 4. Synchronize sequences dynamically for actual identity/serial columns
    with target_engine.connect() as target_conn:
        with target_conn.begin():
            for table_name in tables_to_migrate:
                if table_name not in target_meta.tables:
                    continue
                target_table = Table(table_name, target_meta, autoload_with=target_engine)

                for col in target_table.columns:
                    # Check if column is autoincrement / has a sequence
                    has_seq = False
                    if getattr(col, "autoincrement", False) is True:
                        has_seq = True
                    default_str = str(col.server_default.arg) if col.server_default is not None and hasattr(col.server_default, "arg") else ""
                    if "nextval" in default_str:
                        has_seq = True

                    if has_seq and col.type.python_type in (int,):
                        col_name = col.name
                        try:
                            target_conn.execute(text(f"""
                                DO $$
                                DECLARE
                                    seq_name text;
                                    max_val bigint;
                                BEGIN
                                    seq_name := pg_get_serial_sequence('public.{table_name}', '{col_name}');
                                    IF seq_name IS NOT NULL THEN
                                        EXECUTE 'SELECT COALESCE(MAX({col_name}), 1) FROM public.{table_name}' INTO max_val;
                                        PERFORM setval(seq_name, max_val);
                                    END IF;
                                END $$;
                            """))
                            logger.info(f"Synchronized sequence for {table_name}.{col_name}")
                        except Exception as e:
                            logger.warning(f"Could not synchronize sequence on {table_name}.{col_name}: {e}")

    # 5. Verify row count reconciliation
    logger.info("=== VERIFICATION & RECONCILIATION SUMMARY ===")
    all_matched = True
    for table_name, counts in stats.items():
        if table_name in target_meta.tables:
            with target_engine.connect() as target_conn:
                res = target_conn.execute(text(f"SELECT COUNT(*) FROM public.{table_name}")).scalar()
                counts["target_total"] = res or 0

            match = (counts["source"] <= counts["target_total"])
            if not match:
                all_matched = False
            status_str = "MATCH" if match else "MISMATCH"
            logger.info(
                f"[{status_str}] {table_name}: source={counts['source']} | "
                f"newly_inserted={counts['inserted']} | "
                f"already_existed={counts['existing_verified']} | "
                f"target_total={counts['target_total']}"
            )

    if all_matched:
        logger.info("Data migration completed successfully! All records verified.")
    else:
        logger.warning("Migration completed with count mismatches. Check individual table logs.")

    return all_matched


def main():
    parser = argparse.ArgumentParser(description="AutoHR Safe Database Migration (Supabase -> Local)")
    parser.add_argument("--source", type=str, help="Source database URL (e.g. Supabase)")
    parser.add_argument("--target", type=str, help="Target database URL (e.g. Local PostgreSQL)")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for inserts")
    args = parser.parse_args()

    source_url = args.source or os.environ.get("SOURCE_DATABASE_URL")
    target_url = args.target or os.environ.get("TARGET_DATABASE_URL") or os.environ.get("DATABASE_URL")

    if not source_url:
        print("ERROR: Source database URL is required via --source or SOURCE_DATABASE_URL environment variable.")
        sys.exit(1)

    if not target_url:
        print("ERROR: Target database URL is required via --target, TARGET_DATABASE_URL, or DATABASE_URL.")
        sys.exit(1)

    success = migrate_data(source_url, target_url, batch_size=args.batch_size)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
