"""
Database Queries for PostgreSQL
Thay thế SQLite bằng PostgreSQL
Với Retry Logic mạnh mẽ cho Render free tier
"""

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor
import os
import time
import functools
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

# ============================================
# CONNECTION & RETRY LOGIC
# Xử lý triệt để lỗi "SSL connection has been closed unexpectedly"
# trên Render free tier (server hay ngắt kết nối idle)
# ============================================

def _get_db_url():
    """Lấy DATABASE_URL với sslmode=require"""
    db_url = DATABASE_URL
    if db_url and 'sslmode' not in db_url:
        separator = '&' if '?' in db_url else '?'
        db_url = f"{db_url}{separator}sslmode=require"
    return db_url

def get_db_connection():
    """Kết nối PostgreSQL với retry logic mạnh mẽ và TCP keepalive.
    
    - Retry 3 lần với exponential backoff
    - Bắt cả OperationalError và InterfaceError  
    - TCP keepalive để phát hiện connection chết sớm
    - Health check connection trước khi trả về
    """
    db_url = _get_db_url()
    if not db_url:
        raise Exception("DATABASE_URL chưa được cấu hình")
    
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = psycopg2.connect(
                db_url,
                connect_timeout=15,
                # TCP keepalive: phát hiện connection chết nhanh hơn
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3
            )
            conn.set_session(autocommit=False)
            
            # Health check: đảm bảo connection thực sự hoạt động
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.execute("SET timezone = 'Asia/Ho_Chi_Minh'")
            conn.commit()
            cursor.close()
            
            return conn
            
        except (psycopg2.OperationalError, psycopg2.InterfaceError, OSError) as e:
            last_error = e
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            print(f"[DB] Kết nối thất bại (lần {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 2s, 4s
                time.sleep(wait_time)
            else:
                raise
        except Exception as e:
            last_error = e
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            print(f"[DB] Lỗi không mong đợi khi kết nối (lần {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise

def close_db_connection(conn):
    """Đóng connection an toàn (alias cho conn.close() nhưng bắt exception)"""
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass

def retry_db_operation(max_retries=2):
    """Decorator: tự động retry khi DB operation bị SSL drop hoặc connection lỗi.
    
    Khi gặp lỗi kết nối (SSL drop, connection reset, etc.),
    tự động retry toàn bộ function (bao gồm tạo connection mới).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    last_error = e
                    error_msg = str(e).lower()
                    is_connection_error = any(keyword in error_msg for keyword in [
                        'ssl', 'connection', 'server closed', 'broken pipe',
                        'connection reset', 'network', 'timeout', 'eof',
                        'could not connect', 'terminating connection',
                        'closed unexpectedly', 'gone away'
                    ])
                    if is_connection_error and attempt < max_retries:
                        print(f"[DB RETRY] {func.__name__} lỗi kết nối (lần {attempt + 1}): {e}")
                        time.sleep((attempt + 1) * 2)
                    else:
                        raise
            raise last_error
        return wrapper
    return decorator

def get_db_cursor(conn):
    """Lấy cursor với RealDictCursor để trả về dict"""
    return conn.cursor(cursor_factory=RealDictCursor)

# ============================================
# USER MANAGEMENT
# ============================================

def create_user(name, email, hashed_password):
    """Tạo user mới"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            INSERT INTO NguoiDung (TenNguoiDung, Email, MatKhau, VaiTro)
            VALUES (%s, %s, %s, 'user')
            RETURNING MaNguoiDung
        """, (name, email, hashed_password))
        
        user_id = cursor.fetchone()['manguoidung']
        conn.commit()
        conn.close()
        
        return True, f"Đăng ký thành công! User ID: {user_id}", user_id
    except psycopg2.IntegrityError:
        if conn:
            conn.rollback()
            conn.close()
        return False, "Email đã tồn tại", None
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return False, f"Lỗi: {str(e)}", None

def get_user_by_email(email):
    """Lấy thông tin user theo email"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT MaNguoiDung, TenNguoiDung, Email, MatKhau, VaiTro, LoaiTaiKhoan, NgayHetHanPremium
            FROM NguoiDung
            WHERE Email = %s
        """, (email,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Check expiration
            loai_tk = user.get('loaitaikhoan', 'free') or 'free'
            ngay_het_han = user.get('ngayhethanpremium')
            remaining_days = 0
            
            if loai_tk == 'premium' and ngay_het_han:
                from datetime import datetime
                now = datetime.now()
                if ngay_het_han > now:
                    remaining_days = (ngay_het_han - now).days
                else:
                    loai_tk = 'free' # Should ideally update DB here too, but for read-only it's fine
                    
            return {
                'MaNguoiDung': user['manguoidung'],
                'TenNguoiDung': user['tennguoidung'],
                'Email': user['email'],
                'MatKhau': user['matkhau'],
                'VaiTro': user['vaitro'],
                'LoaiTaiKhoan': loai_tk,
                'RemainingDays': remaining_days
            }
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_user_by_id(user_id):
    """Lấy thông tin user theo ID"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT MaNguoiDung, TenNguoiDung, Email, MatKhau, VaiTro, LoaiTaiKhoan, NgayHetHanPremium
            FROM NguoiDung
            WHERE MaNguoiDung = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Check expiration
            loai_tk = user.get('loaitaikhoan', 'free') or 'free'
            ngay_het_han = user.get('ngayhethanpremium')
            remaining_days = 0
            
            if loai_tk == 'premium' and ngay_het_han:
                from datetime import datetime
                now = datetime.now()
                if ngay_het_han > now:
                    remaining_days = (ngay_het_han - now).days
                else:
                    loai_tk = 'free' # Temporary downgrade in memory
                    
            return {
                'MaNguoiDung': user['manguoidung'],
                'TenNguoiDung': user['tennguoidung'],
                'Email': user['email'],
                'MatKhau': user['matkhau'],
                'VaiTro': user['vaitro'],
                'LoaiTaiKhoan': loai_tk,
                'RemainingDays': remaining_days,
                'NgayHetHanPremium': ngay_het_han
            }
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def update_password(user_id, new_hashed_password):
    """Cập nhật mật khẩu"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE NguoiDung
            SET MatKhau = %s
            WHERE MaNguoiDung = %s
        """, (new_hashed_password, user_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def create_google_user(name, email, google_id):
    """Tạo user mới đăng ký bằng Google (không cần mật khẩu)"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            INSERT INTO NguoiDung (TenNguoiDung, Email, MatKhau, VaiTro, GoogleId)
            VALUES (%s, %s, %s, 'user', %s)
            RETURNING MaNguoiDung
        """, (name, email, 'GOOGLE_AUTH', google_id))
        
        user_id = cursor.fetchone()['manguoidung']
        conn.commit()
        conn.close()
        
        return True, f"Đăng ký Google thành công! User ID: {user_id}", user_id
    except psycopg2.IntegrityError:
        if conn:
            conn.rollback()
            conn.close()
        return False, "Email đã tồn tại", None
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return False, f"Lỗi: {str(e)}", None

def get_user_by_google_id(google_id):
    """Lấy thông tin user theo Google ID"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT MaNguoiDung, TenNguoiDung, Email, MatKhau, VaiTro, GoogleId, LoaiTaiKhoan, NgayHetHanPremium
            FROM NguoiDung
            WHERE GoogleId = %s
        """, (google_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Check expiration
            loai_tk = user.get('loaitaikhoan', 'free') or 'free'
            ngay_het_han = user.get('ngayhethanpremium')
            remaining_days = 0
            
            if loai_tk == 'premium' and ngay_het_han:
                from datetime import datetime
                now = datetime.now()
                if ngay_het_han > now:
                    remaining_days = (ngay_het_han - now).days
                else:
                    loai_tk = 'free' # Temporary downgrade in memory
                    
            return {
                'MaNguoiDung': user['manguoidung'],
                'TenNguoiDung': user['tennguoidung'],
                'Email': user['email'],
                'MatKhau': user['matkhau'],
                'VaiTro': user['vaitro'],
                'GoogleId': user.get('googleid'),
                'LoaiTaiKhoan': loai_tk,
                'RemainingDays': remaining_days
            }
        return None
    except Exception as e:
        print(f"Error get_user_by_google_id: {e}")
        return None

def update_user_google_id(user_id, google_id):
    """Cập nhật GoogleId cho user đã có (liên kết tài khoản Google)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE NguoiDung
            SET GoogleId = %s
            WHERE MaNguoiDung = %s
        """, (google_id, user_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error update_user_google_id: {e}")
        return False

# ============================================
# FOOD MANAGEMENT
# ============================================

@retry_db_operation(max_retries=2)
def search_food_by_name(food_name):
    """Tìm món ăn theo tên (hỗ trợ tiếng Việt)"""
    try:
        from food_translator import get_search_variants
        from unicode_utils import normalize_for_search
    except ImportError:
        from backend.food_translator import get_search_variants
        from backend.unicode_utils import normalize_for_search
    
    search_variants = get_search_variants(food_name)
    print(f"[SEARCH] Searching for: '{food_name}'")
    print(f"[SEARCH] Variants: {search_variants}")
    
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    
    try:
        # Priority 1: Exact match
        for variant in search_variants:
            cursor.execute("""
                SELECT * FROM MonAn 
                WHERE LOWER(TenMonAn) = LOWER(%s) AND IsDeleted = 0
                LIMIT 1
            """, (variant,))
            
            mon_an = cursor.fetchone()
            if mon_an:
                print(f"[SEARCH] Exact match: '{variant}'")
                result = format_food_data(mon_an, cursor, conn)
                conn.close()
                return result
        
        # Priority 2: Starts-with match (chính xác hơn contains)
        for variant in search_variants:
            cursor.execute("""
                SELECT * FROM MonAn 
                WHERE LOWER(TenMonAn) LIKE LOWER(%s) AND IsDeleted = 0
                ORDER BY LENGTH(TenMonAn) ASC
                LIMIT 1
            """, (f'{variant}%',))
            
            mon_an = cursor.fetchone()
            if mon_an:
                print(f"[SEARCH] Starts-with match: '{variant}' -> '{mon_an['tenmonan']}'")
                result = format_food_data(mon_an, cursor, conn)
                conn.close()
                return result
        
        # Priority 3: Contains match (rộng nhất, ưu tiên tên ngắn nhất)
        for variant in search_variants:
            cursor.execute("""
                SELECT * FROM MonAn 
                WHERE LOWER(TenMonAn) LIKE LOWER(%s) AND IsDeleted = 0
                ORDER BY LENGTH(TenMonAn) ASC
                LIMIT 1
            """, (f'%{variant}%',))
            
            mon_an = cursor.fetchone()
            if mon_an:
                print(f"[SEARCH] Contains match: '{variant}' -> '{mon_an['tenmonan']}'")
                result = format_food_data(mon_an, cursor, conn)
                conn.close()
                return result

        # Priority 4: Reverse Contains match (AI name contains DB name, e.g., AI="Gỏi cuốn tôm thịt" -> DB="Gỏi Cuốn")
        # Phải dùng '%%' để psycopg2 không hiểu nhầm là param format
        for variant in search_variants:
            cursor.execute("""
                SELECT * FROM MonAn 
                WHERE LOWER(%s) LIKE '%%' || LOWER(TenMonAn) || '%%' AND IsDeleted = 0
                ORDER BY LENGTH(TenMonAn) DESC
                LIMIT 1
            """, (variant,))
            
            mon_an = cursor.fetchone()
            if mon_an:
                print(f"[SEARCH] Reverse match: DB '{mon_an['tenmonan']}' is inside '{variant}'")
                result = format_food_data(mon_an, cursor, conn)
                conn.close()
                return result
        
        print(f"[SEARCH] No match found")
        conn.close()
        return None
    except Exception as e:
        print(f"[SEARCH ERROR] {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        return None

def format_food_data(mon_an, cursor, conn):
    """Format dữ liệu món ăn với dinh dưỡng, công thức, nguyên liệu"""
    ma_mon_an = mon_an['mamonan']
    
    # Get nutrition
    cursor.execute("SELECT * FROM DinhDuong WHERE MaMonAn = %s", (ma_mon_an,))
    dinh_duong = cursor.fetchone()
    
    # Get recipe
    cursor.execute("SELECT * FROM CongThuc WHERE MaMonAn = %s", (ma_mon_an,))
    cong_thuc = cursor.fetchone()
    
    # Get ingredients
    nguyen_lieu = []
    if cong_thuc:
        ma_cong_thuc = cong_thuc['macongthuc']
        cursor.execute("""
            SELECT nl.TenNguyenLieu, ctnl.SoLuong 
            FROM ChiTietNguyenLieu ctnl
            JOIN NguyenLieu nl ON ctnl.MaNguyenLieu = nl.MaNguyenLieu
            WHERE ctnl.MaCongThuc = %s
        """, (ma_cong_thuc,))
        
        ingredients = cursor.fetchall()
        nguyen_lieu = [
            {
                'TenNguyenLieu': ing['tennguyenlieu'],
                'SoLuong': ing['soluong']
            }
            for ing in ingredients
        ]
    
    # Don't close connection here - let caller handle it
    
    result = {
        'MaMonAn': ma_mon_an,
        'TenMonAn': mon_an['tenmonan'],
        'MoTa': mon_an['mota'] or '',
        'PhanLoai': mon_an['phanloai'] or '',
        'IsDeleted': mon_an.get('isdeleted', False),
        'DinhDuong': {
            'Calo': float(dinh_duong['calo']) if dinh_duong and dinh_duong['calo'] else 0,
            'Protein': float(dinh_duong['protein']) if dinh_duong and dinh_duong['protein'] else 0,
            'ChatBeo': float(dinh_duong['chatbeo']) if dinh_duong and dinh_duong['chatbeo'] else 0,
            'Carbohydrate': float(dinh_duong['carbohydrate']) if dinh_duong and dinh_duong['carbohydrate'] else 0,
            'Vitamin': dinh_duong['vitamin'] if dinh_duong else ''
        } if dinh_duong else {
            'Calo': 0,
            'Protein': 0,
            'ChatBeo': 0,
            'Carbohydrate': 0,
            'Vitamin': ''
        },
        'CongThuc': {
            'HuongDan': cong_thuc['huongdan'] if cong_thuc else '',
            'ThoiGianNau': cong_thuc['thoigiannau'] if cong_thuc else 0,
            'KhauPhan': cong_thuc['khauphan'] if cong_thuc else 0,
            'NguyenLieu': nguyen_lieu
        } if cong_thuc else {
            'HuongDan': '',
            'ThoiGianNau': 0,
            'KhauPhan': 0,
            'NguyenLieu': []
        }
    }
    
    return result

@retry_db_operation(max_retries=2)
def insert_food_full(food_data):
    """Thêm món ăn mới với đầy đủ thông tin"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prevent duplicate
        cursor.execute("SELECT MaMonAn FROM MonAn WHERE LOWER(TenMonAn) = LOWER(%s) AND IsDeleted = 0", (food_data['TenMonAn'],))
        if cursor.fetchone():
            print(f"[SKIP] Món '{food_data['TenMonAn']}' đã tồn tại trong database.")
            conn.close()
            return False
        
        # Insert MonAn
        cursor.execute("""
            INSERT INTO MonAn (TenMonAn, MoTa, PhanLoai)
            VALUES (%s, %s, %s)
            RETURNING MaMonAn
        """, (
            food_data['TenMonAn'],
            food_data.get('MoTa', ''),
            food_data.get('PhanLoai', 'Món ăn')
        ))
        
        ma_mon_an = cursor.fetchone()[0]
        
        # Insert DinhDuong
        if 'DinhDuong' in food_data:
            dd = food_data['DinhDuong']
            cursor.execute("""
                INSERT INTO DinhDuong (MaMonAn, Calo, Protein, ChatBeo, Carbohydrate, Vitamin)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                ma_mon_an,
                dd.get('Calo', 0),
                dd.get('Protein', 0),
                dd.get('ChatBeo', 0),
                dd.get('Carbohydrate', 0),
                dd.get('Vitamin', '')
            ))
        
        # Insert CongThuc
        if 'CongThuc' in food_data:
            ct = food_data['CongThuc']
            cursor.execute("""
                INSERT INTO CongThuc (MaMonAn, HuongDan, ThoiGianNau, KhauPhan)
                VALUES (%s, %s, %s, %s)
                RETURNING MaCongThuc
            """, (
                ma_mon_an,
                ct.get('HuongDan', ''),
                ct.get('ThoiGianNau', 30),
                ct.get('KhauPhan', 1)
            ))
            
            ma_cong_thuc = cursor.fetchone()[0]
            
            # Insert NguyenLieu
            if 'NguyenLieu' in ct:
                for nl in ct['NguyenLieu']:
                    # Insert or get NguyenLieu
                    cursor.execute("""
                        INSERT INTO NguyenLieu (TenNguyenLieu)
                        VALUES (%s)
                        ON CONFLICT DO NOTHING
                        RETURNING MaNguyenLieu
                    """, (nl['TenNguyenLieu'],))
                    
                    result = cursor.fetchone()
                    if result:
                        ma_nguyen_lieu = result[0]
                    else:
                        cursor.execute("""
                            SELECT MaNguyenLieu FROM NguyenLieu
                            WHERE TenNguyenLieu = %s
                        """, (nl['TenNguyenLieu'],))
                        ma_nguyen_lieu = cursor.fetchone()[0]
                    
                    # Insert ChiTietNguyenLieu
                    cursor.execute("""
                        INSERT INTO ChiTietNguyenLieu (MaCongThuc, MaNguyenLieu, SoLuong)
                        VALUES (%s, %s, %s)
                    """, (ma_cong_thuc, ma_nguyen_lieu, nl['SoLuong']))
        
        conn.commit()
        conn.close()
        
        print(f"[SUCCESS] Đã thêm món '{food_data['TenMonAn']}' vào database")
        return True
        
    except Exception as e:
        print(f"[ERROR] Lỗi khi thêm món ăn: {e}")
        return False

# ============================================
# HISTORY
# ============================================

@retry_db_operation(max_retries=2)
def insert_lich_su(user_id, image_path, food_name, accuracy, calories=0):
    """Lưu lịch sử nhận diện - trả về MaLichSu ID"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            INSERT INTO LichSu (MaNguoiDung, DuongDanAnh, TenMonAn, DoChinhXac, Calo)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING MaLichSu
        """, (user_id, image_path, food_name, accuracy, calories))
        
        result = cursor.fetchone()
        history_id = result['malichsu'] if result else None
        conn.commit()
        conn.close()
        return history_id
    except Exception as e:
        print(f"Error inserting history: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_user_history(user_id):
    """Lấy lịch sử nhận diện của user (bao gồm ảnh, calories và số bình luận)"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT MaLichSu, TenMonAn, DoChinhXac, ThoiGian, DuongDanAnh, Calo, KhuyenNghiKeHoach
            FROM LichSu
            WHERE MaNguoiDung = %s
            ORDER BY ThoiGian DESC
            LIMIT 50
        """, (user_id,))
        
        history = cursor.fetchall()
        
        result = []
        for h in history:
            # Đếm bình luận
            comment_count = 0
            try:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM BinhLuan 
                    WHERE MaLichSu = %s
                """, (h['malichsu'],))
                comment_count = cursor.fetchone()['count'] or 0
            except:
                pass
            
            # Parse plan_advice JSON
            plan_advice = None
            if h.get('khuyennghikehoach'):
                try:
                    import json
                    plan_advice = json.loads(h['khuyennghikehoach'])
                except:
                    pass
            
            result.append({
                'id': h['malichsu'],
                'food_name': h['tenmonan'],
                'accuracy': float(h['dochinhxac']) if h['dochinhxac'] else 0,
                'time': h['thoigian'].strftime('%Y-%m-%d %H:%M:%S') if h['thoigian'] else '',
                'image': h.get('duongdananh', '') or '',
                'calories': float(h['calo']) if h.get('calo') else 0,
                'comment_count': comment_count,
                'plan_advice': plan_advice
            })
        
        conn.close()
        return result
    except Exception as e:
        print(f"Error getting user history: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_user_food_stats(user_id):
    """Thống kê calories theo ngày/tuần cho user"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # 1. Calories theo từng ngày (30 ngày gần nhất)
        cursor.execute("""
            SELECT DATE(ThoiGian) as ngay,
                   SUM(CASE WHEN DaAn = TRUE THEN Calo ELSE 0 END) as tong_calo,
                   COUNT(*) as so_mon
            FROM LichSu
            WHERE MaNguoiDung = %s 
              AND ThoiGian >= CURRENT_DATE - INTERVAL '30 days'
              AND Calo > 0
            GROUP BY DATE(ThoiGian)
            ORDER BY ngay DESC
        """, (user_id,))
        
        daily_stats = []
        for row in cursor.fetchall():
            daily_stats.append({
                'date': row['ngay'].strftime('%Y-%m-%d') if row['ngay'] else '',
                'total_calories': float(row['tong_calo']) if row['tong_calo'] else 0,
                'food_count': row['so_mon'] or 0
            })
        
        # 2. Calories theo tuần (4 tuần gần nhất)
        cursor.execute("""
            SELECT DATE_TRUNC('week', ThoiGian)::date as tuan,
                   SUM(CASE WHEN DaAn = TRUE THEN Calo ELSE 0 END) as tong_calo,
                   COUNT(*) as so_mon
            FROM LichSu
            WHERE MaNguoiDung = %s 
              AND ThoiGian >= CURRENT_DATE - INTERVAL '28 days'
              AND Calo > 0
            GROUP BY DATE_TRUNC('week', ThoiGian)
            ORDER BY tuan DESC
        """, (user_id,))
        
        weekly_stats = []
        for row in cursor.fetchall():
            weekly_stats.append({
                'week_start': row['tuan'].strftime('%Y-%m-%d') if row['tuan'] else '',
                'total_calories': float(row['tong_calo']) if row['tong_calo'] else 0,
                'food_count': row['so_mon'] or 0
            })
        
        # 3. Tổng calories hôm nay
        cursor.execute("""
            SELECT SUM(CASE WHEN DaAn = TRUE THEN Calo ELSE 0 END) as tong_calo, COUNT(*) as so_mon
            FROM LichSu
            WHERE MaNguoiDung = %s 
              AND DATE(ThoiGian) = CURRENT_DATE
              AND Calo > 0
        """, (user_id,))
        
        today = cursor.fetchone()
        today_calories = float(today['tong_calo']) if today and today['tong_calo'] else 0
        today_count = today['so_mon'] if today else 0
        
        # 4. Top món ăn thường xuyên nhất
        cursor.execute("""
            SELECT TenMonAn, COUNT(*) as so_lan, AVG(Calo) as calo_tb
            FROM LichSu
            WHERE MaNguoiDung = %s AND Calo > 0
            GROUP BY TenMonAn
            ORDER BY so_lan DESC
            LIMIT 5
        """, (user_id,))
        
        top_foods = []
        for row in cursor.fetchall():
            top_foods.append({
                'name': row['tenmonan'],
                'count': row['so_lan'] or 0,
                'avg_calories': round(float(row['calo_tb']), 1) if row['calo_tb'] else 0
            })
        
        # 5. Tổng tất cả
        cursor.execute("""
            SELECT COUNT(*) as tong_mon, SUM(Calo) as tong_calo
            FROM LichSu
            WHERE MaNguoiDung = %s
        """, (user_id,))
        
        total = cursor.fetchone()
        
        conn.close()
        
        return {
            'today_calories': today_calories,
            'today_count': today_count,
            'daily': daily_stats,
            'weekly': weekly_stats,
            'top_foods': top_foods,
            'total_foods': total['tong_mon'] if total else 0,
            'total_calories': float(total['tong_calo']) if total and total['tong_calo'] else 0
        }
    except Exception as e:
        print(f"Error getting food stats: {e}")
        import traceback
        traceback.print_exc()
        return {
            'today_calories': 0,
            'today_count': 0,
            'daily': [],
            'weekly': [],
            'top_foods': [],
            'total_foods': 0,
            'total_calories': 0
        }

# ============================================
# ADMIN FUNCTIONS
# ============================================

def get_all_users():
    """Lấy danh sách tất cả users kèm thống kê"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT n.MaNguoiDung, n.TenNguoiDung, n.Email, n.VaiTro, n.NgayDangKy,
                   n.GoogleId, n.LastActive, n.LoaiTaiKhoan, n.NgayNangCap,
                   COUNT(l.MaLichSu) as analysis_count
            FROM NguoiDung n
            LEFT JOIN LichSu l ON n.MaNguoiDung = l.MaNguoiDung
            GROUP BY n.MaNguoiDung, n.TenNguoiDung, n.Email, n.VaiTro, n.NgayDangKy, n.GoogleId, n.LastActive, n.LoaiTaiKhoan, n.NgayNangCap
            ORDER BY n.NgayDangKy DESC
        """)
        
        users = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': u['manguoidung'],
                'name': u['tennguoidung'],
                'email': u['email'],
                'role': u['vaitro'],
                'created_at': u['ngaydangky'].strftime('%Y-%m-%d') if u['ngaydangky'] else '',
                'google_id': u.get('googleid') or None,
                'auth_provider': 'google' if u.get('googleid') else 'local',
                'last_active': u['lastactive'].strftime('%Y-%m-%d %H:%M:%S') if u.get('lastactive') else None,
                'analysis_count': u.get('analysis_count', 0) or 0,
                'account_type': u.get('loaitaikhoan', 'free') or 'free',
                'upgrade_date': u['ngaynangcap'].strftime('%Y-%m-%d %H:%M:%S') if u.get('ngaynangcap') else None
            }
            for u in users
        ]
    except Exception as e:
        print(f"Error getting users: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_user_detail_admin(user_id):
    """Lấy chi tiết user cho admin: thông tin + health profile + lịch sử gần đây"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # 1. Thông tin user
        cursor.execute("""
            SELECT MaNguoiDung, TenNguoiDung, Email, VaiTro, NgayDangKy, GoogleId, LastActive, LoaiTaiKhoan, NgayNangCap
            FROM NguoiDung
            WHERE MaNguoiDung = %s
        """, (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return None
        
        # 2. Thống kê phân tích
        cursor.execute("""
            SELECT COUNT(*) as total_analyses,
                   COALESCE(AVG(Calo), 0) as avg_calories,
                   MIN(ThoiGian) as first_analysis,
                   MAX(ThoiGian) as last_analysis
            FROM LichSu
            WHERE MaNguoiDung = %s
        """, (user_id,))
        stats = cursor.fetchone()
        
        # 3. Health Profile (BMI/BMR)
        cursor.execute("""
            SELECT CanNang, ChieuCao, Tuoi, GioiTinh, MucDoVanDong, MucTieu, BMR, TDEE, CaloDuKien
            FROM HoSoSucKhoe
            WHERE MaNguoiDung = %s
            ORDER BY NgayCapNhat DESC
            LIMIT 1
        """, (user_id,))
        health = cursor.fetchone()
        
        # 4. Lịch sử hoạt động gần đây (10 records)
        cursor.execute("""
            SELECT MaLichSu, TenMonAn, Calo, ThoiGian, DanhGiaNguoiDung
            FROM LichSu
            WHERE MaNguoiDung = %s
            ORDER BY ThoiGian DESC
            LIMIT 10
        """, (user_id,))
        recent_history = cursor.fetchall()
        
        conn.close()
        
        # Build BMI
        bmi = None
        bmi_status = ''
        if health and health.get('cannang') and health.get('chieucao'):
            h_m = float(health['chieucao']) / 100
            if h_m > 0:
                bmi = round(float(health['cannang']) / (h_m * h_m), 1)
                if bmi < 18.5: bmi_status = 'Thiếu cân'
                elif bmi < 25: bmi_status = 'Bình thường'
                elif bmi < 30: bmi_status = 'Thừa cân'
                else: bmi_status = 'Béo phì'
        
        result = {
            'id': user['manguoidung'],
            'name': user['tennguoidung'],
            'email': user['email'],
            'role': user['vaitro'],
            'created_at': user['ngaydangky'].strftime('%Y-%m-%d %H:%M:%S') if user['ngaydangky'] else '',
            'auth_provider': 'google' if user.get('googleid') else 'local',
            'last_active': user['lastactive'].strftime('%Y-%m-%d %H:%M:%S') if user['lastactive'] else None,
            'account_type': user.get('loaitaikhoan', 'free') or 'free',
            'upgrade_date': user['ngaynangcap'].strftime('%Y-%m-%d %H:%M:%S') if user['ngaynangcap'] else None,
            'stats': {
                'total_analyses': stats['total_analyses'] if stats else 0,
                'avg_calories': round(float(stats['avg_calories']), 1) if stats and stats['avg_calories'] else 0,
                'first_analysis': stats['first_analysis'].strftime('%Y-%m-%d') if stats and stats.get('first_analysis') else None,
                'last_analysis': stats['last_analysis'].strftime('%Y-%m-%d %H:%M') if stats and stats.get('last_analysis') else None
            },
            'health': None,
            'recent_history': []
        }
        
        if health:
            result['health'] = {
                'weight': float(health['cannang']) if health.get('cannang') else 0,
                'height': float(health['chieucao']) if health.get('chieucao') else 0,
                'age': health.get('tuoi'),
                'gender': health.get('gioitinh'),
                'activity': health.get('mucdovandong'),
                'goal': health.get('muctieu'),
                'bmr': round(float(health['bmr']), 1) if health.get('bmr') else 0,
                'tdee': round(float(health['tdee']), 1) if health.get('tdee') else 0,
                'target_cal': round(float(health['calodukien']), 1) if health.get('calodukien') else 0,
                'bmi': bmi,
                'bmi_status': bmi_status
            }
        
        for h in recent_history:
            result['recent_history'].append({
                'id': h['malichsu'],
                'food_name': h['tenmonan'],
                'calories': float(h['calo']) if h.get('calo') else 0,
                'time': h['thoigian'].strftime('%Y-%m-%d %H:%M') if h.get('thoigian') else '',
                'rating': h.get('danhgianguoidung')
            })
        
        return result
    except Exception as e:
        print(f"Error get_user_detail_admin: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_last_active(user_id):
    """Cập nhật thời gian hoạt động cuối cùng"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE NguoiDung SET LastActive = CURRENT_TIMESTAMP WHERE MaNguoiDung = %s
        """, (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error update_last_active: {e}")

def delete_user(user_id):
    """Xóa user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM NguoiDung WHERE MaNguoiDung = %s", (user_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def get_system_stats():
    """Lấy thống kê hệ thống + tổng hợp bình luận phản hồi"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # Count users
        cursor.execute("SELECT COUNT(*) as count FROM NguoiDung")
        total_users = cursor.fetchone()['count']
        
        # Count foods
        cursor.execute("SELECT COUNT(*) as count FROM MonAn WHERE IsDeleted = 0")
        total_foods = cursor.fetchone()['count']
        
        # Count history
        cursor.execute("SELECT COUNT(*) as count FROM LichSu")
        total_scans = cursor.fetchone()['count']
        
        # Comment aggregation
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE MaBinhLuanCha IS NULL) as total_comments,
                    COUNT(*) FILTER (WHERE MaBinhLuanCha IS NOT NULL) as total_replies
                FROM BinhLuan
            """)
            comment_row = cursor.fetchone()
            total_comments = comment_row['total_comments'] or 0
            total_replies = comment_row['total_replies'] or 0
            
            # Đếm bình luận chưa được phản hồi
            cursor.execute("""
                SELECT COUNT(*) as count FROM BinhLuan b
                WHERE b.MaBinhLuanCha IS NULL
                AND NOT EXISTS (
                    SELECT 1 FROM BinhLuan r WHERE r.MaBinhLuanCha = b.MaBinhLuan
                )
            """)
            pending_comments = cursor.fetchone()['count'] or 0
        except:
            total_comments = 0
            total_replies = 0
            pending_comments = 0
        
        # Recent comments (10 bình luận gần nhất)
        recent_comments = []
        try:
            cursor.execute("""
                SELECT b.MaBinhLuan, b.NoiDung, b.ThoiGian, b.MaLichSu,
                       n.TenNguoiDung, l.TenMonAn,
                       (SELECT COUNT(*) FROM BinhLuan r WHERE r.MaBinhLuanCha = b.MaBinhLuan) as reply_count
                FROM BinhLuan b
                LEFT JOIN NguoiDung n ON b.MaNguoiDung = n.MaNguoiDung
                LEFT JOIN LichSu l ON b.MaLichSu = l.MaLichSu
                WHERE b.MaBinhLuanCha IS NULL
                ORDER BY b.ThoiGian DESC
                LIMIT 10
            """)
            for r in cursor.fetchall():
                recent_comments.append({
                    'id': r['mabinhluan'],
                    'content': r['noidung'],
                    'user_name': r['tennguoidung'] or 'Ẩn danh',
                    'food_name': r['tenmonan'] or 'Không rõ',
                    'history_id': r['malichsu'],
                    'reply_count': r['reply_count'] or 0,
                    'time': r['thoigian'].strftime('%d/%m/%Y %H:%M') if r['thoigian'] else ''
                })
        except:
            pass
        
        conn.close()
        
        # Count premium users
        try:
            conn2 = get_db_connection()
            cursor2 = get_db_cursor(conn2)
            cursor2.execute("SELECT COUNT(*) as count FROM NguoiDung WHERE LoaiTaiKhoan = 'premium'")
            premium_row = cursor2.fetchone()
            premium_users = premium_row['count'] if premium_row else 0
            conn2.close()
        except:
            premium_users = 0
            
        # Top foods recognized
        top_foods = []
        try:
            conn3 = get_db_connection()
            cursor3 = get_db_cursor(conn3)
            cursor3.execute("""
                SELECT TenMonAn, COUNT(*) as count 
                FROM LichSu 
                GROUP BY TenMonAn 
                ORDER BY count DESC 
                LIMIT 10
            """)
            for r in cursor3.fetchall():
                top_foods.append({'name': r['tenmonan'], 'count': r['count']})
            conn3.close()
        except:
            pass
        
        return {
            'total_users': total_users,
            'total_foods': total_foods,
            'total_recognitions': total_scans,
            'premium_users': premium_users,
            'comments': {
                'total': total_comments,
                'replied': total_comments - pending_comments,
                'pending': pending_comments,
                'total_replies': total_replies
            },
            'recent_comments': recent_comments,
            'top_foods': top_foods
        }
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total_users': 0, 'total_foods': 0, 'total_recognitions': 0,
            'comments': {'total': 0, 'replied': 0, 'pending': 0, 'total_replies': 0},
            'recent_comments': [],
            'top_foods': []
        }

def get_all_history_admin():
    """Lấy tất cả lịch sử (admin) - bao gồm ảnh và calo"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT l.MaLichSu, n.TenNguoiDung, n.Email, l.TenMonAn, 
                   l.DoChinhXac, l.ThoiGian, l.DuongDanAnh, l.Calo
            FROM LichSu l
            LEFT JOIN NguoiDung n ON l.MaNguoiDung = n.MaNguoiDung
            ORDER BY l.ThoiGian DESC
            LIMIT 200
        """)
        
        history = cursor.fetchall()
        
        # Đếm comment cho mỗi history
        result = []
        for h in history:
            comment_count = 0
            try:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM BinhLuan 
                    WHERE MaLichSu = %s AND MaBinhLuanCha IS NULL
                """, (h['malichsu'],))
                comment_count = cursor.fetchone()['count'] or 0
            except:
                pass
            result.append({
                'id': h['malichsu'],
                'user_name': h['tennguoidung'] or 'Khách',
                'user_email': h.get('email', ''),
                'food_name': h['tenmonan'],
                'accuracy': float(h['dochinhxac']) if h['dochinhxac'] else 0,
                'time': h['thoigian'].strftime('%Y-%m-%d %H:%M:%S') if h['thoigian'] else '',
                'image': h.get('duongdananh', '') or '',
                'calories': float(h['calo']) if h.get('calo') else 0,
                'comment_count': comment_count
            })
        
        conn.close()
        return result
    except Exception as e:
        print(f"Error getting history: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_history_detail_admin(history_id):
    """Lấy chi tiết một bản ghi lịch sử (admin)"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT l.MaLichSu, l.MaNguoiDung, n.TenNguoiDung, n.Email,
                   l.TenMonAn, l.DoChinhXac, l.ThoiGian, l.DuongDanAnh, l.Calo
            FROM LichSu l
            LEFT JOIN NguoiDung n ON l.MaNguoiDung = n.MaNguoiDung
            WHERE l.MaLichSu = %s
        """, (history_id,))
        
        h = cursor.fetchone()
        
        if not h:
            conn.close()
            return None
        
        # Tìm thông tin dinh dưỡng từ bảng MonAn nếu có
        food_info = None
        if h['tenmonan']:
            food_name = h['tenmonan'].strip()
            food_row = None
            
            # Bước 1: Exact match
            cursor.execute("""
                SELECT m.MaMonAn, m.TenMonAn, m.MoTa, m.PhanLoai,
                       d.Calo, d.Protein, d.ChatBeo, d.Carbohydrate
                FROM MonAn m
                LEFT JOIN DinhDuong d ON m.MaMonAn = d.MaMonAn
                WHERE LOWER(m.TenMonAn) = LOWER(%s) AND m.IsDeleted = 0
                LIMIT 1
            """, (food_name,))
            food_row = cursor.fetchone()
            
            # Bước 2: Partial match - tên trong lịch sử chứa trong tên MonAn hoặc ngược lại
            if not food_row:
                cursor.execute("""
                    SELECT m.MaMonAn, m.TenMonAn, m.MoTa, m.PhanLoai,
                           d.Calo, d.Protein, d.ChatBeo, d.Carbohydrate
                    FROM MonAn m
                    LEFT JOIN DinhDuong d ON m.MaMonAn = d.MaMonAn
                    WHERE m.IsDeleted = 0
                      AND (LOWER(m.TenMonAn) LIKE LOWER(%s) OR LOWER(%s) LIKE '%%' || LOWER(m.TenMonAn) || '%%')
                    ORDER BY LENGTH(m.TenMonAn) ASC
                    LIMIT 1
                """, (f'%{food_name}%', food_name))
                food_row = cursor.fetchone()
            
            # Bước 3: Match từng từ trong tên món
            if not food_row and len(food_name) >= 2:
                words = food_name.split()
                for word in words:
                    if len(word) >= 2:
                        cursor.execute("""
                            SELECT m.MaMonAn, m.TenMonAn, m.MoTa, m.PhanLoai,
                                   d.Calo, d.Protein, d.ChatBeo, d.Carbohydrate
                            FROM MonAn m
                            LEFT JOIN DinhDuong d ON m.MaMonAn = d.MaMonAn
                            WHERE m.IsDeleted = 0
                              AND LOWER(m.TenMonAn) LIKE LOWER(%s)
                            ORDER BY LENGTH(m.TenMonAn) ASC
                            LIMIT 1
                        """, (f'%{word}%',))
                        food_row = cursor.fetchone()
                        if food_row:
                            break
            
            if food_row:
                food_info = {
                    'id': food_row['mamonan'],
                    'name': food_row['tenmonan'],
                    'description': food_row.get('mota', '') or '',
                    'category': food_row.get('phanloai', '') or '',
                    'calories': float(food_row['calo']) if food_row.get('calo') else 0,
                    'protein': float(food_row['protein']) if food_row.get('protein') else 0,
                    'fat': float(food_row['chatbeo']) if food_row.get('chatbeo') else 0,
                    'carbs': float(food_row['carbohydrate']) if food_row.get('carbohydrate') else 0,
                }
        
        # Lấy bình luận cho history này
        comments = []
        try:
            cursor.execute("""
                SELECT b.MaBinhLuan, b.NoiDung, b.ThoiGian, b.MaBinhLuanCha,
                       n.TenNguoiDung, n.VaiTro
                FROM BinhLuan b
                LEFT JOIN NguoiDung n ON b.MaNguoiDung = n.MaNguoiDung
                WHERE b.MaLichSu = %s
                ORDER BY b.ThoiGian ASC
            """, (h['malichsu'],))
            for c in cursor.fetchall():
                comments.append({
                    'id': c['mabinhluan'],
                    'content': c['noidung'],
                    'time': c['thoigian'].strftime('%d/%m/%Y %H:%M') if c['thoigian'] else '',
                    'user_name': c['tennguoidung'] or 'Ẩn danh',
                    'is_admin': c.get('vaitro') == 'admin',
                    'parent_id': c['mabinhluancha']
                })
        except:
            pass
        
        conn.close()
        
        return {
            'id': h['malichsu'],
            'user_id': h.get('manguoidung'),
            'user_name': h['tennguoidung'] or 'Khách',
            'user_email': h.get('email', '') or '',
            'food_name': h['tenmonan'],
            'accuracy': float(h['dochinhxac']) if h['dochinhxac'] else 0,
            'time': h['thoigian'].strftime('%Y-%m-%d %H:%M:%S') if h['thoigian'] else '',
            'image': h.get('duongdananh', '') or '',
            'calories': float(h['calo']) if h.get('calo') else 0,
            'comments': comments,
            'food_info': food_info
        }
    except Exception as e:
        print(f"Error getting history detail: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_all_foods_admin():
    """Lấy tất cả món ăn (admin)"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT m.MaMonAn, m.TenMonAn, m.PhanLoai, m.IsDeleted,
                   d.Calo, d.Protein
            FROM MonAn m
            LEFT JOIN DinhDuong d ON m.MaMonAn = d.MaMonAn
            ORDER BY m.MaMonAn DESC
        """)
        
        foods = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': f['mamonan'],
                'name': f['tenmonan'],
                'category': f['phanloai'],
                'calories': float(f['calo']) if f['calo'] else 0,
                'protein': float(f['protein']) if f['protein'] else 0,
                'is_deleted': f['isdeleted']
            }
            for f in foods
        ]
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_food_detail_admin(food_id):
    """Lấy chi tiết món ăn (admin)"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("SELECT * FROM MonAn WHERE MaMonAn = %s", (food_id,))
        mon_an = cursor.fetchone()
        
        if not mon_an:
            conn.close()
            return None
        
        result = format_food_data(mon_an, cursor, conn)
        conn.close()
        return result
    except Exception as e:
        print(f"Error getting food detail: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_food_full(food_id, food_data):
    """Cập nhật món ăn"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update MonAn
        cursor.execute("""
            UPDATE MonAn
            SET TenMonAn = %s, MoTa = %s, PhanLoai = %s, IsDeleted = %s
            WHERE MaMonAn = %s
        """, (
            food_data['TenMonAn'],
            food_data.get('MoTa', ''),
            food_data.get('PhanLoai', ''),
            food_data.get('IsDeleted', False),
            food_id
        ))
        
        # Update or insert DinhDuong
        if 'DinhDuong' in food_data:
            dd = food_data['DinhDuong']
            cursor.execute("""
                INSERT INTO DinhDuong (MaMonAn, Calo, Protein, ChatBeo, Carbohydrate, Vitamin)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (MaMonAn) DO UPDATE
                SET Calo = EXCLUDED.Calo,
                    Protein = EXCLUDED.Protein,
                    ChatBeo = EXCLUDED.ChatBeo,
                    Carbohydrate = EXCLUDED.Carbohydrate,
                    Vitamin = EXCLUDED.Vitamin
            """, (
                food_id,
                dd.get('Calo', 0),
                dd.get('Protein', 0),
                dd.get('ChatBeo', 0),
                dd.get('Carbohydrate', 0),
                dd.get('Vitamin', '')
            ))
        
        # Update or insert CongThuc
        if 'CongThuc' in food_data:
            ct = food_data['CongThuc']
            
            # Check if recipe exists
            cursor.execute("SELECT MaCongThuc FROM CongThuc WHERE MaMonAn = %s", (food_id,))
            existing_recipe = cursor.fetchone()
            
            if existing_recipe:
                ma_cong_thuc = existing_recipe[0]
                cursor.execute("""
                    UPDATE CongThuc
                    SET HuongDan = %s, ThoiGianNau = %s, KhauPhan = %s
                    WHERE MaCongThuc = %s
                """, (
                    ct.get('HuongDan', ''),
                    ct.get('ThoiGianNau', 30),
                    ct.get('KhauPhan', 1),
                    ma_cong_thuc
                ))
                
                # Delete old ingredients
                cursor.execute("DELETE FROM ChiTietNguyenLieu WHERE MaCongThuc = %s", (ma_cong_thuc,))
            else:
                cursor.execute("""
                    INSERT INTO CongThuc (MaMonAn, HuongDan, ThoiGianNau, KhauPhan)
                    VALUES (%s, %s, %s, %s)
                    RETURNING MaCongThuc
                """, (
                    food_id,
                    ct.get('HuongDan', ''),
                    ct.get('ThoiGianNau', 30),
                    ct.get('KhauPhan', 1)
                ))
                ma_cong_thuc = cursor.fetchone()[0]
            
            # Insert new ingredients
            if 'NguyenLieu' in ct:
                for nl in ct['NguyenLieu']:
                    if not nl.get('TenNguyenLieu'):
                        continue
                        
                    # Insert or get NguyenLieu
                    cursor.execute("""
                        INSERT INTO NguyenLieu (TenNguyenLieu)
                        VALUES (%s)
                        ON CONFLICT (TenNguyenLieu) DO NOTHING
                        RETURNING MaNguyenLieu
                    """, (nl['TenNguyenLieu'],))
                    
                    result = cursor.fetchone()
                    if result:
                        ma_nguyen_lieu = result[0]
                    else:
                        cursor.execute("""
                            SELECT MaNguyenLieu FROM NguyenLieu
                            WHERE TenNguyenLieu = %s
                        """, (nl['TenNguyenLieu'],))
                        ma_nguyen_lieu = cursor.fetchone()[0]
                    
                    # Insert ChiTietNguyenLieu
                    cursor.execute("""
                        INSERT INTO ChiTietNguyenLieu (MaCongThuc, MaNguyenLieu, SoLuong)
                        VALUES (%s, %s, %s)
                    """, (ma_cong_thuc, ma_nguyen_lieu, nl.get('SoLuong', '')))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating food: {e}")
        import traceback
        traceback.print_exc()
        return False

def delete_food_soft(food_id):
    """Soft delete món ăn"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE MonAn
            SET IsDeleted = 1
            WHERE MaMonAn = %s
        """, (food_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting food: {e}")
        import traceback
        traceback.print_exc()
        return False

def restore_food_soft(food_id):
    """Khôi phục món ăn"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE MonAn
            SET IsDeleted = 0
            WHERE MaMonAn = %s
        """, (food_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error restoring food: {e}")
        import traceback
        traceback.print_exc()
        return False

def delete_food_hard(food_id):
    """Xóa vĩnh viễn món ăn và tất cả dữ liệu liên quan"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Xóa ChiTietNguyenLieu (qua CongThuc)
        cursor.execute("""
            DELETE FROM ChiTietNguyenLieu
            WHERE MaCongThuc IN (
                SELECT MaCongThuc FROM CongThuc WHERE MaMonAn = %s
            )
        """, (food_id,))
        
        # 2. Xóa CongThuc
        cursor.execute("DELETE FROM CongThuc WHERE MaMonAn = %s", (food_id,))
        
        # 3. Xóa DinhDuong
        cursor.execute("DELETE FROM DinhDuong WHERE MaMonAn = %s", (food_id,))
        
        # 4. Xóa MonAn
        cursor.execute("DELETE FROM MonAn WHERE MaMonAn = %s", (food_id,))
        
        conn.commit()
        conn.close()
        print(f"[SUCCESS] Đã xóa vĩnh viễn món ăn ID={food_id}")
        return True
    except Exception as e:
        print(f"Error hard-deleting food: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================
# HEALTH PROFILE MANAGEMENT
# ============================================

def classify_bmi(bmi):
    """Phân loại thể trạng theo BMI. Trả về (category, color, recommendation, suggested_goal)."""
    if bmi < 18.5:
        return (
            "Gầy",
            "#3b82f6",
            "Bạn đang ở thể trạng gầy. Hãy tăng khẩu phần ăn lành mạnh, ưu tiên thực phẩm giàu protein, carbs phức hợp và chất béo tốt.",
            "Tăng cân"
        )
    if bmi < 25:
        return (
            "Bình thường",
            "#22c55e",
            "Bạn đang ở thể trạng bình thường. Hãy duy trì chế độ ăn cân đối và vận động đều đặn.",
            "Duy trì"
        )
    if bmi < 30:
        return (
            "Thừa cân",
            "#f59e0b",
            "Bạn đang ở thể trạng thừa cân. Hãy giảm lượng calo nạp vào (300-500 kcal/ngày), ưu tiên rau xanh và protein nạc.",
            "Giảm cân"
        )
    return (
        "Béo phì",
        "#ef4444",
        "Bạn đang ở thể trạng béo phì. Nên giảm cân an toàn 0.5-1kg/tuần, ưu tiên thực phẩm ít calo và tham vấn bác sĩ nếu có bệnh nền.",
        "Giảm cân"
    )


def build_weight_message(muc_tieu, diff):
    """Sinh thông điệp chúc mừng / khuyến nghị theo mục tiêu và mức chênh cân nặng (kg)."""
    abs_diff = abs(diff)
    abs_str = f"{abs_diff:.1f}"

    if muc_tieu == "Giảm cân":
        if diff < -0.3:
            return ("success",
                    "🎉 Chúc mừng giảm cân thành công!",
                    f"Bạn đã giảm {abs_str}kg so với lần trước. Tiếp tục duy trì kế hoạch dinh dưỡng nhé!")
        if diff > 0.3:
            return ("warning",
                    "💪 Cần cải thiện",
                    f"Cân nặng tăng {abs_str}kg so với mục tiêu giảm cân. Hãy xem lại lượng calo và tăng vận động.")
        return ("info",
                "Hãy kiên trì!",
                "Cân nặng chưa thay đổi đáng kể, tiếp tục bám sát kế hoạch để đạt mục tiêu.")

    if muc_tieu == "Tăng cân":
        if diff > 0.3:
            return ("success",
                    "🎉 Chúc mừng tăng cân thành công!",
                    f"Bạn đã tăng {abs_str}kg so với lần trước. Tiếp tục bổ sung dinh dưỡng đầy đủ nhé!")
        if diff < -0.3:
            return ("warning",
                    "💪 Cần cải thiện",
                    f"Cân nặng giảm {abs_str}kg so với mục tiêu tăng cân. Hãy bổ sung thêm calo và protein.")
        return ("info",
                "Hãy kiên trì!",
                "Cân nặng chưa thay đổi đáng kể, tiếp tục bám sát kế hoạch để đạt mục tiêu.")

    # Duy trì
    if abs_diff <= 1.0:
        return ("success",
                "🎯 Duy trì tốt!",
                f"Cân nặng dao động {abs_str}kg, vẫn nằm trong khoảng duy trì lành mạnh. Cố lên nhé!")
    return ("warning",
            "⚠️ Cần điều chỉnh",
            f"Cân nặng biến động {abs_str}kg so với lần trước, vượt khoảng duy trì cho phép. Hãy xem lại kế hoạch.")


@retry_db_operation(max_retries=2)
def get_health_profile(user_id):
    """Lấy hồ sơ sức khỏe của user"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT MaHoSo, MaNguoiDung, CanNang, ChieuCao, Tuoi, GioiTinh, 
                   MucDoVanDong, MucTieu, BMR, TDEE, CaloDuKien
            FROM HoSoSucKhoe
            WHERE MaNguoiDung = %s
            ORDER BY NgayCapNhat DESC
            LIMIT 1
        """, (user_id,))
        
        profile = cursor.fetchone()
        conn.close()
        
        if profile:
            # Map lowercase column names
            return {
                'MaHoSo': profile.get('mahoso'),
                'MaNguoiDung': profile.get('manguoidung'),
                'CanNang': float(profile.get('cannang')) if profile.get('cannang') else 0,
                'ChieuCao': float(profile.get('chieucao')) if profile.get('chieucao') else 0,
                'Tuoi': profile.get('tuoi'),
                'GioiTinh': profile.get('gioitinh'),
                'MucDoVanDong': profile.get('mucdovandong'),
                'MucTieu': profile.get('muctieu'),
                'BMR': float(profile.get('bmr')) if profile.get('bmr') else 0,
                'TDEE': float(profile.get('tdee')) if profile.get('tdee') else 0,
                'CaloDuKien': float(profile.get('calodukien')) if profile.get('calodukien') else 0
            }
        return None
    except Exception as e:
        print(f"Error getting health profile: {e}")
        import traceback
        traceback.print_exc()
        return None

def upsert_health_profile(user_id, data):
    """Thêm hoặc cập nhật hồ sơ sức khỏe. Trả về dict thông tin thay đổi cân nặng."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Calculate BMR, TDEE, CaloDuKien
        can_nang = float(data.get('CanNang', 0))
        chieu_cao = float(data.get('ChieuCao', 0))
        tuoi = int(data.get('Tuoi', 0))
        gioi_tinh = data.get('GioiTinh', 'Nam')
        muc_do_van_dong = data.get('MucDoVanDong', 'Vừa')
        muc_tieu = data.get('MucTieu', 'Duy trì')

        # Calculate BMR (Mifflin-St Jeor)
        if gioi_tinh == 'Nam':
            bmr = 10 * can_nang + 6.25 * chieu_cao - 5 * tuoi + 5
        else:
            bmr = 10 * can_nang + 6.25 * chieu_cao - 5 * tuoi - 161

        # Calculate TDEE
        activity_factors = {
            'Ít': 1.2,
            'Vừa': 1.55,
            'Nhiều': 1.725
        }
        tdee = bmr * activity_factors.get(muc_do_van_dong, 1.55)

        # Adjust for goal
        goal_adjustments = {
            'Giảm cân': -400,
            'Tăng cân': 400,
            'Duy trì': 0
        }
        calo_du_kien = tdee + goal_adjustments.get(muc_tieu, 0)

        # Fetch old weight/height before update to compute diff
        old_weight = None
        old_height = None
        cursor.execute("""
            SELECT CanNang, ChieuCao FROM HoSoSucKhoe WHERE MaNguoiDung = %s
        """, (user_id,))
        old_row = cursor.fetchone()
        if old_row and old_row[0] is not None:
            old_weight = float(old_row[0])
            old_height = float(old_row[1]) if old_row[1] is not None else None

        # Check if profile exists
        cursor.execute("""
            SELECT MaHoSo FROM HoSoSucKhoe WHERE MaNguoiDung = %s
        """, (user_id,))
        existing = cursor.fetchone()

        if existing:
            # Update
            cursor.execute("""
                UPDATE HoSoSucKhoe
                SET CanNang = %s, ChieuCao = %s, Tuoi = %s, GioiTinh = %s,
                    MucDoVanDong = %s, MucTieu = %s, BMR = %s, TDEE = %s, CaloDuKien = %s,
                    NgayCapNhat = CURRENT_TIMESTAMP
                WHERE MaNguoiDung = %s
            """, (can_nang, chieu_cao, tuoi, gioi_tinh, muc_do_van_dong,
                  muc_tieu, bmr, tdee, calo_du_kien, user_id))
        else:
            # Insert
            cursor.execute("""
                INSERT INTO HoSoSucKhoe
                (MaNguoiDung, CanNang, ChieuCao, Tuoi, GioiTinh, MucDoVanDong, MucTieu, BMR, TDEE, CaloDuKien)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, can_nang, chieu_cao, tuoi, gioi_tinh, muc_do_van_dong,
                  muc_tieu, bmr, tdee, calo_du_kien))

        # Compute BMI for the new entry and log history
        bmi_new = None
        category_new = None
        if chieu_cao > 0:
            bmi_new = round(can_nang / ((chieu_cao / 100) ** 2), 2)
            category_new, _color, _rec, _suggested = classify_bmi(bmi_new)

        cursor.execute("""
            INSERT INTO LichSuCanNang (MaNguoiDung, CanNang, ChieuCao, BMI, PhanLoaiBMI)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, can_nang, chieu_cao, bmi_new, category_new))

        conn.commit()
        conn.close()

        # Compute diff & BMI old
        diff = (can_nang - old_weight) if old_weight is not None else 0.0
        bmi_old = None
        category_old = None
        if old_weight and old_height and old_height > 0:
            bmi_old = round(old_weight / ((old_height / 100) ** 2), 2)
            category_old, _c, _r, _s = classify_bmi(bmi_old)

        # Create notification if weight change is notable
        if old_weight is not None and abs(diff) >= 0.5:
            msg_type, title, desc = build_weight_message(muc_tieu, diff)
            try:
                create_notification(
                    user_id,
                    None,
                    f"{title} — {desc}",
                    old_name=f"{old_weight:.1f}kg",
                    new_name=f"{can_nang:.1f}kg"
                )
            except Exception as ne:
                print(f"Warning: could not create weight notification: {ne}")

        return {
            "success": True,
            "old_weight": old_weight,
            "new_weight": can_nang,
            "old_height": old_height,
            "diff": round(diff, 2),
            "bmi_old": bmi_old,
            "bmi_new": bmi_new,
            "category_old": category_old,
            "category_new": category_new,
            "muc_tieu": muc_tieu,
            "is_first_entry": old_weight is None
        }
    except Exception as e:
        print(f"Error upserting health profile: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def get_weight_history(user_id, limit=30):
    """Lấy lịch sử cân nặng gần nhất, sắp xếp theo thời gian tăng dần (để vẽ chart)."""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        cursor.execute("""
            SELECT MaLichSuCN, CanNang, ChieuCao, BMI, PhanLoaiBMI, ThoiGian
            FROM LichSuCanNang
            WHERE MaNguoiDung = %s
            ORDER BY ThoiGian DESC
            LIMIT %s
        """, (user_id, limit))
        rows = cursor.fetchall()
        conn.close()

        history = []
        for r in rows:
            history.append({
                'id': r.get('malichsucn'),
                'can_nang': float(r.get('cannang')) if r.get('cannang') is not None else None,
                'chieu_cao': float(r.get('chieucao')) if r.get('chieucao') is not None else None,
                'bmi': float(r.get('bmi')) if r.get('bmi') is not None else None,
                'phan_loai': r.get('phanloaibmi'),
                'thoi_gian': r.get('thoigian').strftime('%Y-%m-%d %H:%M:%S') if r.get('thoigian') else None
            })
        # Reverse to ASC for chart
        history.reverse()
        return history
    except Exception as e:
        print(f"Error fetching weight history: {e}")
        import traceback
        traceback.print_exc()
        return []

# ============================================
# COMMENT / FEEDBACK SYSTEM & ADMIN EDIT & NOTIFICATIONS
# ============================================

def insert_comment(history_id, user_id, content):
    """Thêm bình luận phản hồi từ user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            INSERT INTO BinhLuan (MaLichSu, MaNguoiDung, NoiDung)
            VALUES (%s, %s, %s)
            RETURNING MaBinhLuan
        """, (history_id, user_id, content))
        
        result = cursor.fetchone()
        conn.commit()
        conn.close()
        return result['mabinhluan'] if result else None
    except Exception as e:
        print(f"Error inserting comment: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_comments_by_history(history_id):
    """Lấy danh sách bình luận theo history_id (kèm replies)"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT b.MaBinhLuan, b.NoiDung, b.ThoiGian, b.MaBinhLuanCha, b.MaNguoiDung,
                   n.TenNguoiDung, n.VaiTro
            FROM BinhLuan b
            LEFT JOIN NguoiDung n ON b.MaNguoiDung = n.MaNguoiDung
            WHERE b.MaLichSu = %s
            ORDER BY b.ThoiGian ASC
        """, (history_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        comments = []
        for r in rows:
            comments.append({
                'id': r['mabinhluan'],
                'content': r['noidung'],
                'time': r['thoigian'].strftime('%d/%m/%Y %H:%M') if r['thoigian'] else '',
                'time_raw': r['thoigian'].isoformat() if r['thoigian'] else '',
                'parent_id': r['mabinhluancha'],
                'user_id': r['manguoidung'],
                'user_name': r['tennguoidung'] or 'Ẩn danh',
                'is_admin': r.get('vaitro') == 'admin'
            })
        return comments
    except Exception as e:
        print(f"Error getting comments: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_all_comments_admin(filter_status='all'):
    """Lấy tất cả bình luận gốc cho admin (có filter)"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT b.MaBinhLuan, b.NoiDung, b.ThoiGian, b.MaLichSu, b.MaNguoiDung,
                   n.TenNguoiDung, n.Email, l.TenMonAn, l.DuongDanAnh,
                   (SELECT COUNT(*) FROM BinhLuan r WHERE r.MaBinhLuanCha = b.MaBinhLuan) as reply_count
            FROM BinhLuan b
            LEFT JOIN NguoiDung n ON b.MaNguoiDung = n.MaNguoiDung
            LEFT JOIN LichSu l ON b.MaLichSu = l.MaLichSu
            WHERE b.MaBinhLuanCha IS NULL
            ORDER BY b.ThoiGian DESC
            LIMIT 200
        """)
        
        rows = cursor.fetchall()
        
        comments = []
        for r in rows:
            reply_count = r['reply_count'] or 0
            status = 'replied' if reply_count > 0 else 'pending'
            
            if filter_status != 'all' and status != filter_status:
                continue
            
            # Lấy replies cho comment này
            replies = []
            if reply_count > 0:
                cursor.execute("""
                    SELECT b.MaBinhLuan, b.NoiDung, b.ThoiGian,
                           n.TenNguoiDung, n.VaiTro
                    FROM BinhLuan b
                    LEFT JOIN NguoiDung n ON b.MaNguoiDung = n.MaNguoiDung
                    WHERE b.MaBinhLuanCha = %s
                    ORDER BY b.ThoiGian ASC
                """, (r['mabinhluan'],))
                for rep in cursor.fetchall():
                    replies.append({
                        'id': rep['mabinhluan'],
                        'content': rep['noidung'],
                        'time': rep['thoigian'].strftime('%d/%m/%Y %H:%M') if rep['thoigian'] else '',
                        'user_name': rep['tennguoidung'] or 'Admin',
                        'is_admin': rep.get('vaitro') == 'admin'
                    })
            
            comments.append({
                'id': r['mabinhluan'],
                'content': r['noidung'],
                'time': r['thoigian'].strftime('%Y-%m-%d %H:%M:%S') if r['thoigian'] else '',
                'history_id': r['malichsu'],
                'user_id': r['manguoidung'],
                'user_name': r['tennguoidung'] or 'Ẩn danh',
                'user_email': r.get('email', ''),
                'food_name': r['tenmonan'] or 'Không rõ',
                'food_image': r.get('duongdananh', '') or '',
                'reply_count': reply_count,
                'status': status,
                'replies': replies
            })
        
        conn.close()
        return comments
    except Exception as e:
        print(f"Error getting all comments admin: {e}")
        import traceback
        traceback.print_exc()
        return []

def admin_reply_comment(comment_id, admin_id, content, history_id):
    """Admin phản hồi bình luận"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            INSERT INTO BinhLuan (MaLichSu, MaNguoiDung, NoiDung, MaBinhLuanCha)
            VALUES (%s, %s, %s, %s)
            RETURNING MaBinhLuan
        """, (history_id, admin_id, content, comment_id))
        
        result = cursor.fetchone()
        conn.commit()
        conn.close()
        return result['mabinhluan'] if result else None
    except Exception as e:
        print(f"Error admin reply comment: {e}")
        import traceback
        traceback.print_exc()
        return None

def delete_comment(comment_id):
    """Xóa bình luận (và replies)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Xóa replies trước
        cursor.execute("DELETE FROM BinhLuan WHERE MaBinhLuanCha = %s", (comment_id,))
        # Xóa comment gốc
        cursor.execute("DELETE FROM BinhLuan WHERE MaBinhLuan = %s", (comment_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting comment: {e}")
        return False

def get_comment_detail(comment_id):
    """Lấy chi tiết 1 comment (để tìm user_id, history_id)"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT b.MaBinhLuan, b.MaLichSu, b.MaNguoiDung, b.NoiDung,
                   n.TenNguoiDung, l.TenMonAn
            FROM BinhLuan b
            LEFT JOIN NguoiDung n ON b.MaNguoiDung = n.MaNguoiDung
            LEFT JOIN LichSu l ON b.MaLichSu = l.MaLichSu
            WHERE b.MaBinhLuan = %s
        """, (comment_id,))
        
        r = cursor.fetchone()
        conn.close()
        
        if r:
            return {
                'id': r['mabinhluan'],
                'history_id': r['malichsu'],
                'user_id': r['manguoidung'],
                'content': r['noidung'],
                'user_name': r['tennguoidung'] or 'Ẩn danh',
                'food_name': r['tenmonan'] or 'Không rõ'
            }
        return None
    except Exception as e:
        print(f"Error getting comment detail: {e}")
        return None

def update_history_record(history_id, new_food_name, new_calories=None):
    """Admin cập nhật tên món và calo trong bản ghi lịch sử"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # Lấy thông tin cũ trước
        cursor.execute("""
            SELECT MaNguoiDung, TenMonAn, Calo FROM LichSu WHERE MaLichSu = %s
        """, (history_id,))
        old = cursor.fetchone()
        if not old:
            conn.close()
            return None
        
        old_name = old['tenmonan']
        user_id = old['manguoidung']
        
        # Cập nhật
        if new_calories is not None:
            cursor.execute("""
                UPDATE LichSu SET TenMonAn = %s, Calo = %s WHERE MaLichSu = %s
            """, (new_food_name, new_calories, history_id))
        else:
            cursor.execute("""
                UPDATE LichSu SET TenMonAn = %s WHERE MaLichSu = %s
            """, (new_food_name, history_id))
        
        conn.commit()
        conn.close()
        
        return {
            'user_id': user_id,
            'old_name': old_name,
            'new_name': new_food_name
        }
    except Exception as e:
        print(f"Error updating history record: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_admin_user_ids():
    """Lấy danh sách MaNguoiDung của tất cả admin"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        cursor.execute("SELECT MaNguoiDung FROM NguoiDung WHERE VaiTro = 'admin'")
        ids = [r['manguoidung'] for r in cursor.fetchall()]
        conn.close()
        return ids
    except Exception as e:
        print(f"Error get_admin_user_ids: {e}")
        return []

def notify_admins(content, history_id=None, old_name='', new_name=''):
    """Gửi thông báo tới tất cả admin"""
    admin_ids = get_admin_user_ids()
    for admin_id in admin_ids:
        create_notification(admin_id, history_id, content, old_name, new_name)

def create_notification(user_id, history_id, content, old_name='', new_name=''):
    """Tạo thông báo cho user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ThongBao (MaNguoiDung, MaLichSu, NoiDung, TenCu, TenMoi)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, history_id, content, old_name, new_name))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating notification: {e}")
        return False

def get_user_notifications(user_id):
    """Lấy danh sách thông báo của user"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT MaThongBao, MaLichSu, NoiDung, TenCu, TenMoi, DaDoc, ThoiGian
            FROM ThongBao
            WHERE MaNguoiDung = %s
            ORDER BY ThoiGian DESC
            LIMIT 50
        """, (user_id,))
        
        notifs = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': n['mathongbao'],
                'history_id': n.get('malichsu'),
                'content': n['noidung'],
                'old_name': n.get('tencu', ''),
                'new_name': n.get('tenmoi', ''),
                'is_read': n['dadoc'],
                'time': n['thoigian'].strftime('%Y-%m-%d %H:%M:%S') if n['thoigian'] else ''
            }
            for n in notifs
        ]
    except Exception as e:
        print(f"Error getting notifications: {e}")
        import traceback
        traceback.print_exc()
        return []

def mark_notification_read(notification_id):
    """Đánh dấu thông báo đã đọc"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ThongBao SET DaDoc = TRUE WHERE MaThongBao = %s
        """, (notification_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking notification read: {e}")
        return False

def mark_all_notifications_read(user_id):
    """Đánh dấu tất cả thông báo đã đọc"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ThongBao SET DaDoc = TRUE WHERE MaNguoiDung = %s AND DaDoc = FALSE
        """, (user_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking all notifications read: {e}")
        return False

def delete_history_record(history_id):
    """Xóa bản ghi lịch sử"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Xóa thông báo liên quan trước
        cursor.execute("DELETE FROM ThongBao WHERE MaLichSu = %s", (history_id,))
        # Xóa bản ghi lịch sử
        cursor.execute("DELETE FROM LichSu WHERE MaLichSu = %s", (history_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting history: {e}")
        return False

def bulk_delete_history(history_ids):
    """Xóa nhiều bản ghi lịch sử cùng lúc"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        ids_tuple = tuple(history_ids)
        placeholders = ','.join(['%s'] * len(ids_tuple))
        
        cursor.execute(f"DELETE FROM ThongBao WHERE MaLichSu IN ({placeholders})", ids_tuple)
        cursor.execute(f"DELETE FROM LichSu WHERE MaLichSu IN ({placeholders})", ids_tuple)
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted
    except Exception as e:
        print(f"Error bulk deleting history: {e}")
        return 0


# ============================================
# PREMIUM ACCOUNT & PAYMENT FUNCTIONS
# ============================================

def get_user_recognition_count_today(user_id):
    """Đếm số lần nhận diện hôm nay của user"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM LichSu
            WHERE MaNguoiDung = %s AND DATE(ThoiGian) = CURRENT_DATE
        """, (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        return result['count'] if result else 0
    except Exception as e:
        print(f"Error get_user_recognition_count_today: {e}")
        return 0


@retry_db_operation(max_retries=2)
def check_user_quota(user_id):
    """Kiểm tra quota nhận diện của user"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # Lấy loại tài khoản
        cursor.execute("""
            SELECT LoaiTaiKhoan, NgayHetHanPremium FROM NguoiDung WHERE MaNguoiDung = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        if not user:
            conn.close()
            return {
                'allowed': False,
                'account_type': 'free',
                'is_premium': False,
                'used_today': 0,
                'remaining': 0,
                'limit_per_day': 10,
                'message': 'Không tìm thấy người dùng'
            }
        
        account_type = user.get('loaitaikhoan', 'free') or 'free'
        ngay_het_han = user.get('ngayhethanpremium')
        
        # Check expiration
        if account_type == 'premium' and ngay_het_han:
            from datetime import datetime
            now = datetime.now()
            if ngay_het_han <= now:
                # Expired! Downgrade
                cursor.execute("UPDATE NguoiDung SET LoaiTaiKhoan = 'free' WHERE MaNguoiDung = %s", (user_id,))
                conn.commit()
                account_type = 'free'
                
        is_premium = account_type == 'premium'
        
        if is_premium:
            conn.close()
            return {
                'allowed': True,
                'account_type': 'premium',
                'is_premium': True,
                'used_today': 0,
                'remaining': -1,  # unlimited
                'limit_per_day': -1,
                'message': 'Tài khoản Premium - Không giới hạn'
            }
        
        # Free user - đếm số lần nhận diện hôm nay
        cursor.execute("""
            SELECT COUNT(*) as count FROM LichSu
            WHERE MaNguoiDung = %s AND DATE(ThoiGian) = CURRENT_DATE
        """, (user_id,))
        
        result = cursor.fetchone()
        used_today = result['count'] if result else 0
        limit_per_day = 10
        remaining = max(0, limit_per_day - used_today)
        allowed = used_today < limit_per_day
        
        conn.close()
        return {
            'allowed': allowed,
            'account_type': 'free',
            'is_premium': False,
            'used_today': used_today,
            'remaining': remaining,
            'limit_per_day': limit_per_day,
            'message': f'Còn {remaining}/{limit_per_day} lượt hôm nay' if allowed else 'Đã hết lượt nhận diện hôm nay'
        }
    except Exception as e:
        print(f"Error check_user_quota: {e}")
        return {
            'allowed': True,
            'account_type': 'free',
            'is_premium': False,
            'used_today': 0,
            'remaining': 10,
            'limit_per_day': 10,
            'message': 'Lỗi kiểm tra quota'
        }


def upgrade_user_account(user_id):
    """Nâng cấp tài khoản lên Premium"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE NguoiDung 
            SET LoaiTaiKhoan = 'premium', 
                NgayNangCap = CURRENT_TIMESTAMP,
                NgayHetHanPremium = CURRENT_TIMESTAMP + INTERVAL '30 days'
            WHERE MaNguoiDung = %s
        """, (user_id,))
        
        conn.commit()
        conn.close()
        print(f"[PREMIUM] User {user_id} upgraded to Premium!")
        return True
    except Exception as e:
        print(f"Error upgrade_user_account: {e}")
        return False


def create_payment(user_id, order_id, amount, package='premium'):
    """Tạo bản ghi thanh toán mới"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ThanhToan (MaNguoiDung, MaDonHang, SoTien, GoiNangCap, PhuongThuc)
            VALUES (%s, %s, %s, %s, 'payos')
            RETURNING MaThanhToan
        """, (user_id, order_id, amount, package))
        
        result = cursor.fetchone()
        conn.commit()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error create_payment: {e}")
        return None


def update_payment_status(order_id, status, momo_trans_id=None, response_data=None):
    """Cập nhật trạng thái thanh toán"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ThanhToan 
            SET TrangThai = %s, MomoTransId = %s, ResponseData = %s, 
                ThoiGianCapNhat = CURRENT_TIMESTAMP
            WHERE MaDonHang = %s
        """, (status, momo_trans_id, response_data, order_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error update_payment_status: {e}")
        return False


def get_payment_by_order_id(order_id):
    """Lấy thông tin thanh toán theo mã đơn hàng"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("""
            SELECT * FROM ThanhToan WHERE MaDonHang = %s
        """, (order_id,))
        
        payment = cursor.fetchone()
        conn.close()
        return payment
    except Exception as e:
        print(f"Error get_payment_by_order_id: {e}")
        return None


def get_all_payments_admin():
    """Admin: Lấy danh sách tất cả thanh toán"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # Auto-expire pending payments older than 15 minutes
        cursor.execute("""
            UPDATE ThanhToan
            SET TrangThai = 'failed', ThoiGianCapNhat = CURRENT_TIMESTAMP
            WHERE TrangThai = 'pending' 
              AND ThoiGianTao < CURRENT_TIMESTAMP - INTERVAL '15 minutes'
            RETURNING MaThanhToan, MaDonHang, MaNguoiDung
        """)
        expired_payments = cursor.fetchall()
        
        if expired_payments:
            cursor.execute("SELECT MaNguoiDung FROM NguoiDung WHERE VaiTro = 'admin'")
            admins = cursor.fetchall()
            for p in expired_payments:
                # Thông báo cho admin
                for a in admins:
                    cursor.execute("""
                        INSERT INTO ThongBao (MaNguoiDung, NoiDung)
                        VALUES (%s, %s)
                    """, (a['manguoidung'], f"Giao dịch thanh toán {p['madonhang']} quá hạn 15 phút và đã tự động bị hủy."))
                
                # Thông báo cho người dùng
                if p['manguoidung']:
                    cursor.execute("""
                        INSERT INTO ThongBao (MaNguoiDung, NoiDung)
                        VALUES (%s, %s)
                    """, (p['manguoidung'], f"Đơn hàng {p['madonhang']} của bạn đã bị hủy do quá hạn thanh toán 15 phút."))
            conn.commit()
        
        cursor.execute("""
            SELECT t.MaThanhToan, t.MaDonHang, t.SoTien, t.GoiNangCap,
                   t.TrangThai, t.PhuongThuc, t.MomoTransId,
                   t.ThoiGianTao, t.ThoiGianCapNhat,
                   n.TenNguoiDung, n.Email
            FROM ThanhToan t
            LEFT JOIN NguoiDung n ON t.MaNguoiDung = n.MaNguoiDung
            ORDER BY t.ThoiGianTao DESC
            LIMIT 200
        """)
        
        payments = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': p['mathanhtoan'],
                'order_id': p['madonhang'],
                'amount': float(p['sotien']) if p['sotien'] else 0,
                'package': p['goinangcap'],
                'status': p['trangthai'],
                'method': p['phuongthuc'],
                'momo_trans_id': p.get('momotransid', ''),
                'user_name': p.get('tennguoidung', 'Không rõ'),
                'user_email': p.get('email', ''),
                'created_at': p['thoigiantao'].strftime('%d/%m/%Y %H:%M') if p.get('thoigiantao') else '',
                'updated_at': p['thoigiancapnhat'].strftime('%d/%m/%Y %H:%M') if p.get('thoigiancapnhat') else ''
            }
            for p in payments
        ]
    except Exception as e:
        print(f"Error get_all_payments_admin: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_payment_stats_admin():
    """Admin: Thống kê doanh thu"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # Tổng doanh thu (chỉ tính success)
        cursor.execute("""
            SELECT COALESCE(SUM(SoTien), 0) as total_revenue,
                   COUNT(*) FILTER (WHERE TrangThai = 'success') as success_count,
                   COUNT(*) FILTER (WHERE TrangThai = 'pending') as pending_count,
                   COUNT(*) FILTER (WHERE TrangThai = 'failed') as failed_count,
                   COUNT(*) as total_payments
            FROM ThanhToan
        """)
        stats = cursor.fetchone()
        
        # Số user Premium
        cursor.execute("""
            SELECT COUNT(*) as count FROM NguoiDung WHERE LoaiTaiKhoan = 'premium'
        """)
        premium_row = cursor.fetchone()
        premium_users = premium_row['count'] if premium_row else 0
        
        # Doanh thu chỉ tính thành công
        cursor.execute("""
            SELECT COALESCE(SUM(SoTien), 0) as revenue FROM ThanhToan WHERE TrangThai = 'success'
        """)
        rev_row = cursor.fetchone()
        actual_revenue = float(rev_row['revenue']) if rev_row else 0
        
        # 5 giao dịch gần nhất
        cursor.execute("""
            SELECT t.MaDonHang, t.SoTien, t.TrangThai, t.ThoiGianTao,
                   n.TenNguoiDung
            FROM ThanhToan t
            LEFT JOIN NguoiDung n ON t.MaNguoiDung = n.MaNguoiDung
            ORDER BY t.ThoiGianTao DESC
            LIMIT 5
        """)
        recent = []
        for r in cursor.fetchall():
            recent.append({
                'order_id': r['madonhang'],
                'amount': float(r['sotien']) if r['sotien'] else 0,
                'status': r['trangthai'],
                'user_name': r.get('tennguoidung', 'Không rõ'),
                'created_at': r['thoigiantao'].strftime('%d/%m/%Y %H:%M') if r.get('thoigiantao') else ''
            })
        
        conn.close()
        
        return {
            'total_revenue': actual_revenue,
            'total_payments': stats['total_payments'] if stats else 0,
            'success_count': stats['success_count'] if stats else 0,
            'pending_count': stats['pending_count'] if stats else 0,
            'failed_count': stats['failed_count'] if stats else 0,
            'premium_users': premium_users,
            'recent_payments': recent
        }
    except Exception as e:
        print(f"Error get_payment_stats_admin: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total_revenue': 0, 'total_payments': 0,
            'success_count': 0, 'pending_count': 0, 'failed_count': 0,
            'premium_users': 0, 'recent_payments': []
        }

def update_user_account_type(user_id, account_type):
    """Chuyển đổi loại tài khoản (free/premium)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if account_type == 'premium':
            cursor.execute("""
                UPDATE NguoiDung 
                SET LoaiTaiKhoan = 'premium', NgayNangCap = CURRENT_TIMESTAMP
                WHERE MaNguoiDung = %s
            """, (user_id,))
        else:
            cursor.execute("""
                UPDATE NguoiDung 
                SET LoaiTaiKhoan = 'free', NgayNangCap = NULL
                WHERE MaNguoiDung = %s
            """, (user_id,))
            
        conn.commit()
        conn.close()
        print(f"[ACCOUNT] User {user_id} account type changed to {account_type}")
        return True
    except Exception as e:
        print(f"Error update_user_account_type: {e}")
        return False

