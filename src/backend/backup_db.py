"""
BACKUP Database SmartFoodAI ra file SQL
Chay: python backup_db.py
File backup se luu tai: d:/KLTN/backend/backups/
"""
import os, sys, json, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if 'sslmode' not in DATABASE_URL:
    DATABASE_URL += ('&' if '?' in DATABASE_URL else '?') + 'sslmode=require'

# Tao thu muc backups
backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
os.makedirs(backup_dir, exist_ok=True)

timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = os.path.join(backup_dir, f'backup_{timestamp}.sql')

print("=" * 60)
print(f"BACKUP DATABASE - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
cursor = conn.cursor(cursor_factory=RealDictCursor)

# Thu tu backup (quan trong vi co foreign key)
TABLES_ORDER = [
    'NguoiDung', 'MonAn', 'DinhDuong', 'CongThuc', 'NguyenLieu',
    'ChiTietNguyenLieu', 'LichSu', 'HoSoSucKhoe', 'LichSuCanNang',
    'BinhLuan', 'ThongBao', 'KeHoachDinhDuong'
]

sql_lines = []
sql_lines.append(f"-- SmartFoodAI Database Backup")
sql_lines.append(f"-- Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
sql_lines.append(f"-- Tables: {len(TABLES_ORDER)}")
sql_lines.append("")

# Schema
sql_lines.append("-- ============ SCHEMA ============")
sql_lines.append("""
CREATE TABLE IF NOT EXISTS NguoiDung (
    MaNguoiDung SERIAL PRIMARY KEY,
    TenNguoiDung VARCHAR(100) NOT NULL,
    Email VARCHAR(100) UNIQUE NOT NULL,
    MatKhau VARCHAR(255) NOT NULL,
    VaiTro VARCHAR(20) DEFAULT 'user',
    NgayDangKy TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    GoogleId VARCHAR(255),
    LastActive TIMESTAMP
);
CREATE TABLE IF NOT EXISTS MonAn (
    MaMonAn SERIAL PRIMARY KEY,
    TenMonAn VARCHAR(255) NOT NULL,
    MoTa TEXT,
    PhanLoai VARCHAR(100) DEFAULT 'Mon an',
    IsDeleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS DinhDuong (
    MaDinhDuong SERIAL PRIMARY KEY,
    MaMonAn INTEGER UNIQUE REFERENCES MonAn(MaMonAn) ON DELETE CASCADE,
    Calo DECIMAL(10,2) DEFAULT 0,
    Protein DECIMAL(10,2) DEFAULT 0,
    ChatBeo DECIMAL(10,2) DEFAULT 0,
    Carbohydrate DECIMAL(10,2) DEFAULT 0,
    Vitamin TEXT
);
CREATE TABLE IF NOT EXISTS CongThuc (
    MaCongThuc SERIAL PRIMARY KEY,
    MaMonAn INTEGER REFERENCES MonAn(MaMonAn) ON DELETE CASCADE,
    HuongDan TEXT,
    ThoiGianNau INTEGER DEFAULT 30,
    KhauPhan INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS NguyenLieu (
    MaNguyenLieu SERIAL PRIMARY KEY,
    TenNguyenLieu VARCHAR(255) UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS ChiTietNguyenLieu (
    MaChiTiet SERIAL PRIMARY KEY,
    MaCongThuc INTEGER REFERENCES CongThuc(MaCongThuc) ON DELETE CASCADE,
    MaNguyenLieu INTEGER REFERENCES NguyenLieu(MaNguyenLieu) ON DELETE CASCADE,
    SoLuong VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS LichSu (
    MaLichSu SERIAL PRIMARY KEY,
    MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
    DuongDanAnh TEXT,
    TenMonAn VARCHAR(255),
    DoChinhXac DECIMAL(5,2),
    ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Calo DECIMAL(10,2) DEFAULT 0,
    DanhGiaNguoiDung INTEGER,
    KhuyenNghiKeHoach TEXT
);
CREATE TABLE IF NOT EXISTS HoSoSucKhoe (
    MaHoSo SERIAL PRIMARY KEY,
    MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
    CanNang DECIMAL(5,2),
    ChieuCao DECIMAL(5,2),
    Tuoi INTEGER,
    GioiTinh VARCHAR(10),
    MucDoVanDong VARCHAR(20),
    MucTieu VARCHAR(50),
    BMR DECIMAL(10,2),
    TDEE DECIMAL(10,2),
    CaloDuKien DECIMAL(10,2),
    NgayCapNhat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS LichSuCanNang (
    MaLichSuCN SERIAL PRIMARY KEY,
    MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
    CanNang DECIMAL(5,2) NOT NULL,
    ChieuCao DECIMAL(5,2),
    BMI DECIMAL(5,2),
    PhanLoaiBMI VARCHAR(30),
    GhiChu TEXT,
    ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_lscn_user_time ON LichSuCanNang(MaNguoiDung, ThoiGian DESC);
CREATE TABLE IF NOT EXISTS BinhLuan (
    MaBinhLuan SERIAL PRIMARY KEY,
    MaLichSu INTEGER REFERENCES LichSu(MaLichSu) ON DELETE CASCADE,
    MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
    NoiDung TEXT NOT NULL,
    ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    MaBinhLuanCha INTEGER REFERENCES BinhLuan(MaBinhLuan) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ThongBao (
    MaThongBao SERIAL PRIMARY KEY,
    MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
    MaLichSu INTEGER REFERENCES LichSu(MaLichSu) ON DELETE SET NULL,
    NoiDung TEXT NOT NULL,
    TenCu VARCHAR(255) DEFAULT '',
    TenMoi VARCHAR(255) DEFAULT '',
    DaDoc BOOLEAN DEFAULT FALSE,
    ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS KeHoachDinhDuong (
    MaKeHoach SERIAL PRIMARY KEY,
    MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
    NgayLuu TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CaloDuKien DECIMAL(10,2) DEFAULT 0,
    TongCaloChon DECIMAL(10,2) DEFAULT 0,
    BuaSang TEXT DEFAULT '',
    BuaSangCalo DECIMAL(10,2) DEFAULT 0,
    BuaTrua TEXT DEFAULT '',
    BuaTruaCalo DECIMAL(10,2) DEFAULT 0,
    BuaToi TEXT DEFAULT '',
    BuaToiCalo DECIMAL(10,2) DEFAULT 0,
    BuaPhu TEXT DEFAULT '',
    BuaPhuCalo DECIMAL(10,2) DEFAULT 0
);
""")

# Data
sql_lines.append("-- ============ DATA ============")

total_records = 0
for table in TABLES_ORDER:
    try:
        cursor.execute(f'SELECT * FROM "{table.lower()}"')
        rows = cursor.fetchall()
        
        if not rows:
            print(f"  [SKIP] {table} (0 records)")
            continue
        
        columns = [desc[0] for desc in cursor.description]
        sql_lines.append(f"\n-- {table} ({len(rows)} records)")
        
        for row in rows:
            values = []
            for col in columns:
                val = row[col]
                if val is None:
                    values.append("NULL")
                elif isinstance(val, bool):
                    values.append("TRUE" if val else "FALSE")
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                elif isinstance(val, datetime.datetime):
                    values.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
                elif isinstance(val, datetime.date):
                    values.append(f"'{val.strftime('%Y-%m-%d')}'")
                else:
                    escaped = str(val).replace("'", "''")
                    values.append(f"'{escaped}'")
            
            cols_str = ', '.join(columns)
            vals_str = ', '.join(values)
            sql_lines.append(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str}) ON CONFLICT DO NOTHING;")
        
        total_records += len(rows)
        print(f"  [OK] {table} ({len(rows)} records)")
        
    except Exception as e:
        print(f"  [ERR] {table}: {e}")

# Reset sequences
sql_lines.append("\n-- ============ RESET SEQUENCES ============")
for table in TABLES_ORDER:
    try:
        cursor.execute(f"""
            SELECT column_name, column_default 
            FROM information_schema.columns 
            WHERE table_name = '{table.lower()}' 
            AND column_default LIKE 'nextval%%'
        """)
        seq_cols = cursor.fetchall()
        for sc in seq_cols:
            col = sc['column_name']
            sql_lines.append(f"SELECT setval(pg_get_serial_sequence('{table.lower()}', '{col}'), COALESCE((SELECT MAX({col}) FROM {table}), 1));")
    except:
        pass

conn.close()

# Ghi file
with open(backup_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(sql_lines))

file_size = os.path.getsize(backup_file)
print(f"\n{'=' * 60}")
print(f"BACKUP THANH CONG!")
print(f"  File: {backup_file}")
print(f"  Size: {file_size / 1024:.1f} KB")
print(f"  Records: {total_records}")
print(f"{'=' * 60}")
