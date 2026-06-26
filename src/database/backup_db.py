import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime
from dotenv import load_dotenv

# Setup date/datetime serialization for JSON
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

def backup_db():
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("Không tìm thấy DATABASE_URL trong file .env")
        return

    # Handle SSL requirement for Render
    if 'sslmode' not in db_url:
        separator = '&' if '?' in db_url else '?'
        db_url = f"{db_url}{separator}sslmode=require"

    print("Connecting to Render database...")
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Lấy danh sách tất cả các bảng
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        tables = [row['table_name'] for row in cursor.fetchall()]
        print(f"Found tables: {', '.join(tables)}")

        # Tạo thư mục backup
        backup_dir = "db_backup"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for table in tables:
            print(f"Backing up table {table}...")
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            # Lưu ra file JSON
            filename = os.path.join(backup_dir, f"{table}_{timestamp}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(rows, f, ensure_ascii=False, indent=4, cls=DateTimeEncoder)
            print(f"Saved {len(rows)} records to {filename}")

        conn.close()
        print(f"Backup successful! Data saved in directory: {backup_dir}")

    except Exception as e:
        print(f"Backup error: {e}")

if __name__ == "__main__":
    backup_db()
