"""
Script khoi tao toan bo Schema cho Database SmartFoodAI
Chay 1 lan sau khi tao database moi tren Render
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

# Them sslmode
if DATABASE_URL and 'sslmode' not in DATABASE_URL:
    separator = '&' if '?' in DATABASE_URL else '?'
    DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"

print("=" * 60)
print("KHOI TAO DATABASE SMARTFOODAI")
print("=" * 60)

try:
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    cursor = conn.cursor()
    print("[OK] Ket noi database thanh cong!\n")
    
    # ============================================
    # TAO CAC BANG
    # ============================================
    
    print("Dang tao cac bang...")
    
    # 1. NguoiDung (Users)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS NguoiDung (
            MaNguoiDung SERIAL PRIMARY KEY,
            TenNguoiDung VARCHAR(100) NOT NULL,
            Email VARCHAR(100) UNIQUE NOT NULL,
            MatKhau VARCHAR(255) NOT NULL,
            VaiTro VARCHAR(20) DEFAULT 'user',
            NgayDangKy TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            GoogleId VARCHAR(255),
            LastActive TIMESTAMP
        )
    """)
    print("  [OK] Bang NguoiDung")
    
    # 2. MonAn (Foods)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS MonAn (
            MaMonAn SERIAL PRIMARY KEY,
            TenMonAn VARCHAR(255) NOT NULL,
            MoTa TEXT,
            PhanLoai VARCHAR(100) DEFAULT 'Mon an',
            IsDeleted INTEGER DEFAULT 0
        )
    """)
    print("  [OK] Bang MonAn")
    
    # 3. DinhDuong (Nutrition)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS DinhDuong (
            MaDinhDuong SERIAL PRIMARY KEY,
            MaMonAn INTEGER UNIQUE REFERENCES MonAn(MaMonAn) ON DELETE CASCADE,
            Calo DECIMAL(10,2) DEFAULT 0,
            Protein DECIMAL(10,2) DEFAULT 0,
            ChatBeo DECIMAL(10,2) DEFAULT 0,
            Carbohydrate DECIMAL(10,2) DEFAULT 0,
            Vitamin TEXT
        )
    """)
    print("  [OK] Bang DinhDuong")
    
    # 4. CongThuc (Recipes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CongThuc (
            MaCongThuc SERIAL PRIMARY KEY,
            MaMonAn INTEGER REFERENCES MonAn(MaMonAn) ON DELETE CASCADE,
            HuongDan TEXT,
            ThoiGianNau INTEGER DEFAULT 30,
            KhauPhan INTEGER DEFAULT 1
        )
    """)
    print("  [OK] Bang CongThuc")
    
    # 5. NguyenLieu (Ingredients)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS NguyenLieu (
            MaNguyenLieu SERIAL PRIMARY KEY,
            TenNguyenLieu VARCHAR(255) UNIQUE NOT NULL
        )
    """)
    print("  [OK] Bang NguyenLieu")
    
    # 6. ChiTietNguyenLieu (Recipe-Ingredient mapping)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ChiTietNguyenLieu (
            MaChiTiet SERIAL PRIMARY KEY,
            MaCongThuc INTEGER REFERENCES CongThuc(MaCongThuc) ON DELETE CASCADE,
            MaNguyenLieu INTEGER REFERENCES NguyenLieu(MaNguyenLieu) ON DELETE CASCADE,
            SoLuong VARCHAR(100)
        )
    """)
    print("  [OK] Bang ChiTietNguyenLieu")
    
    # 7. LichSu (History)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS LichSu (
            MaLichSu SERIAL PRIMARY KEY,
            MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
            DuongDanAnh TEXT,
            TenMonAn VARCHAR(255),
            DoChinhXac DECIMAL(5,2),
            ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            Calo DECIMAL(10,2) DEFAULT 0,
            DaAn BOOLEAN DEFAULT FALSE,
            DanhGiaNguoiDung INTEGER,
            KhuyenNghiKeHoach TEXT
        )
    """)
    print("  [OK] Bang LichSu")
    
    # 8. HoSoSucKhoe (Health Profile)
    cursor.execute("""
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
        )
    """)
    print("  [OK] Bang HoSoSucKhoe")

    # 8b. LichSuCanNang (Weight History)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS LichSuCanNang (
            MaLichSuCN SERIAL PRIMARY KEY,
            MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
            CanNang DECIMAL(5,2) NOT NULL,
            ChieuCao DECIMAL(5,2),
            BMI DECIMAL(5,2),
            PhanLoaiBMI VARCHAR(30),
            GhiChu TEXT,
            ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_lscn_user_time
        ON LichSuCanNang(MaNguoiDung, ThoiGian DESC)
    """)
    print("  [OK] Bang LichSuCanNang")

    # 9. BinhLuan (Comments)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS BinhLuan (
            MaBinhLuan SERIAL PRIMARY KEY,
            MaLichSu INTEGER REFERENCES LichSu(MaLichSu) ON DELETE CASCADE,
            MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
            NoiDung TEXT NOT NULL,
            ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            MaBinhLuanCha INTEGER REFERENCES BinhLuan(MaBinhLuan) ON DELETE CASCADE
        )
    """)
    print("  [OK] Bang BinhLuan")
    
    # 10. ThongBao (Notifications)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ThongBao (
            MaThongBao SERIAL PRIMARY KEY,
            MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
            MaLichSu INTEGER REFERENCES LichSu(MaLichSu) ON DELETE SET NULL,
            NoiDung TEXT NOT NULL,
            TenCu VARCHAR(255) DEFAULT '',
            TenMoi VARCHAR(255) DEFAULT '',
            DaDoc BOOLEAN DEFAULT FALSE,
            ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  [OK] Bang ThongBao")

    # 11. KeHoachDinhDuong (Nutrition Plans)
    cursor.execute("""
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
        )
    """)
    print("  [OK] Bang KeHoachDinhDuong")

    # 12. ThanhToan (Payment Transactions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ThanhToan (
            MaThanhToan SERIAL PRIMARY KEY,
            MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
            MaDonHang VARCHAR(100) UNIQUE NOT NULL,
            SoTien DECIMAL(15,2) NOT NULL,
            GoiNangCap VARCHAR(50) DEFAULT 'premium',
            TrangThai VARCHAR(20) DEFAULT 'pending',
            PhuongThuc VARCHAR(20) DEFAULT 'momo',
            MomoTransId VARCHAR(100),
            ResponseData TEXT,
            ThoiGianTao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ThoiGianCapNhat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  [OK] Bang ThanhToan")

    conn.commit()
    print("\n[OK] Da tao xong tat ca 13 bang!")
    
    # ============================================
    # TAO TAI KHOAN ADMIN MAC DINH
    # ============================================
    print("\nDang tao tai khoan admin mac dinh...")
    
    from werkzeug.security import generate_password_hash
    
    admin_email = "admin@smartfoodai.com"
    admin_password = generate_password_hash("admin123")
    admin_name = "Admin"
    
    try:
        cursor.execute("""
            INSERT INTO NguoiDung (TenNguoiDung, Email, MatKhau, VaiTro)
            VALUES (%s, %s, %s, 'admin')
            ON CONFLICT (Email) DO NOTHING
        """, (admin_name, admin_email, admin_password))
        conn.commit()
        print(f"  [OK] Tai khoan admin da tao:")
        print(f"       Email:    {admin_email}")
        print(f"       Password: admin123")
    except Exception as e:
        print(f"  [WARNING] Loi tao admin: {e}")
    
    # ============================================
    # KIEM TRA KET QUA
    # ============================================
    print("\n" + "=" * 60)
    print("KIEM TRA KET QUA")
    print("=" * 60)
    
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    print(f"\nTim thay {len(tables)} bang:")
    for t in tables:
        cursor.execute(f'SELECT COUNT(*) FROM "{t[0]}"')
        count = cursor.fetchone()[0]
        print(f"  - {t[0]} ({count} records)")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("HOAN TAT! Database da san sang su dung.")
    print("=" * 60)
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
