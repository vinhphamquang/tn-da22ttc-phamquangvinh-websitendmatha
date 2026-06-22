"""
RESTORE Database SmartFoodAI tu file backup SQL
Chay: python restore_db.py backups/backup_YYYYMMDD_HHMMSS.sql
"""
import os, sys, psycopg2
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if 'sslmode' not in DATABASE_URL:
    DATABASE_URL += ('&' if '?' in DATABASE_URL else '?') + 'sslmode=require'

if len(sys.argv) < 2:
    # Tim file backup moi nhat
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    if os.path.exists(backup_dir):
        files = sorted([f for f in os.listdir(backup_dir) if f.endswith('.sql')], reverse=True)
        if files:
            backup_file = os.path.join(backup_dir, files[0])
            print(f"Su dung backup moi nhat: {files[0]}")
        else:
            print("Khong tim thay file backup nao trong thu muc backups/")
            sys.exit(1)
    else:
        print("Chua co thu muc backups/")
        print("Cach dung: python restore_db.py backups/backup_YYYYMMDD.sql")
        sys.exit(1)
else:
    backup_file = sys.argv[1]

if not os.path.exists(backup_file):
    print(f"Khong tim thay file: {backup_file}")
    sys.exit(1)

print("=" * 60)
print("RESTORE DATABASE TU BACKUP")
print(f"File: {backup_file}")
print("=" * 60)

confirm = 'y'
if confirm.lower() != 'y':
    print("Da huy.")
    sys.exit(0)

with open(backup_file, 'r', encoding='utf-8') as f:
    sql_content = f.read()

conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
conn.autocommit = False
cursor = conn.cursor()

try:
    statements = sql_content.split(';')
    success = 0
    errors = 0
    
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt or stmt.startswith('--'):
            continue
        try:
            cursor.execute(stmt + ';')
            success += 1
        except Exception as e:
            errors += 1
            conn.rollback()
            continue
    
    conn.commit()
    
    # Kiem tra ket qua
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    tables = cursor.fetchall()
    
    print(f"\n[OK] Restore hoan tat!")
    print(f"  Thanh cong: {success} lenh")
    print(f"  Loi (bo qua): {errors} lenh")
    print(f"\nCac bang ({len(tables)}):")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM \"{t[0]}\"")
        count = cursor.fetchone()[0]
        print(f"  - {t[0]} ({count} records)")
    
except Exception as e:
    conn.rollback()
    print(f"[ERROR] {e}")
finally:
    conn.close()

print(f"\n{'=' * 60}")
print("HOAN TAT!")
print("=" * 60)
