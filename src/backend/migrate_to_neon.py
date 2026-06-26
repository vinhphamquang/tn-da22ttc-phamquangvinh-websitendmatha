"""
Migrate DATA from Render PostgreSQL to Neon PostgreSQL.
Schema must already exist on target (run init_database.py first).

Usage:
  1. $env:DATABASE_URL = "<NEON_URL>"; python backend/init_database.py
  2. python backend/migrate_to_neon.py <NEON_DATABASE_URL>
"""
import psycopg2
import os
import sys
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()

# Source (Render) - from .env
SOURCE_URL = os.getenv('DATABASE_URL')
if SOURCE_URL and 'sslmode' not in SOURCE_URL:
    SOURCE_URL += '?sslmode=require'

# Target (Neon) - from NEON_DATABASE_URL env var, command line, or _neon_url.txt file
TARGET_URL = os.getenv('NEON_DATABASE_URL')
if not TARGET_URL and len(sys.argv) >= 2:
    TARGET_URL = sys.argv[1]
if not TARGET_URL:
    url_file = os.path.join(os.path.dirname(__file__), '_neon_url.txt')
    if os.path.exists(url_file):
        with open(url_file, 'r') as f:
            TARGET_URL = f.read().strip()
if not TARGET_URL:
    print("Set NEON_DATABASE_URL env var or create _neon_url.txt")
    sys.exit(1)
if TARGET_URL and 'sslmode' not in TARGET_URL:
    TARGET_URL += '?sslmode=require'

# Migration order (parents first for FK integrity)
TABLES = [
    'nguoidung',
    'monan',
    'dinhduong',
    'congthuc',
    'nguyenlieu',
    'chitietnguyenlieu',
    'lichsu',
    'hososuckhoe',
    'lichsucannang',
    'binhluan',
    'thongbao',
    'kehoachdinhduong',
    'thanhtoan',
]

def migrate():
    print(f"Source (Render): {SOURCE_URL[:60]}...")
    print(f"Target (Neon):   {TARGET_URL[:60]}...")
    print()

    src_conn = psycopg2.connect(SOURCE_URL, connect_timeout=15)
    src_cur = src_conn.cursor()
    tgt_conn = psycopg2.connect(TARGET_URL, connect_timeout=15)
    tgt_cur = tgt_conn.cursor()

    total = 0
    for table in TABLES:
        # Get columns from source
        src_cur.execute("""
            SELECT column_name, data_type, character_maximum_length,
                   numeric_precision, numeric_scale, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
        """, (table,))
        src_cols = src_cur.fetchall()
        src_col_names = [c[0] for c in src_cols]
        if not src_col_names:
            print(f"  [SKIP] {table}: table not found in source")
            continue

        # Get columns from target
        tgt_cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
        """, (table,))
        tgt_col_names = set(r[0] for r in tgt_cur.fetchall())

        # Add missing columns to target
        for col in src_cols:
            name, dtype, max_len, num_prec, num_scale, default, nullable = col
            if name not in tgt_col_names:
                if dtype == 'character varying':
                    type_str = f'varchar({max_len})' if max_len else 'varchar'
                elif dtype == 'numeric':
                    type_str = f'numeric({num_prec},{num_scale})' if num_prec else 'numeric'
                else:
                    type_str = dtype
                default_str = f' DEFAULT {default}' if default else ''
                nullable_str = '' if nullable == 'YES' else ' NOT NULL'
                alter_sql = f'ALTER TABLE "{table}" ADD COLUMN "{name}" {type_str}{default_str}{nullable_str}'
                tgt_cur.execute(alter_sql)
                print(f"  [ADD] {table}.{name} ({type_str})")
                tgt_col_names.add(name)
        tgt_conn.commit()

        # Only copy columns that exist in both
        columns = [c for c in src_col_names if c in tgt_col_names]

        col_list = ','.join(columns)
        placeholders = ','.join(['%s'] * len(columns))

        # Read from source
        src_cur.execute(f'SELECT {col_list} FROM "{table}"')
        rows = src_cur.fetchall()

        if rows:
            insert_sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            tgt_cur.executemany(insert_sql, rows)
            tgt_conn.commit()
            print(f"  [OK] {table}: {len(rows)} rows copied")
            total += len(rows)
        else:
            print(f"  [--] {table}: 0 rows")

    # Reset SERIAL sequences to MAX(id)+1
    print("\nResetting sequences...")
    for table in TABLES:
        src_cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
              AND column_default LIKE 'nextval%%'
        """, (table,))
        for (col,) in src_cur.fetchall():
            try:
                tgt_cur.execute(f"""
                    SELECT setval(
                        pg_get_serial_sequence('"{table}"', '{col}'),
                        COALESCE((SELECT MAX("{col}") FROM "{table}"), 1)
                    )
                """)
            except Exception as e:
                print(f"  [SKIP] {table}.{col}: {e}")

    tgt_conn.commit()

    # Verify
    print("\n=== VERIFY ===")
    all_ok = True
    for table in TABLES:
        src_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        src_cnt = src_cur.fetchone()[0]
        tgt_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        tgt_cnt = tgt_cur.fetchone()[0]
        ok = "OK" if src_cnt == tgt_cnt else "MISMATCH!"
        if src_cnt != tgt_cnt:
            all_ok = False
        print(f"  {table}: source={src_cnt} target={tgt_cnt} [{ok}]")

    src_conn.close()
    tgt_conn.close()
    print(f"\nTotal rows migrated: {total}")
    print("=== MIGRATION COMPLETE ===" if all_ok else "=== MIGRATION COMPLETE (with warnings) ===")

if __name__ == '__main__':
    migrate()
