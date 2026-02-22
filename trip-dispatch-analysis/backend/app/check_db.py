# Save as: backend/app/check_db.py
# Run from backend/app/: python check_db.py

import psycopg2
from config import DATABASE_URL

def inspect_db():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Get all tables + materialized views
    cur.execute("""
        SELECT table_name, 'table' as type FROM information_schema.tables 
        WHERE table_schema = 'public'
        UNION ALL
        SELECT matviewname, 'materialized_view' FROM pg_matviews
        WHERE schemaname = 'public'
        ORDER BY type, table_name
    """)
    tables = cur.fetchall()
    print(f"=== FOUND {len(tables)} TABLES/VIEWS ===\n")

    for table_name, table_type in tables:
        # Column info
        cur.execute(f"""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' 
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        print(f"\n--- {table_name} ({table_type}, {len(columns)} columns) ---")
        for col_name, dtype, nullable in columns:
            print(f"  {col_name:35s} {dtype:25s} nullable={nullable}")

        # Sample rows
        cur.execute(f'SELECT * FROM "{table_name}" LIMIT 3')
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        print(f"\n  Sample data ({len(rows)} rows):")
        for row in rows:
            print(f"  {dict(zip(col_names, row))}")

    # 2. Row counts
    print("\n\n=== ROW COUNTS ===")
    for table_name, table_type in tables:
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        count = cur.fetchone()[0]
        print(f"  {table_name:35s} [{table_type:20s}] {count:>8,} rows")

    cur.close()
    conn.close()

if __name__ == "__main__":
    inspect_db()
