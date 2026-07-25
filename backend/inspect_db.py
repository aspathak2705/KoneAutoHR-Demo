import sqlite3

DB_PATH = "autohr.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("TABLES")
print("=" * 80)

cursor.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name;
""")

tables = [row[0] for row in cursor.fetchall()]

for table in tables:
    print(table)

print("\n" + "=" * 80)
print("SCHEMA")
print("=" * 80)

for table in tables:
    print(f"\n\nTABLE: {table}")
    print("-" * 80)

    cursor.execute(f"PRAGMA table_info({table});")

    columns = cursor.fetchall()

    for col in columns:
        cid, name, dtype, notnull, default, pk = col
        print(
            f"{name:25} "
            f"{dtype:15} "
            f"NOT NULL={bool(notnull)} "
            f"DEFAULT={default}"
        )

conn.close()