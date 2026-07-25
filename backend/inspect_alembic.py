import sqlite3

conn = sqlite3.connect("autohr.db")
cur = conn.cursor()

cur.execute("SELECT * FROM alembic_version")
print(cur.fetchall())

conn.close()