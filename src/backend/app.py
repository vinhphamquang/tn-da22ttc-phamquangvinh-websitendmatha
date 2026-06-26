import sys
import os
import base64
import io

# Fix stdout encoding for Windows
if sys.stdout and hasattr(sys.stdout, 'encoding') and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.dirname(__file__))

from flask import Flask, request, jsonify, send_from_directory, send_file, make_response, redirect
from flask_cors import CORS
from external_api import analyze_image
from db_queries import (
    search_food_by_name, insert_lich_su, get_db_connection, get_db_cursor, close_db_connection,
    create_user, get_user_by_email, get_user_history, get_user_by_id, update_password,
    get_all_users, delete_user, get_system_stats, get_all_history_admin, get_history_detail_admin,
    get_all_foods_admin, get_food_detail_admin, insert_food_full, update_food_full, 
    delete_food_soft, restore_food_soft, delete_food_hard, get_health_profile, upsert_health_profile,
    get_weight_history, classify_bmi,
    get_user_food_stats, update_history_record,
    create_notification, get_user_notifications, mark_notification_read, mark_all_notifications_read,
    delete_history_record, bulk_delete_history,
    create_google_user, get_user_by_google_id, update_user_google_id,
    get_user_detail_admin, update_last_active, notify_admins,
    insert_comment, get_comments_by_history, get_all_comments_admin,
    admin_reply_comment, delete_comment, get_comment_detail,
    check_user_quota, upgrade_user_account, update_user_account_type,
    create_payment, update_payment_status, get_payment_by_order_id,
    get_all_payments_admin, get_payment_stats_admin
)
from ai_generator import generate_food_data_vietnamese
from food_translator import translate_food_name, get_search_variants
from payos_payment import create_payos_payment, verify_payos_webhook, generate_order_id, PREMIUM_PRICE
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Google OAuth
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

load_dotenv()
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')

app = Flask(__name__, static_folder="../frontend")
CORS(app)

# ============================================
# DATABASE MIGRATION
# ============================================
def run_migrations():
    """Chạy migration để thêm cột mới vào DB nếu chưa có"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Thêm cột Calo vào LichSu
        cursor.execute("""
            ALTER TABLE LichSu ADD COLUMN IF NOT EXISTS Calo REAL DEFAULT 0
        """)
        
        # 2. Thêm cột DanhGiaNguoiDung vào LichSu (đánh giá từ user)
        cursor.execute("""
            ALTER TABLE LichSu ADD COLUMN IF NOT EXISTS DanhGiaNguoiDung TEXT DEFAULT NULL
        """)
        
        # 3. Tạo bảng ThongBao (thông báo cho user)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ThongBao (
                MaThongBao SERIAL PRIMARY KEY,
                MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
                MaLichSu INTEGER,
                NoiDung TEXT NOT NULL,
                TenCu TEXT,
                TenMoi TEXT,
                DaDoc BOOLEAN DEFAULT FALSE,
                ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. Thêm cột GoogleId vào NguoiDung
        cursor.execute("""
            ALTER TABLE NguoiDung ADD COLUMN IF NOT EXISTS GoogleId TEXT DEFAULT NULL
        """)
        
        # 5. Thêm cột LastActive vào NguoiDung (trạng thái online)
        cursor.execute("""
            ALTER TABLE NguoiDung ADD COLUMN IF NOT EXISTS LastActive TIMESTAMP DEFAULT NULL
        """)
        
        # 6. Tạo bảng BinhLuan (bình luận phản hồi)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BinhLuan (
                MaBinhLuan SERIAL PRIMARY KEY,
                MaLichSu INTEGER REFERENCES LichSu(MaLichSu) ON DELETE CASCADE,
                MaNguoiDung INTEGER REFERENCES NguoiDung(MaNguoiDung) ON DELETE CASCADE,
                NoiDung TEXT NOT NULL,
                MaBinhLuanCha INTEGER DEFAULT NULL,
                ThoiGian TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 7. Thêm cột KhuyenNghiKeHoach vào LichSu (lưu JSON khuyến nghị kế hoạch dinh dưỡng)
        cursor.execute("""
            ALTER TABLE LichSu ADD COLUMN IF NOT EXISTS KhuyenNghiKeHoach TEXT DEFAULT NULL
        """)
        
        # 8. Thêm cột LoaiTaiKhoan và NgayNangCap vào NguoiDung (Premium upgrade)
        cursor.execute("""
            ALTER TABLE NguoiDung ADD COLUMN IF NOT EXISTS LoaiTaiKhoan VARCHAR(20) DEFAULT 'free'
        """)
        cursor.execute("""
            ALTER TABLE NguoiDung ADD COLUMN IF NOT EXISTS NgayNangCap TIMESTAMP DEFAULT NULL
        """)
        cursor.execute("""
            ALTER TABLE NguoiDung ADD COLUMN IF NOT EXISTS NgayHetHanPremium TIMESTAMP DEFAULT NULL
        """)

        
        # 9. Tạo bảng ThanhToan (Payment Transactions)
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
        
        conn.commit()
        close_db_connection(conn)
        print("[MIGRATION] Đã chạy migrations thành công (Calo, DanhGiaNguoiDung, ThongBao, GoogleId, LastActive, BinhLuan, KhuyenNghiKeHoach, LoaiTaiKhoan, ThanhToan)")
    except Exception as e:
        print(f"[MIGRATION WARNING] {e}")

run_migrations()

@app.route("/api/google-client-id")
def get_google_client_id():
    """Trả về Google Client ID cho frontend"""
    return jsonify({"client_id": GOOGLE_CLIENT_ID})

def serve_html_no_cache(filename):
    """Serve an HTML page without caching so updates ship immediately
    (the inline page-veil script must be the latest version)."""
    resp = make_response(send_file(os.path.join(app.static_folder, filename)))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.route("/")
def index():
    return serve_html_no_cache("index.html")

@app.route("/admin")
def admin_page():
    return serve_html_no_cache("admin.html")

@app.route("/nutrition")
def nutrition_page():
    return serve_html_no_cache("nutrition.html")

@app.route("/thanh-toan")
def thanh_toan_page():
    return serve_html_no_cache("thanh-toan.html")

@app.route("/dat-hang-thanh-cong")
def dat_hang_thanh_cong_page():
    return serve_html_no_cache("dat-hang-thanh-cong.html")

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# SPA catch-all: mọi route không match sẽ trả về index.html
@app.route("/<path:path>")
def catch_all(path):
    # Nếu là file tĩnh thực sự thì serve nó
    file_path = os.path.join(app.static_folder, path)
    if os.path.isfile(file_path):
        return send_from_directory(app.static_folder, path)
    # Ngược lại trả về index.html cho SPA routing
    return serve_html_no_cache("index.html")

@app.route("/api/dishes")
def get_dishes():
    """API trả về danh sách các món ăn được hỗ trợ (cho trang Giới Thiệu)"""
    try:
        conn = get_db_connection()
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT m.MaMonAn, m.TenMonAn, m.MoTa, m.PhanLoai,
                   d.Calo, d.Protein, d.ChatBeo, d.Carbohydrate
            FROM MonAn m
            LEFT JOIN DinhDuong d ON m.MaMonAn = d.MaMonAn
            WHERE m.IsDeleted = 0
            ORDER BY m.MaMonAn
        """)
        
        rows = cursor.fetchall()
        dishes = []
        for row in rows:
            dishes.append({
                "id": row.get("mamonan"),
                "name": row.get("tenmonan", ""),
                "description": row.get("mota", ""),
                "category": row.get("phanloai", ""),
                "calories": float(row.get("calo", 0)) if row.get("calo") else 0,
                "protein": float(row.get("protein", 0)) if row.get("protein") else 0,
                "fats": float(row.get("chatbeo", 0)) if row.get("chatbeo") else 0,
                "carbs": float(row.get("carbohydrate", 0)) if row.get("carbohydrate") else 0,
            })
        
        close_db_connection(conn)
        return jsonify({"dishes": dishes, "total": len(dishes)})
    except Exception as e:
        print(f"[ERROR] get_dishes: {e}")
        return jsonify({"dishes": [], "total": 0, "error": str(e)})

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    if not data or not data.get("name") or not data.get("email") or not data.get("password"):
        return jsonify({"success": False, "message": "Vui lòng điền đầy đủ thông tin"}), 400
    
    hashed_password = generate_password_hash(data["password"])
    success, message, user_id = create_user(data["name"], data["email"], hashed_password)
    
    if success and user_id:
        # Nếu có thông tin sức khỏe thì lưu luôn
        tuoi = data.get("hp_age")
        chieu_cao = data.get("hp_height")
        can_nang = data.get("hp_weight")
        if tuoi and chieu_cao and can_nang:
            hp_data = {
                "Tuoi": tuoi,
                "ChieuCao": chieu_cao,
                "CanNang": can_nang,
                "GioiTinh": data.get("hp_gender", "Nam"),
                "MucTieu": data.get("hp_goal", "giu_dang")
            }
            upsert_health_profile(user_id, hp_data)
            
        # Thông báo cho admin khi có người đăng ký mới
        try:
            notify_admins(
                f"👤 Người dùng mới đăng ký: {data['name']} ({data['email']})"
            )
        except Exception as e:
            print(f"[NOTIFY] Error notifying admins about new user: {e}")
        
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 400

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"success": False, "message": "Vui lòng nhập Email và Mật khẩu"}), 400
        
    user = get_user_by_email(data["email"])
    if not user or not check_password_hash(user["MatKhau"], data["password"]):
        return jsonify({"success": False, "message": "Email hoặc mật khẩu không đúng"}), 401
    
    # Cập nhật trạng thái hoạt động
    update_last_active(user["MaNguoiDung"])
    
    return jsonify({
        "success": True,
        "message": "Đăng nhập thành công",
        "user": {
            "id": user["MaNguoiDung"],
            "name": user["TenNguoiDung"],
            "email": user["Email"],
            "role": user["VaiTro"],
            "account_type": user.get("LoaiTaiKhoan", "free")
        }
    })

@app.route("/api/google-login", methods=["POST"])
def google_login():
    """Đăng nhập / Đăng ký bằng tài khoản Google"""
    data = request.json
    token = data.get("id_token")
    
    if not token:
        return jsonify({"success": False, "message": "Thiếu token Google"}), 400
    
    try:
        # Verify Google ID token
        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        
        # Lấy thông tin user từ token
        google_id = idinfo['sub']
        email = idinfo.get('email', '')
        name = idinfo.get('name', email.split('@')[0])
        picture = idinfo.get('picture', '')
        
        if not email:
            return jsonify({"success": False, "message": "Không lấy được email từ Google"}), 400
        
        # Tìm user theo GoogleId
        user = get_user_by_google_id(google_id)
        
        if user:
            # User đã đăng ký bằng Google trước đó → đăng nhập
            return jsonify({
                "success": True,
                "message": "Đăng nhập Google thành công",
                "user": {
                    "id": user["MaNguoiDung"],
                    "name": user["TenNguoiDung"],
                    "email": user["Email"],
                    "role": user["VaiTro"],
                    "account_type": user.get("LoaiTaiKhoan", "free"),
                    "auth_provider": "google",
                    "picture": picture
                }
            })
        
        # Tìm user theo email (đã đăng ký truyền thống)
        existing_user = get_user_by_email(email)
        
        if existing_user:
            # Liên kết tài khoản Google với user đã có
            update_user_google_id(existing_user["MaNguoiDung"], google_id)
            return jsonify({
                "success": True,
                "message": "Đã liên kết tài khoản Google thành công",
                "user": {
                    "id": existing_user["MaNguoiDung"],
                    "name": existing_user["TenNguoiDung"],
                    "email": existing_user["Email"],
                    "role": existing_user["VaiTro"],
                    "account_type": existing_user.get("LoaiTaiKhoan", "free"),
                    "auth_provider": "google",
                    "picture": picture
                }
            })
        
        # Tạo user mới bằng Google
        success, message, user_id = create_google_user(name, email, google_id)
        
        if success and user_id:
            return jsonify({
                "success": True,
                "message": "Đăng ký tài khoản Google thành công",
                "user": {
                    "id": user_id,
                    "name": name,
                    "email": email,
                    "role": "user",
                    "auth_provider": "google",
                    "picture": picture
                }
            })
        else:
            return jsonify({"success": False, "message": message}), 400
            
    except ValueError as e:
        print(f"[GOOGLE LOGIN] Token không hợp lệ: {e}")
        return jsonify({"success": False, "message": "Token Google không hợp lệ"}), 401
    except Exception as e:
        print(f"[GOOGLE LOGIN ERROR] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Lỗi xác thực Google: {str(e)}"}), 500

@app.route("/api/history/<int:user_id>")
def get_user_history_api(user_id):
    history = get_user_history(user_id)
    return jsonify({"success": True, "history": history})

@app.route("/api/food-stats/<int:user_id>")
def get_food_stats_api(user_id):
    """API thống kê calories theo ngày/tuần"""
    stats = get_user_food_stats(user_id)
    return jsonify({"success": True, "stats": stats})

@app.route("/api/change-password", methods=["POST"])
def change_password():
    data = request.json
    user_id = data.get("user_id")
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    
    if not user_id or not old_password or not new_password:
        return jsonify({"success": False, "message": "Vui lòng nhập đủ thông tin"}), 400
        
    user = get_user_by_id(user_id)
    if not user or not check_password_hash(user["MatKhau"], old_password):
        return jsonify({"success": False, "message": "Mật khẩu cũ không chính xác"}), 400
        
    if update_password(user_id, generate_password_hash(new_password)):
        return jsonify({"success": True, "message": "Đổi mật khẩu thành công"})
    else:
        return jsonify({"success": False, "message": "Có lỗi xảy ra, vui lòng thử lại"}), 500

@app.route("/api/health-profile/<int:user_id>", methods=["GET"])
def get_user_health_profile(user_id):
    profile = get_health_profile(user_id)
    if profile:
        return jsonify({"success": True, "profile": profile})
    return jsonify({"success": False, "message": "Chưa có hồ sơ sức khỏe"}), 404

@app.route("/api/health-profile/<int:user_id>", methods=["POST"])
def update_user_health_profile(user_id):
    data = request.json
    result = upsert_health_profile(user_id, data)
    if result and result.get("success"):
        return jsonify({
            "success": True,
            "message": "Cập nhật hồ sơ sức khỏe thành công",
            "weightChange": result
        })
    return jsonify({"success": False, "message": "Lỗi khi cập nhật hồ sơ"}), 500


@app.route("/api/weight-history/<int:user_id>", methods=["GET"])
def api_weight_history(user_id):
    history = get_weight_history(user_id)
    return jsonify({"success": True, "history": history})

@app.route("/api/meal-suggestions", methods=["GET"])
def get_meal_suggestions():
    """API đề xuất món ăn theo bữa và calo mục tiêu - lấy từ CSDL"""
    meal_type = request.args.get('meal_type', 'breakfast')
    target_calo = float(request.args.get('target_calo', 500))
    
    try:
        conn = get_db_connection()
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # ===== PHÂN LOẠI THEO BỮA ĂN =====
        # Bữa sáng: nhẹ nhàng, nhanh, dễ tiêu hóa
        # Bữa trưa: no bụng, đầy đủ dinh dưỡng, có cơm/bún/mì
        # Bữa tối: vừa phải, không quá nặng nhưng đủ no
        # Bữa phụ: nhẹ, ăn vặt, tráng miệng
        
        # Categories phù hợp theo từng bữa
        meal_categories = {
            'breakfast': [
                'Ăn sáng', 'Món ăn sáng', 'Món hấp', 'Món cháo', 'Món bánh',
                'Món xôi', 'Món nước', 'Ăn nhẹ', 'Breakfast'
            ],
            'lunch': [
                'Món chính', 'Món cơm', 'Món nước', 'Món mặn', 'Món bún',
                'Món kho', 'Món xào', 'Món chiên', 'Món canh', 'Món lẩu',
                'Món nướng', 'Món hầm', 'Món cá', 'Món trộn', 'Món luộc',
                'Món quay', 'Món um', 'Món rang', 'Bún trộn', 'Cơm', 'Lunch',
                'Canh', 'Main dish', 'Món chay'
            ],
            'dinner': [
                'Món chính', 'Món cơm', 'Món mặn', 'Món nước', 'Món bún',
                'Món kho', 'Món xào', 'Món canh', 'Món hấp', 'Món nướng',
                'Món hầm', 'Món cá', 'Món luộc', 'Món um', 'Cơm', 'Canh',
                'Món chay', 'Main dish'
            ],
            'snack': [
                'Ăn nhẹ', 'Ăn chơi', 'Món ăn chơi', 'Khai vị', 'Món chè',
                'Tráng miệng', 'Ăn nhanh', 'Món ăn vặt', 'Món gỏi',
                'Antipasti', 'Fingerfood', 'Snack', 'Món bánh'
            ]
        }
        
        # Keywords trong TÊN MÓN phù hợp theo bữa
        meal_name_keywords = {
            'breakfast': [
                'Phở', 'Bún', 'Cháo', 'Bánh', 'Xôi', 'Hủ Tiếu', 'Mì ',
                'Bánh Canh', 'Bánh Bao', 'Bánh Mì', 'Bánh Cuốn', 'Bún Mọc',
                'Bún Ốc', 'Bún Riêu', 'Bún Bò'
            ],
            'lunch': [
                'Cơm', 'Kho', 'Xào', 'Chiên', 'Nướng', 'Lẩu', 'Canh',
                'Sườn', 'Thịt', 'Cá', 'Tôm', 'Gà', 'Bò', 'Vịt',
                'Heo', 'Ếch', 'Lươn', 'Rắn'
            ],
            'dinner': [
                'Cơm', 'Kho', 'Xào', 'Hấp', 'Canh', 'Nấu', 'Luộc',
                'Thịt', 'Cá', 'Tôm', 'Gà', 'Bò', 'Vịt', 'Um',
                'Bún', 'Phở'
            ],
            'snack': [
                'Chè', 'Gỏi', 'Bánh Tráng', 'Kẹo', 'Ốc', 'Bông',
                'Rau', 'Khô', 'Nem', 'Bánh Khọt', 'Bánh Căn'
            ]
        }
        
        # Giới hạn calo hợp lý theo bữa
        meal_calo_limits = {
            'breakfast': (80, 500),    # Sáng: nhẹ
            'lunch': (200, 600),       # Trưa: no
            'dinner': (150, 520),      # Tối: vừa phải
            'snack': (50, 350)         # Phụ: nhẹ nhàng
        }
        
        # Loại trừ các PhanLoai KHÔNG phù hợp
        meal_exclude_categories = {
            'breakfast': ['Món lẩu', 'Món quay', 'Món hầm'],
            'lunch': ['Món chè', 'Ăn nhẹ', 'Tráng miệng', 'Món ăn vặt'],
            'dinner': ['Món lẩu', 'Món chè', 'Ăn nhẹ', 'Tráng miệng', 'Thức ăn nhanh'],
            'snack': ['Món lẩu', 'Món hầm', 'Món quay', 'Món kho', 'Món cơm']
        }
        
        categories = meal_categories.get(meal_type, [])
        name_keywords = meal_name_keywords.get(meal_type, [])
        calo_min, calo_max = meal_calo_limits.get(meal_type, (50, 600))
        exclude_cats = meal_exclude_categories.get(meal_type, [])
        
        suggestions = []
        seen_ids = set()
        seen_names = set()
        
        # ===== BƯỚC 1: Tìm theo PhanLoai phù hợp =====
        if categories:
            category_conditions = ' OR '.join(['m.PhanLoai ILIKE %s' for _ in categories])
            category_params = [f'%{cat}%' for cat in categories]
            
            # Exclude conditions
            exclude_conditions = ""
            exclude_params_list = []
            if exclude_cats:
                exclude_conditions = ' AND '.join(['m.PhanLoai NOT ILIKE %s' for _ in exclude_cats])
                exclude_params_list = [f'%{ex}%' for ex in exclude_cats]
                exclude_conditions = "AND " + exclude_conditions
            
            query_category = f"""
                SELECT m.MaMonAn, m.TenMonAn, m.MoTa, m.PhanLoai,
                       d.Calo, d.Protein, d.ChatBeo, d.Carbohydrate
                FROM MonAn m
                JOIN DinhDuong d ON m.MaMonAn = d.MaMonAn
                WHERE m.IsDeleted = 0
                AND d.Calo IS NOT NULL
                AND d.Calo BETWEEN %s AND %s
                AND ({category_conditions})
                {exclude_conditions}
                ORDER BY ABS(d.Calo - %s), RANDOM()
                LIMIT 15
            """
            
            params = [calo_min, calo_max] + category_params + exclude_params_list + [target_calo]
            cursor.execute(query_category, params)
            
            for food in cursor.fetchall():
                food_id = food['mamonan']
                food_name = food['tenmonan'].strip().lower()
                if food_id not in seen_ids and food_name not in seen_names:
                    seen_ids.add(food_id)
                    seen_names.add(food_name)
                    suggestions.append(_format_food_suggestion(food))
        
        # ===== BƯỚC 2: Tìm theo tên món ăn (keyword) =====
        if len(suggestions) < 8 and name_keywords:
            keyword_conditions = ' OR '.join(['m.TenMonAn ILIKE %s' for _ in name_keywords])
            keyword_params = [f'%{kw}%' for kw in name_keywords]
            
            exclude_clause = ""
            exclude_id_params = []
            if seen_ids:
                placeholders = ', '.join(['%s'] * len(seen_ids))
                exclude_clause = f"AND m.MaMonAn NOT IN ({placeholders})"
                exclude_id_params = list(seen_ids)
            
            # Exclude categories
            exclude_conditions2 = ""
            exclude_params_list2 = []
            if exclude_cats:
                exclude_conditions2 = ' AND '.join(['m.PhanLoai NOT ILIKE %s' for _ in exclude_cats])
                exclude_params_list2 = [f'%{ex}%' for ex in exclude_cats]
                exclude_conditions2 = "AND " + exclude_conditions2
            
            remaining = 12 - len(suggestions)
            
            query_keywords = f"""
                SELECT m.MaMonAn, m.TenMonAn, m.MoTa, m.PhanLoai,
                       d.Calo, d.Protein, d.ChatBeo, d.Carbohydrate
                FROM MonAn m
                JOIN DinhDuong d ON m.MaMonAn = d.MaMonAn
                WHERE m.IsDeleted = 0
                AND d.Calo IS NOT NULL
                AND d.Calo BETWEEN %s AND %s
                AND ({keyword_conditions})
                {exclude_clause}
                {exclude_conditions2}
                ORDER BY ABS(d.Calo - %s), RANDOM()
                LIMIT %s
            """
            
            params_kw = [calo_min, calo_max] + keyword_params + exclude_id_params + exclude_params_list2 + [target_calo, remaining]
            cursor.execute(query_keywords, params_kw)
            
            for food in cursor.fetchall():
                food_id = food['mamonan']
                food_name = food['tenmonan'].strip().lower()
                if food_id not in seen_ids and food_name not in seen_names:
                    seen_ids.add(food_id)
                    seen_names.add(food_name)
                    suggestions.append(_format_food_suggestion(food))
        
        # ===== BƯỚC 3: Fallback - bổ sung nếu vẫn chưa đủ =====
        if len(suggestions) < 6:
            remaining = 12 - len(suggestions)
            exclude_clause = ""
            exclude_params_fb = []
            
            if seen_ids:
                placeholders = ', '.join(['%s'] * len(seen_ids))
                exclude_clause = f"AND m.MaMonAn NOT IN ({placeholders})"
                exclude_params_fb = list(seen_ids)
            
            # Exclude categories
            exclude_conditions3 = ""
            exclude_params_list3 = []
            if exclude_cats:
                exclude_conditions3 = ' AND '.join(['m.PhanLoai NOT ILIKE %s' for _ in exclude_cats])
                exclude_params_list3 = [f'%{ex}%' for ex in exclude_cats]
                exclude_conditions3 = "AND " + exclude_conditions3
            
            query_fallback = f"""
                SELECT m.MaMonAn, m.TenMonAn, m.MoTa, m.PhanLoai,
                       d.Calo, d.Protein, d.ChatBeo, d.Carbohydrate
                FROM MonAn m
                JOIN DinhDuong d ON m.MaMonAn = d.MaMonAn
                WHERE m.IsDeleted = 0
                AND d.Calo IS NOT NULL
                AND d.Calo BETWEEN %s AND %s
                {exclude_clause}
                {exclude_conditions3}
                ORDER BY ABS(d.Calo - %s), RANDOM()
                LIMIT %s
            """
            
            params_fallback = [calo_min, calo_max] + exclude_params_fb + exclude_params_list3 + [target_calo, remaining]
            cursor.execute(query_fallback, params_fallback)
            
            for food in cursor.fetchall():
                food_id = food['mamonan']
                food_name = food['tenmonan'].strip().lower()
                if food_id not in seen_ids and food_name not in seen_names:
                    seen_ids.add(food_id)
                    seen_names.add(food_name)
                    suggestions.append(_format_food_suggestion(food))
        
        close_db_connection(conn)
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'meal_type': meal_type,
            'target_calo': target_calo
        })
        
    except Exception as e:
        print(f"[ERROR] get_meal_suggestions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


def _format_food_suggestion(food):
    """Format một dòng dữ liệu món ăn thành dict cho API response"""
    return {
        'id': food['mamonan'],
        'name': food['tenmonan'],
        'description': food['mota'] or '',
        'category': food['phanloai'] or '',
        'calories': float(food['calo']) if food['calo'] else 0,
        'protein': float(food['protein']) if food['protein'] else 0,
        'carbs': float(food['carbohydrate']) if food['carbohydrate'] else 0,
        'fats': float(food['chatbeo']) if food['chatbeo'] else 0
    }

# ============================================
# MEAL PLAN SAVE & HISTORY
# ============================================

@app.route("/api/meal-plans/<int:user_id>", methods=["POST"])
def save_meal_plan(user_id):
    """Lưu kế hoạch dinh dưỡng trong ngày"""
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO KeHoachDinhDuong 
            (MaNguoiDung, CaloDuKien, TongCaloChon, BuaSang, BuaSangCalo, BuaTrua, BuaTruaCalo, BuaToi, BuaToiCalo, BuaPhu, BuaPhuCalo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            data.get('caloDuKien', 0),
            data.get('tongCaloChon', 0),
            data.get('buaSang', ''),
            data.get('buaSangCalo', 0),
            data.get('buaTrua', ''),
            data.get('buaTruaCalo', 0),
            data.get('buaToi', ''),
            data.get('buaToiCalo', 0),
            data.get('buaPhu', ''),
            data.get('buaPhuCalo', 0)
        ))
        
        conn.commit()
        close_db_connection(conn)
        return jsonify({'success': True, 'message': 'Đã lưu kế hoạch dinh dưỡng!'})
        
    except Exception as e:
        print(f"[ERROR] save_meal_plan: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route("/api/meal-plans/<int:user_id>", methods=["GET"])
def get_meal_plans(user_id):
    """Lấy lịch sử kế hoạch dinh dưỡng"""
    try:
        from psycopg2.extras import RealDictCursor
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT MaKeHoach, NgayLuu, CaloDuKien, TongCaloChon,
                   BuaSang, BuaSangCalo, BuaTrua, BuaTruaCalo,
                   BuaToi, BuaToiCalo, BuaPhu, BuaPhuCalo
            FROM KeHoachDinhDuong
            WHERE MaNguoiDung = %s
            ORDER BY NgayLuu DESC
            LIMIT 100
        """, (user_id,))
        
        plans = cursor.fetchall()
        close_db_connection(conn)
        
        result = []
        for p in plans:
            result.append({
                'id': p['makehoach'],
                'date': p['ngayluu'].strftime('%Y-%m-%d %H:%M') if p['ngayluu'] else '',
                'month': p['ngayluu'].strftime('%Y-%m') if p['ngayluu'] else '',
                'caloDuKien': float(p['calodukien']) if p['calodukien'] else 0,
                'tongCaloChon': float(p['tongcalochon']) if p['tongcalochon'] else 0,
                'buaSang': p['buasang'] or '',
                'buaSangCalo': float(p['buasangcalo']) if p['buasangcalo'] else 0,
                'buaTrua': p['buatrua'] or '',
                'buaTruaCalo': float(p['buatruacalo']) if p['buatruacalo'] else 0,
                'buaToi': p['buatoi'] or '',
                'buaToiCalo': float(p['buatoicalo']) if p['buatoicalo'] else 0,
                'buaPhu': p['buaphu'] or '',
                'buaPhuCalo': float(p['buaphucalo']) if p['buaphucalo'] else 0
            })
        
        return jsonify({'success': True, 'plans': result})
        
    except Exception as e:
        print(f"[ERROR] get_meal_plans: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# MARK FOOD AS EATEN
# ============================================

@app.route("/api/history/<int:history_id>/mark-eaten", methods=["POST"])
def mark_food_eaten(history_id):
    """Đánh dấu món ăn đã ăn - calo sẽ được tính vào kế hoạch dinh dưỡng"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE LichSu SET DaAn = TRUE WHERE MaLichSu = %s
        """, (history_id,))
        
        if cursor.rowcount == 0:
            close_db_connection(conn)
            return jsonify({'success': False, 'message': 'Không tìm thấy bản ghi'}), 404
        
        conn.commit()
        close_db_connection(conn)
        return jsonify({'success': True, 'message': 'Đã đánh dấu món ăn đã ăn!'})
        
    except Exception as e:
        print(f"[ERROR] mark_food_eaten: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route("/api/admin/users", methods=["GET"])
def api_admin_get_users():
    return jsonify({"success": True, "users": get_all_users()})

@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def api_admin_delete_user(user_id):
    if delete_user(user_id): return jsonify({"success": True, "message": "Xóa người dùng thành công"})
    return jsonify({"success": False, "message": "Lỗi khi xóa người dùng"}), 500

@app.route("/api/admin/users/<int:user_id>/account-type", methods=["PUT"])
def api_admin_update_account_type(user_id):
    data = request.json
    account_type = data.get('account_type', 'free')
    if update_user_account_type(user_id, account_type):
        return jsonify({"success": True, "message": f"Đã chuyển đổi thành tài khoản {account_type}"})
    return jsonify({"success": False, "message": "Lỗi khi cập nhật tài khoản"}), 500

@app.route("/api/admin/users/<int:user_id>/detail", methods=["GET"])
def api_admin_user_detail(user_id):
    """Xem chi tiết user: info + health + history"""
    detail = get_user_detail_admin(user_id)
    if detail:
        return jsonify({"success": True, "detail": detail})
    return jsonify({"success": False, "message": "Không tìm thấy người dùng"}), 404

@app.route("/api/admin/stats", methods=["GET"])
def api_admin_get_stats():
    return jsonify({"success": True, "stats": get_system_stats()})

@app.route("/api/admin/history", methods=["GET"])
def api_admin_get_history():
    return jsonify({"success": True, "history": get_all_history_admin()})

@app.route("/api/admin/history/<int:history_id>", methods=["GET"])
def api_admin_get_history_detail(history_id):
    data = get_history_detail_admin(history_id)
    if data:
        return jsonify({"success": True, "detail": data})
    return jsonify({"success": False, "message": "Không tìm thấy bản ghi lịch sử"}), 404

@app.route("/api/admin/history/<int:history_id>", methods=["PUT"])
def api_admin_update_history(history_id):
    """Admin chỉnh sửa tên món + calo trong lịch sử → tạo thông báo cho user"""
    data = request.json
    new_name = data.get("food_name", "").strip()
    new_calories = data.get("calories")
    
    if not new_name:
        return jsonify({"success": False, "message": "Tên món ăn không được để trống"}), 400
    
    try:
        new_cal = float(new_calories) if new_calories is not None and str(new_calories).strip() != '' else None
    except:
        new_cal = None
    
    result = update_history_record(history_id, new_name, new_cal)
    if not result:
        return jsonify({"success": False, "message": "Không tìm thấy bản ghi"}), 404
    
    # Tạo thông báo cho user nếu tên thay đổi
    if result['user_id'] and result['old_name'] != new_name:
        content = f"Quản trị viên đã cập nhật kết quả nhận diện món ăn của bạn."
        create_notification(
            result['user_id'], history_id, content,
            result['old_name'], new_name
        )
    
    return jsonify({"success": True, "message": "Đã cập nhật và thông báo cho người dùng"})

# ============================================
# COMMENT / FEEDBACK SYSTEM
# ============================================

@app.route("/api/comments", methods=["POST"])
def api_submit_comment():
    """User gửi bình luận phản hồi về kết quả nhận diện"""
    data = request.json
    history_id = data.get("history_id")
    user_id = data.get("user_id")
    content = data.get("content", "").strip()
    
    if not history_id or not user_id or not content:
        return jsonify({"success": False, "message": "Thiếu thông tin"}), 400
    
    if len(content) > 1000:
        return jsonify({"success": False, "message": "Nội dung quá dài (tối đa 1000 ký tự)"}), 400
    
    comment_id = insert_comment(history_id, user_id, content)
    if comment_id:
        # Thông báo cho admin
        try:
            conn = get_db_connection()
            cursor = get_db_cursor(conn)
            cursor.execute("""
                SELECT l.TenMonAn, n.TenNguoiDung 
                FROM LichSu l 
                LEFT JOIN NguoiDung n ON l.MaNguoiDung = n.MaNguoiDung 
                WHERE l.MaLichSu = %s
            """, (history_id,))
            row = cursor.fetchone()
            close_db_connection(conn)
            
            if row:
                food_name = row['tenmonan'] or 'Không rõ'
                user_name = row['tennguoidung'] or 'Ẩn danh'
                notify_admins(
                    f"💬 Bình luận mới từ {user_name} về món \"{food_name}\": {content[:50]}{'...' if len(content) > 50 else ''}",
                    history_id=history_id
                )
        except Exception as e:
            print(f"[NOTIFY] Error notifying admins about comment: {e}")
        
        return jsonify({"success": True, "message": "Đã gửi bình luận", "comment_id": comment_id})
    return jsonify({"success": False, "message": "Lỗi khi gửi bình luận"}), 500

@app.route("/api/comments/<int:history_id>", methods=["GET"])
def api_get_comments(history_id):
    """Lấy danh sách bình luận theo history_id"""
    comments = get_comments_by_history(history_id)
    return jsonify({"success": True, "comments": comments})

@app.route("/api/admin/comments", methods=["GET"])
def api_admin_get_comments():
    """Admin lấy tất cả bình luận"""
    filter_status = request.args.get("status", "all")
    comments = get_all_comments_admin(filter_status)
    return jsonify({"success": True, "comments": comments})

@app.route("/api/admin/comments/<int:comment_id>/reply", methods=["POST"])
def api_admin_reply_comment(comment_id):
    """Admin phản hồi bình luận"""
    data = request.json
    admin_id = data.get("admin_id")
    content = data.get("content", "").strip()
    
    if not admin_id or not content:
        return jsonify({"success": False, "message": "Thiếu thông tin"}), 400
    
    # Lấy thông tin comment gốc
    comment_info = get_comment_detail(comment_id)
    if not comment_info:
        return jsonify({"success": False, "message": "Không tìm thấy bình luận"}), 404
    
    reply_id = admin_reply_comment(comment_id, admin_id, content, comment_info['history_id'])
    if reply_id:
        # Thông báo cho user
        if comment_info['user_id']:
            create_notification(
                comment_info['user_id'],
                comment_info['history_id'],
                f"💬 Admin đã phản hồi bình luận của bạn về món \"{comment_info['food_name']}\": {content[:80]}{'...' if len(content) > 80 else ''}",
                '', ''
            )
        return jsonify({"success": True, "message": "Đã gửi phản hồi", "reply_id": reply_id})
    return jsonify({"success": False, "message": "Lỗi khi gửi phản hồi"}), 500

@app.route("/api/admin/comments/<int:comment_id>", methods=["DELETE"])
def api_admin_delete_comment(comment_id):
    """Admin xóa bình luận"""
    if delete_comment(comment_id):
        return jsonify({"success": True, "message": "Đã xóa bình luận"})
    return jsonify({"success": False, "message": "Lỗi khi xóa"}), 500

@app.route("/api/notifications/<int:user_id>", methods=["GET"])
def api_get_notifications(user_id):
    notifs = get_user_notifications(user_id)
    unread = sum(1 for n in notifs if not n['is_read'])
    return jsonify({"success": True, "notifications": notifs, "unread_count": unread})

@app.route("/api/notifications/<int:notification_id>/read", methods=["PUT"])
def api_mark_notification_read(notification_id):
    if mark_notification_read(notification_id):
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route("/api/notifications/<int:user_id>/read-all", methods=["PUT"])
def api_mark_all_notifications_read(user_id):
    if mark_all_notifications_read(user_id):
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route("/api/admin/history/<int:history_id>", methods=["DELETE"])
def api_admin_delete_history(history_id):
    if delete_history_record(history_id):
        return jsonify({"success": True, "message": "Đã xóa bản ghi lịch sử"})
    return jsonify({"success": False, "message": "Lỗi khi xóa"}), 500

@app.route("/api/admin/history/bulk-delete", methods=["POST"])
def api_admin_bulk_delete_history():
    data = request.get_json()
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"success": False, "message": "Chưa chọn bản ghi nào"})
    deleted = bulk_delete_history(ids)
    if deleted > 0:
        return jsonify({"success": True, "message": f"Đã xóa {deleted} bản ghi"})
    return jsonify({"success": False, "message": "Lỗi khi xóa"}), 500

@app.route("/api/admin/foods", methods=["GET"])
def api_admin_get_foods():
    return jsonify({"success": True, "foods": get_all_foods_admin()})

@app.route("/api/admin/foods/<int:food_id>", methods=["GET"])
def api_admin_get_food(food_id):
    data = get_food_detail_admin(food_id)
    if data: return jsonify({"success": True, "food": data})
    return jsonify({"success": False, "message": "Không tìm thấy món ăn"}), 404

@app.route("/api/admin/foods", methods=["POST"])
def api_admin_add_food():
    data = request.json
    if not data or not data.get("TenMonAn"):
        return jsonify({"success": False, "message": "Thiếu thông tin tên món ăn"}), 400
    if insert_food_full(data):
        return jsonify({"success": True, "message": "Thêm món ăn thành công"})
    return jsonify({"success": False, "message": "Lỗi khi thêm món ăn"}), 500

@app.route("/api/admin/foods/<int:food_id>", methods=["PUT"])
def api_admin_update_food(food_id):
    data = request.json
    if not data or not data.get("TenMonAn"):
        return jsonify({"success": False, "message": "Thiếu thông tin tên món ăn"}), 400
    if update_food_full(food_id, data):
        return jsonify({"success": True, "message": "Cập nhật món ăn thành công"})
    return jsonify({"success": False, "message": "Lỗi khi cập nhật món ăn"}), 500

@app.route("/api/admin/foods/<int:food_id>", methods=["DELETE"])
def api_admin_delete_food(food_id):
    if delete_food_soft(food_id):
        return jsonify({"success": True, "message": "Đã chuyển món ăn vào thùng rác (Soft Delete) thành công"})
    return jsonify({"success": False, "message": "Lỗi khi xóa món ăn"}), 500

@app.route("/api/admin/foods/<int:food_id>/restore", methods=["PUT"])
def api_admin_restore_food(food_id):
    if restore_food_soft(food_id):
        return jsonify({"success": True, "message": "Đã khôi phục món ăn từ thùng rác thành công"})
    return jsonify({"success": False, "message": "Lỗi khi khôi phục món ăn"}), 500

@app.route("/api/admin/foods/<int:food_id>/hard-delete", methods=["DELETE"])
def api_admin_hard_delete_food(food_id):
    if delete_food_hard(food_id):
        return jsonify({"success": True, "message": "Đã xóa vĩnh viễn món ăn khỏi cơ sở dữ liệu"})
    return jsonify({"success": False, "message": "Lỗi khi xóa vĩnh viễn món ăn"}), 500

def get_recommendation(user_id, calories):
    if not user_id or str(calories) == '--':
        return None
    
    try:
        calories = float(calories)
    except:
        return None

    profile = get_health_profile(user_id)
    if not profile:
        return None

    chieu_cao = profile.get('ChieuCao')
    can_nang = profile.get('CanNang')
    muc_tieu = profile.get('MucTieu')

    if not chieu_cao or not can_nang or not muc_tieu:
        return None

    bmi = can_nang / ((chieu_cao / 100) ** 2)
    bmi = round(bmi, 1)

    if bmi < 18.5:
        bmi_category = "Gầy"
    elif 18.5 <= bmi < 25:
        bmi_category = "Bình thường"
    else:
        bmi_category = "Thừa cân"

    threshold = 350
    recommendation = ""
    reason = ""

    # Normalize muc_tieu to lowercase for comparison
    muc_tieu_lower = str(muc_tieu).lower()
    
    if 'giam' in muc_tieu_lower or 'giảm' in muc_tieu_lower:
        if calories > threshold:
            recommendation = "Hạn chế"
            reason = f"Món ăn có lượng calo ({calories} kcal) khá cao, không tốt cho mục tiêu giảm cân."
        else:
            recommendation = "Nên ăn"
            reason = f"Món ăn ít calo ({calories} kcal), phù hợp với mục tiêu giảm cân."
    elif 'tang' in muc_tieu_lower or 'tăng' in muc_tieu_lower:
        if calories > threshold:
            recommendation = "Nên ăn"
            reason = f"Món ăn giàu năng lượng ({calories} kcal), rất tốt cho mục tiêu tăng cân."
        else:
            recommendation = "Ăn vừa phải"
            reason = f"Món ăn ít năng lượng ({calories} kcal), nên ăn kèm các món khác để đủ calo tăng cân."
    else:
        recommendation = "Ăn cân đối"
        reason = f"Món ăn cung cấp {calories} kcal, ăn uống cân đối để duy trì vóc dáng."

    result = {
        "bmi": bmi,
        "bmi_category": bmi_category,
        "recommendation": recommendation,
        "reason": reason
    }

    # ---- TÍCH HỢP KẾ HOẠCH DINH DƯỠNG ----
    max_plan_retries = 2
    for _plan_attempt in range(max_plan_retries + 1):
        conn = None
        try:
            from psycopg2.extras import RealDictCursor
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Lấy kế hoạch dinh dưỡng MỚI NHẤT trong ngày hôm nay
            cursor.execute("""
                SELECT CaloDuKien, TongCaloChon,
                       BuaSang, BuaSangCalo, BuaTrua, BuaTruaCalo,
                       BuaToi, BuaToiCalo, BuaPhu, BuaPhuCalo
                FROM KeHoachDinhDuong
                WHERE MaNguoiDung = %s AND DATE(NgayLuu) = CURRENT_DATE
                ORDER BY NgayLuu DESC LIMIT 1
            """, (user_id,))
            plan = cursor.fetchone()
            
            if plan:
                plan_total = float(plan['calodukien']) if plan['calodukien'] else 0
                
                # Tính tổng calo đã ăn hôm nay (chỉ tính món đã đánh dấu DaAn = TRUE)
                cursor.execute("""
                    SELECT COALESCE(SUM(CASE WHEN DaAn = TRUE THEN Calo ELSE 0 END), 0) as consumed
                    FROM LichSu
                    WHERE MaNguoiDung = %s AND DATE(ThoiGian) = CURRENT_DATE
                """, (user_id,))
                consumed = float(cursor.fetchone()['consumed'] or 0)
                
                remaining = max(0, plan_total - consumed)
                
                # So sánh calo món ăn vs calo còn lại
                if remaining <= 0:
                    plan_status = "khong_nen"
                    plan_msg = f"Bạn đã vượt kế hoạch calo hôm nay ({int(consumed)}/{int(plan_total)} kcal). Không nên ăn thêm món này."
                elif calories <= remaining * 0.4:
                    plan_status = "phu_hop"
                    plan_msg = f"Món ăn ({int(calories)} kcal) phù hợp với kế hoạch. Còn lại {int(remaining)} kcal trong ngày."
                elif calories <= remaining:
                    plan_status = "an_it"
                    plan_msg = f"Món ăn ({int(calories)} kcal) chiếm phần lớn lượng calo còn lại ({int(remaining)} kcal). Nên ăn vừa phải."
                else:
                    plan_status = "khong_nen"
                    plan_msg = f"Món ăn ({int(calories)} kcal) vượt quá lượng calo còn lại ({int(remaining)} kcal). Nên hạn chế hoặc không ăn."
                
                result["plan_advice"] = {
                    "plan_status": plan_status,
                    "plan_message": plan_msg,
                    "plan_total_calo": int(plan_total),
                    "plan_consumed_calo": int(consumed),
                    "plan_remaining_calo": int(remaining),
                    "food_calo": int(calories)
                }
            
            close_db_connection(conn)
            break  # Thành công, thoát retry loop
        except Exception as e:
            print(f"[PLAN ADVICE] Error (attempt {_plan_attempt + 1}): {e}")
            if conn:
                close_db_connection(conn)
            import time as _time
            if _plan_attempt < max_plan_retries:
                _time.sleep(1)
            # Nếu hết retry, bỏ qua plan_advice (không crash)

    return result

@app.route("/api/dishes/<food_name>", methods=["GET"])
def get_dish_info(food_name):
    """API lấy thông tin món ăn trực tiếp từ database (cho demo mode)"""
    try:
        food_data = search_food_by_name(food_name)
        
        if not food_data:
            return jsonify({
                "success": False,
                "message": f"Không tìm thấy món ăn '{food_name}' trong database"
            }), 404
        
        # Format giống như predict endpoint
        dinh_duong = food_data.get("DinhDuong") or {}
        cong_thuc = food_data.get("CongThuc") or {}
        nguyen_lieu = cong_thuc.get("NguyenLieu") or []
        
        response_data = {
            "success": True,
            "predicted_class_name": food_name,
            "confidence": 100.0,  # Demo mode = 100% confidence
            "food_data": {
                "name": food_data.get("TenMonAn", food_name),
                "description": food_data.get("MoTa", ""),
                "calories": dinh_duong.get("Calo", "--"),
                "proteins": dinh_duong.get("Protein", "--"),
                "carbs": dinh_duong.get("Carbohydrate", "--"),
                "fats": dinh_duong.get("ChatBeo", "--"),
                "recipe_instructions": cong_thuc.get("HuongDan", ""),
                "recipe_time": cong_thuc.get("ThoiGianNau", ""),
                "ingredients": nguyen_lieu
            },
            "message": "Chế độ demo - Dữ liệu từ database"
        }
        
        user_id = request.args.get("user_id")
        if user_id and str(user_id).isdigit():
            rec = get_recommendation(int(user_id), dinh_duong.get("Calo", "--"))
            if rec:
                response_data["health_recommendation"] = rec

        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"[Get Dish Error] {e}")
        return jsonify({
            "success": False,
            "message": f"Lỗi server: {str(e)}"
        }), 500

def _is_english_text(text):
    """Kiểm tra nhanh xem text có phải tiếng Anh không (dựa trên ký tự ASCII)"""
    if not text or len(text) < 5:
        return False
    # Đếm ký tự ASCII (a-z, A-Z)
    ascii_count = sum(1 for c in text if c.isascii() and c.isalpha())
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return False
    # Nếu > 80% là ký tự ASCII → khả năng cao là tiếng Anh
    ratio = ascii_count / total_alpha
    
    # Nếu tỷ lệ ASCII rất cao (> 95%) → gần chắc chắn là tiếng Anh (hoặc ít nhất không phải tiếng Việt)
    if ratio > 0.95 and len(text) >= 15:
        return True
    
    # Kiểm tra thêm: có chứa từ tiếng Anh phổ biến không
    english_words = [
        'the', 'this', 'that', 'with', 'and', 'for', 'you', 'are', 'from',
        'recipe', 'make', 'want', 'add', 'free', 'servings', 'calories',
        'ingredients', 'cook', 'minutes', 'might', 'should', 'gluten',
        'one', 'serving', 'contains', 'protein', 'fat', 'carbs',
        'just', 'your', 'can', 'will', 'have', 'has', 'been', 'was',
        'cup', 'tablespoon', 'teaspoon', 'ounce', 'pound',
        'bake', 'boil', 'fry', 'grill', 'roast', 'steam', 'stir',
        'dairy', 'vegan', 'vegetarian', 'organic', 'healthy',
        'delicious', 'traditional', 'popular', 'dish', 'food', 'meal',
        'dessert', 'snack', 'appetizer', 'sauce', 'soup', 'salad',
        'chicken', 'beef', 'pork', 'fish', 'shrimp', 'rice', 'noodle',
        'per', 'of', 'in', 'is', 'it', 'to', 'a', 'an',
    ]
    text_lower = text.lower()
    english_word_count = sum(1 for w in english_words if f' {w} ' in f' {text_lower} ')
    
    # Nếu tỷ lệ ASCII >= 80% VÀ có ít nhất 1 từ tiếng Anh
    if ratio >= 0.80 and english_word_count >= 1:
        return True
    
    # Nếu có >= 3 từ tiếng Anh phổ biến, dù tỷ lệ ASCII thấp hơn
    if english_word_count >= 3:
        return True
    
    return False

def _batch_translate_food_data(food_name, description, instructions, ingredients_list):
    """
    Dịch mô tả, hướng dẫn và nguyên liệu trong CÙNG MỘT request Gemini 
    để tránh lỗi 429 Too Many Requests.
    """
    import os
    import requests as req
    import json
    import time
    
    # Kiểm tra xem có gì cần dịch không
    needs_desc = description and _is_english_text(description)
    needs_inst = instructions and _is_english_text(instructions)
    
    # Kiểm tra nguyên liệu
    needs_ing = False
    if ingredients_list:
        sample_names = [ing.get("TenNguyenLieu", "") for ing in ingredients_list[:3] if ing.get("TenNguyenLieu")]
        if sample_names:
            combined = " ".join(sample_names)
            is_eng = _is_english_text(combined)
            if not is_eng:
                total_alpha = sum(1 for c in combined if c.isalpha())
                if total_alpha > 0:
                    ascii_ratio = sum(1 for c in combined if c.isascii() and c.isalpha()) / total_alpha
                    is_eng = ascii_ratio >= 0.95 and total_alpha >= 5
            needs_ing = is_eng
            
    # Nếu không có gì cần dịch, trả về nguyên gốc
    if not (needs_desc or needs_inst or needs_ing):
        return description, instructions, ingredients_list
        
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        return description, instructions, ingredients_list
        
    print(f"[TRANSLATE BATCH] Cần dịch cho món '{food_name}'. Gửi 1 request duy nhất...")
    
    # Chuẩn bị dữ liệu nguyên liệu dạng text
    ing_text = ""
    if needs_ing:
        ing_items = [f"{i}. {ing.get('TenNguyenLieu','')} - {ing.get('SoLuong','')}" for i, ing in enumerate(ingredients_list)]
        ing_text = "\n".join(ing_items)
        
    prompt = f"""Dịch các thông tin sau về món ăn "{food_name}" sang tiếng Việt tự nhiên.
Chỉ trả về JSON hợp lệ, KHÔNG có markdown (không dùng ```json), KHÔNG giải thích.

DỮ LIỆU CẦN DỊCH:
1. Mô tả: "{description[:500] if needs_desc else ''}"
2. Hướng dẫn nấu: "{instructions[:800] if needs_inst else ''}"
3. Nguyên liệu:
{ing_text if needs_ing else ''}

TRẢ VỀ ĐÚNG FORMAT JSON NÀY:
{{
    "description": "mô tả đã dịch (nếu có dữ liệu, nếu không để rỗng)",
    "instructions": "hướng dẫn đã dịch (nếu có dữ liệu, nếu không để rỗng)",
    "ingredients": [
        {{"TenNguyenLieu": "tên nguyên liệu 1 đã dịch", "SoLuong": "số lượng đã dịch"}}
    ]
}}
"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800, "responseMimeType": "application/json"}
    }
    
    for attempt in range(2):
        try:
            response = req.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                data = response.json()
                result_text = data['candidates'][0]['content']['parts'][0]['text'].strip()
                
                # Parse JSON
                parsed = json.loads(result_text)
                
                # Gán lại kết quả
                res_desc = parsed.get("description", "") if needs_desc else description
                res_inst = parsed.get("instructions", "") if needs_inst else instructions
                
                res_ing = ingredients_list
                if needs_ing and "ingredients" in parsed and isinstance(parsed["ingredients"], list):
                    if len(parsed["ingredients"]) > 0:
                        res_ing = parsed["ingredients"]
                        
                print(f"[TRANSLATE BATCH] Thành công (attempt {attempt+1})!")
                return res_desc, res_inst, res_ing
            elif response.status_code == 429:
                print(f"[TRANSLATE BATCH] Lỗi 429 Too Many Requests (attempt {attempt+1})")
                time.sleep(2)  # Đợi lâu hơn khi bị rate limit
            else:
                print(f"[TRANSLATE BATCH] Lỗi API: {response.status_code} (attempt {attempt+1})")
        except Exception as e:
            print(f"[TRANSLATE BATCH] Error: {e} (attempt {attempt+1})")
            
        time.sleep(1)
        
    print(f"[TRANSLATE BATCH] Thất bại sau 2 attempts, giữ nguyên dữ liệu.")
    return description, instructions, ingredients_list

@app.route("/predict", methods=["POST"])
def predict():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "No file selected"}), 400
    
    # Kiểm tra quota nhận diện cho free user
    user_id_check = request.form.get("user_id")
    if user_id_check and str(user_id_check).isdigit():
        quota = check_user_quota(int(user_id_check))
        if not quota['allowed']:
            return jsonify({
                'success': False,
                'quota_exceeded': True,
                'message': 'Bạn đã hết lượt nhận diện hôm nay. Nâng cấp Premium để sử dụng không giới hạn!',
                'quota': quota
            }), 200
    
    try:
        image_bytes = file.read()
        
        # 1. Gọi API nhận diện món ăn từ hình ảnh
        # analyze_image trả về 4 giá trị: (food_name_vi, food_name_en, confidence, error_msg)
        food_name_vi, food_name_en, confidence, error_msg = analyze_image(image_bytes)
        
        # HỖ TRỢ DEMO MODE KHI API LỖI HOẶC QUÁ TẢI (Nhận diện qua tên file hoặc ngẫu nhiên)
        if not food_name_vi:
            import unicodedata
            import random
            filename = file.filename.lower()
            filename_no_accent = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode('utf-8')
            
            if "pho" in filename_no_accent:
                food_name_vi, food_name_en, confidence = "Phở", "Pho", 0.99
                print(f"[DEMO FALLBACK] Nhận diện qua tên file: {file.filename} -> Phở")
            elif "banh" in filename_no_accent and "mi" in filename_no_accent:
                food_name_vi, food_name_en, confidence = "Bánh Mì", "Banh Mi", 0.99
                print(f"[DEMO FALLBACK] Nhận diện qua tên file: {file.filename} -> Bánh Mì")
            elif "bun" in filename_no_accent and "cha" in filename_no_accent:
                food_name_vi, food_name_en, confidence = "Bún Chả", "Bun Cha", 0.99
                print(f"[DEMO FALLBACK] Nhận diện qua tên file: {file.filename} -> Bún Chả")
            else:
                # Nếu không khớp tên file, chọn ngẫu nhiên một món ăn phổ biến để demo
                default_foods = [("Cơm Tấm", "Com Tam"), ("Gỏi Cuốn", "Goi Cuon"), ("Bánh Xèo", "Banh Xeo"), ("Phở Bò", "Pho Bo"), ("Bún Bò Huế", "Bun Bo Hue")]
                random_food = random.choice(default_foods)
                food_name_vi, food_name_en, confidence = random_food[0], random_food[1], 0.85
                print(f"[DEMO FALLBACK] Nhận diện ngẫu nhiên (API hết hạn): {file.filename} -> {food_name_vi}")
                error_msg = error_msg or "API keys đã hết hạn hoặc quá tải. Trả về kết quả nhận diện mô phỏng."

        # Cảnh báo người dùng nếu dùng fallback mô phỏng
        if error_msg and "API keys đã hết hạn" in error_msg:
            print(f"[WARNING] API đang gặp sự cố, hệ thống chuyển sang chế độ Demo ngẫu nhiên.")
        
        # Kiểm tra nếu hình ảnh KHÔNG PHẢI MÓN ĂN
        if food_name_vi == "NOT_FOOD":
            return jsonify({
                "success": False,
                "is_food": False,
                "message": "Hình ảnh này không phải là món ăn!",
                "suggestion": "Vui lòng chụp hoặc tải lên hình ảnh một món ăn để hệ thống có thể nhận diện và phân tích dinh dưỡng."
            }), 200
        
        # 2. Xử lý tên tiếng Việt
        # Nếu Gemini đã trả tên tiếng Việt (có dấu), ưu tiên dùng
        # Nếu API khác trả tên tiếng Anh, gọi translator để dịch
        food_name_english = food_name_en or food_name_vi  # Lưu tên tiếng Anh để search
        
        # Kiểm tra xem food_name_vi đã là tiếng Việt có dấu chưa
        import unicodedata
        has_vietnamese_chars = any(
            unicodedata.category(c) == 'Mn'  # Mark, Nonspacing (dấu tiếng Việt)
            for c in unicodedata.normalize('NFD', food_name_vi)
        )
        
        if has_vietnamese_chars:
            # Gemini đã trả tên tiếng Việt có dấu → dùng trực tiếp
            food_name_vietnamese = food_name_vi
            print(f"[PREDICT] Dùng tên tiếng Việt từ AI: '{food_name_vietnamese}'")
        else:
            # Tên chưa có dấu tiếng Việt → cần dịch
            food_name_vietnamese = translate_food_name(food_name_vi)
            print(f"[TRANSLATE] '{food_name_vi}' → '{food_name_vietnamese}'")
        
        # 3. Tìm kiếm món ăn trong Database (thử cả tiếng Anh và tiếng Việt)
        print(f"[INFO] Tìm kiếm '{food_name_vietnamese}' trong database...")
        food_data = search_food_by_name(food_name_vietnamese)
        
        # Nếu không tìm thấy bằng tiếng Việt, thử tiếng Anh
        if not food_data and food_name_vietnamese != food_name_english:
            print(f"[INFO] Thử tìm bằng tên tiếng Anh: '{food_name_english}'")
            food_data = search_food_by_name(food_name_english)
        
        is_newly_added = False
        found_in_db = bool(food_data)  # Track if food was found in DB
        
        # 4. Nếu không có trong database, tự động lấy thông tin từ AI (Tiếng Việt) và thêm vào
        ai_data = None  # Lưu dữ liệu AI để fallback nếu DB insert thất bại
        if not food_data:
            print(f"[INFO] Không tìm thấy '{food_name_vietnamese}' trong database. Đang tạo thông tin mới bằng AI...")
            try:
                from ai_generator import generate_food_data_vietnamese
                
                ai_data = generate_food_data_vietnamese(food_name_english)
                
                if ai_data:
                    print(f"[INFO] Đã tạo thông tin từ AI. Đang thêm vào database...")
                    
                    # Nếu translation dictionary không có, dùng tên tiếng Việt do AI trả về
                    if food_name_vietnamese == food_name_english and "TenMonAn" in ai_data:
                        food_name_vietnamese = ai_data["TenMonAn"]
                    
                    # Chuẩn bị dữ liệu để insert vào database
                    food_to_insert = {
                        "TenMonAn": food_name_vietnamese,
                        "MoTa": ai_data.get("MoTa", f"Món ăn {food_name_vietnamese}"),
                        "PhanLoai": ai_data.get("PhanLoai", "Món ăn"),
                        "DinhDuong": ai_data.get("DinhDuong", {
                            "Calo": 0, "Protein": 0, "ChatBeo": 0, "Carbohydrate": 0, "Vitamin": ""
                        }),
                        "CongThuc": ai_data.get("CongThuc", {
                            "HuongDan": "Chưa có hướng dẫn",
                            "ThoiGianNau": 30,
                            "KhauPhan": 1,
                            "NguyenLieu": []
                        })
                    }
                    
                    # Thêm vào database
                    if insert_food_full(food_to_insert):
                        print(f"[SUCCESS] Đã thêm '{food_name_vietnamese}' vào database!")
                        is_newly_added = True
                        
                        # Tìm lại trong database
                        food_data = search_food_by_name(food_name_vietnamese)
                    else:
                        print(f"[WARNING] Không thể thêm vào DB, sẽ dùng dữ liệu AI trực tiếp cho '{food_name_vietnamese}'")
                else:
                    print(f"[WARNING] Không tạo được dữ liệu từ AI cho '{food_name_english}'")
                    
            except Exception as e:
                print(f"[ERROR] Lỗi khi tạo dữ liệu từ AI: {e}")
                # Không làm gián đoạn flow nếu external API lỗi

        # 4b. Fallback: Nếu vẫn chưa có food_data nhưng ai_data có sẵn, dùng trực tiếp từ AI
        if not food_data and ai_data:
            print(f"[FALLBACK] Sử dụng dữ liệu AI trực tiếp cho '{food_name_vietnamese}' (không qua DB)")
            dinh_duong_ai = ai_data.get("DinhDuong", {})
            cong_thuc_ai = ai_data.get("CongThuc", {})
            food_data = {
                "TenMonAn": ai_data.get("TenMonAn", food_name_vietnamese),
                "MoTa": ai_data.get("MoTa", f"Món ăn {food_name_vietnamese}"),
                "PhanLoai": ai_data.get("PhanLoai", "Món ăn"),
                "DinhDuong": {
                    "Calo": dinh_duong_ai.get("Calo", 0),
                    "Protein": dinh_duong_ai.get("Protein", 0),
                    "ChatBeo": dinh_duong_ai.get("ChatBeo", 0),
                    "Carbohydrate": dinh_duong_ai.get("Carbohydrate", 0),
                    "Vitamin": dinh_duong_ai.get("Vitamin", "")
                },
                "CongThuc": {
                    "HuongDan": cong_thuc_ai.get("HuongDan", ""),
                    "ThoiGianNau": cong_thuc_ai.get("ThoiGianNau", 0),
                    "KhauPhan": cong_thuc_ai.get("KhauPhan", 0),
                    "NguyenLieu": cong_thuc_ai.get("NguyenLieu", [])
                }
            }
            is_newly_added = True  # Đánh dấu là dữ liệu mới từ AI

        # 4c. Fallback cuối cùng: Nếu cả DB và ai_data đều không có, thử Gemini trực tiếp
        if not food_data:
            print(f"[FALLBACK FINAL] Thử lấy dữ liệu từ Gemini trực tiếp cho '{food_name_english}'...")
            try:
                from external_api import get_food_info_from_gemini
                gemini_info = get_food_info_from_gemini(food_name_english)
                if gemini_info:
                    food_data = {
                        "TenMonAn": food_name_vietnamese,
                        "MoTa": gemini_info.get("description", f"Món ăn {food_name_vietnamese}"),
                        "PhanLoai": gemini_info.get("category", "Món ăn"),
                        "DinhDuong": {
                            "Calo": gemini_info.get("calories", 0),
                            "Protein": gemini_info.get("protein", 0),
                            "ChatBeo": gemini_info.get("fat", 0),
                            "Carbohydrate": gemini_info.get("carbs", 0),
                            "Vitamin": gemini_info.get("vitamins", "")
                        },
                        "CongThuc": {
                            "HuongDan": gemini_info.get("instructions", ""),
                            "ThoiGianNau": gemini_info.get("cooking_time", 0),
                            "KhauPhan": gemini_info.get("servings", 0),
                            "NguyenLieu": gemini_info.get("ingredients", [])
                        }
                    }
                    is_newly_added = True
                    print(f"[FALLBACK FINAL] Thành công! Có dữ liệu Gemini cho '{food_name_vietnamese}'")
            except Exception as e:
                print(f"[FALLBACK FINAL] Lỗi: {e}")

        # 5. Format Kết quả (sử dụng tên tiếng Việt)
        confidence_pct = round(confidence * 100, 2) if confidence else 0
        
        response_data = {
            "success": True,
            "predicted_class_name": food_name_vietnamese,  # Trả về tên tiếng Việt
            "confidence": confidence_pct,
            "food_data": None,
            "message": "",
            "found_in_db": found_in_db,  # NEW: Cho frontend biết món có sẵn hay không
            "is_new": is_newly_added  # NEW: Cho frontend biết món vừa được thêm
        }
        
        if food_data:
            # Map properties cho Frontend
            dinh_duong = food_data.get("DinhDuong") or {}
            cong_thuc = food_data.get("CongThuc") or {}
            nguyen_lieu = cong_thuc.get("NguyenLieu") or []
            
            # Dịch hàng loạt (batch) cho mô tả, hướng dẫn và nguyên liệu để tránh lỗi 429
            raw_desc = food_data.get("MoTa", "")
            raw_instructions = cong_thuc.get("HuongDan", "")
            
            description_vi, instructions_vi, translated_ingredients = _batch_translate_food_data(
                food_name_vietnamese, raw_desc, raw_instructions, nguyen_lieu
            )
            
            # Dịch tên món ăn nếu vẫn còn là tiếng Anh
            display_name = food_data.get("TenMonAn", food_name_vietnamese)
            if display_name and _is_english_text(display_name) and len(display_name) > 2:
                display_name = translate_food_name(display_name)
            
            response_data["food_data"] = {
                "name": display_name,
                "description": description_vi,
                "calories": dinh_duong.get("Calo", "--"),
                "proteins": dinh_duong.get("Protein", "--"),
                "carbs": dinh_duong.get("Carbohydrate", "--"),
                "fats": dinh_duong.get("ChatBeo", "--"),
                "recipe_instructions": instructions_vi,
                "recipe_time": cong_thuc.get("ThoiGianNau", ""),
                "ingredients": translated_ingredients
            }
            
            # Cập nhật predicted_class_name để frontend hiển thị tên tiếng Việt
            response_data["predicted_class_name"] = display_name
            
            if is_newly_added and not found_in_db:
                response_data["message"] = f"✨ Dữ liệu món '{display_name}' được tạo bởi AI."
            elif is_newly_added:
                response_data["message"] = f"✨ Món ăn '{display_name}' vừa được thêm vào cơ sở dữ liệu!"
            else:
                response_data["message"] = f"✅ Đã tìm thấy thông tin món '{display_name}' trong cơ sở dữ liệu"
        else:
            response_data["message"] = f"⚠️ Nhận diện được '{food_name_vietnamese}' nhưng chưa có đầy đủ thông tin. Vui lòng thử lại sau."


        # Tạo base64 image để lưu lịch sử
        image_base64 = ""
        try:
            file.seek(0)  # Reset file pointer
            img_b64 = base64.b64encode(image_bytes).decode('utf-8')
            # Detect mime type
            mime = 'image/jpeg'
            if file.filename and file.filename.lower().endswith('.png'):
                mime = 'image/png'
            elif file.filename and file.filename.lower().endswith('.webp'):
                mime = 'image/webp'
            image_base64 = f"data:{mime};base64,{img_b64}"
        except Exception as e:
            print(f"[WARNING] Không thể encode ảnh base64: {e}")

        # Lấy calories từ food_data
        food_calories = 0
        if food_data and food_data.get("DinhDuong"):
            try:
                food_calories = float(food_data["DinhDuong"].get("Calo", 0))
            except:
                food_calories = 0

        user_id = request.form.get("user_id")
        if user_id and str(user_id).isdigit():
            try:
                # Lưu lịch sử với ảnh base64 và calories - trả về history_id
                history_id = insert_lich_su(int(user_id), image_base64, food_name_vietnamese, confidence_pct, food_calories)
                if history_id:
                    response_data["history_id"] = history_id
            except Exception as e:
                print(f"Error saving history: {e}")

            # Tính toán lời khuyên sức khỏe
            if food_data and food_data.get("DinhDuong"):
                calo = food_data["DinhDuong"].get("Calo", "--")
                rec = get_recommendation(int(user_id), calo)
                if rec:
                    response_data["health_recommendation"] = rec
                    
                    # Lưu plan_advice vào LichSu nếu có
                    if rec.get("plan_advice") and response_data.get("history_id"):
                        save_conn = None
                        try:
                            import json
                            save_conn = get_db_connection()
                            cursor = save_conn.cursor()
                            cursor.execute("""
                                UPDATE LichSu SET KhuyenNghiKeHoach = %s WHERE MaLichSu = %s
                            """, (json.dumps(rec["plan_advice"], ensure_ascii=False), response_data["history_id"]))
                            save_conn.commit()
                            close_db_connection(save_conn)
                        except Exception as pe:
                            print(f"[PLAN SAVE] Error saving plan advice: {pe}")
                            if save_conn:
                                close_db_connection(save_conn)

        return jsonify(response_data)
    
    except Exception as e:
        print(f"[PREDICT ERROR] Lỗi không mong đợi: {e}")
        import traceback
        traceback.print_exc()
        
        # Phân loại lỗi để hiển thị thông báo thân thiện
        error_str = str(e).lower()
        if any(kw in error_str for kw in ['ssl', 'connection', 'server closed', 'broken pipe', 'timeout', 'could not connect']):
            user_message = "Hệ thống đang tạm gián đoạn kết nối. Vui lòng thử lại sau vài giây."
            suggestion = "Đây là lỗi tạm thời từ server database, thường tự khắc phục trong vài giây."
        else:
            user_message = "Đã xảy ra lỗi trong quá trình phân tích."
            suggestion = "Vui lòng thử lại sau hoặc chọn ảnh khác."
        
        return jsonify({
            "success": False,
            "message": user_message,
            "suggestion": suggestion
        }), 500

# ============================================
# PREMIUM & PAYMENT ENDPOINTS
# ============================================

@app.route("/api/user/<int:user_id>/quota", methods=["GET"])
def api_user_quota(user_id):
    """Kiểm tra quota nhận diện của user"""
    quota = check_user_quota(user_id)
    return jsonify({"success": True, "quota": quota})

@app.route("/api/user/<int:user_id>/info", methods=["GET"])
def api_user_info(user_id):
    """Lấy thông tin profile user"""
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "message": "Không tìm thấy người dùng"}), 404
        
    return jsonify({
        "success": True, 
        "user": {
            "id": user.get('MaNguoiDung'),
            "name": user.get('TenNguoiDung'),
            "email": user.get('Email'),
            "role": user.get('VaiTro'),
            "account_type": user.get('LoaiTaiKhoan', 'free'),
            "remaining_days": user.get('RemainingDays', 0)
        }
    })

@app.route("/api/payment/payos/create", methods=["POST"])
def api_payos_create():
    """Tạo đơn thanh toán PayOS để nâng cấp Premium"""
    data = request.json
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"success": False, "message": "Thiếu user_id"}), 400
    
    # Kiểm tra user đã premium chưa
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "message": "Không tìm thấy người dùng"}), 404
    
    if user.get("LoaiTaiKhoan") == "premium":
        return jsonify({"success": False, "message": "Tài khoản đã là Premium"}), 400
    
    # Tạo order
    order_id = generate_order_id(user_id)
    amount = PREMIUM_PRICE
    
    # Lưu payment vào DB
    create_payment(user_id, order_id, amount)
    
    # Xác định base URL
    base_url = request.host_url.rstrip('/')
    return_url = f"{base_url}/api/payment/payos/return?orderCode={order_id}"
    cancel_url = f"{base_url}/api/payment/payos/cancel?orderCode={order_id}"
    
    # Gọi hàm create từ payos_payment
    result = create_payos_payment(
        order_id=order_id, 
        amount=amount, 
        description="Nâng cấp Premium", 
        return_url=return_url, 
        cancel_url=cancel_url
    )
    
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 500

@app.route("/api/payment/payos/return", methods=["GET"])
def api_payos_return():
    """Xử lý redirect từ PayOS (Dùng làm fallback thay cho webhook khi chạy ở localhost)"""
    from flask import redirect
    order_id = request.args.get("orderCode")
    if not order_id:
        return redirect("/?payment=failed")
        
    try:
        from payos_payment import payos_client
        link_info = payos_client.getPaymentLinkInformation(order_id)
        
        if getattr(link_info, "status", None) == "PAID":
            payment = get_payment_by_order_id(order_id)
            # Kiểm tra nếu thanh toán chưa được update bởi webhook
            if payment and payment['trangthai'] != 'success':
                trans_id = ''
                if hasattr(link_info, "transactions") and link_info.transactions:
                    trans_id = str(getattr(link_info.transactions[0], "reference", ""))
                
                import json as json_module
                response_data = ""
                if hasattr(link_info, "model_dump_json"):
                    response_data = link_info.model_dump_json()
                elif hasattr(link_info, "dict"):
                    response_data = json_module.dumps(link_info.dict(), ensure_ascii=False)
                
                update_payment_status(order_id, 'success', trans_id, response_data)
                
                # Nâng cấp tài khoản
                user_id = payment['manguoidung']
                upgrade_user_account(user_id)
                
                # Thông báo
                create_notification(
                    user_id,
                    "🎉 Chúc mừng! Tài khoản của bạn đã được nâng cấp lên Premium. Bạn có thể sử dụng tất cả tính năng không giới hạn!",
                    None
                )
                
                # Thông báo cho admin
                user = get_user_by_id(user_id)
                user_name = user.get('TenNguoiDung', 'Unknown') if user else 'Unknown'
                notify_admins(
                    f"💰 Thanh toán thành công! {user_name} đã nâng cấp Premium - PayOS OrderCode: {order_id}"
                )
                
        # Trở về trang chủ, trigger frontend JS
        return redirect(f"/?payment=success&orderCode={order_id}")
    except Exception as e:
        print(f"[PAYOS RETURN ERROR] {e}")
        from flask import redirect
        return redirect("/?payment=failed")

@app.route("/api/payment/payos/cancel", methods=["GET"])
def api_payos_cancel():
    """Xử lý redirect khi người dùng hủy thanh toán từ PayOS"""
    from flask import redirect
    order_id = request.args.get("orderCode")
    if not order_id:
        return redirect("/?payment=failed")
        
    try:
        payment = get_payment_by_order_id(order_id)
        if payment and payment['trangthai'] == 'pending':
            update_payment_status(order_id, 'failed', '', 'User cancelled payment')
            
            # Thông báo cho admin
            user_id = payment['manguoidung']
            user = get_user_by_id(user_id)
            user_name = user.get('TenNguoiDung', 'Unknown') if user else 'Unknown'
            notify_admins(
                f"❌ Khách hàng hủy thanh toán! {user_name} đã hủy giao dịch nâng cấp Premium - PayOS OrderCode: {order_id}"
            )
            
        return redirect(f"/?payment=failed&orderCode={order_id}")
    except Exception as e:
        print(f"[PAYOS CANCEL ERROR] {e}")
        from flask import redirect
        return redirect("/?payment=failed")

@app.route("/api/payment/payos/webhook", methods=["POST"])
def api_payos_webhook():
    """PayOS Webhook"""
    try:
        webhook_body = request.json
        print(f"[PAYOS WEBHOOK] Received: {json.dumps(webhook_body)}")
        
        # Verify webhook
        is_valid, data = verify_payos_webhook(webhook_body)
        
        if not is_valid or not data:
            return jsonify({"success": False, "message": "Invalid webhook"}), 400
            
        order_id = str(data.orderCode)
        trans_id = str(data.transactionDateTime) if hasattr(data, 'transactionDateTime') else ''
        
        import json as json_module
        response_data = json_module.dumps(webhook_body, ensure_ascii=False)
        
        # Theo docs PayOS: success hoặc mã lỗi tương ứng
        if data.code == "00": 
            # Thanh toán thành công
            update_payment_status(order_id, 'success', trans_id, response_data)
            
            # Nâng cấp tài khoản
            payment = get_payment_by_order_id(order_id)
            if payment:
                user_id = payment['manguoidung']
                upgrade_user_account(user_id)
                
                # Thông báo cho user
                create_notification(
                    user_id,
                    "🎉 Chúc mừng! Tài khoản của bạn đã được nâng cấp lên Premium. Bạn có thể sử dụng tất cả tính năng không giới hạn!",
                    None
                )
                
                # Thông báo cho admin
                user = get_user_by_id(user_id)
                user_name = user.get('TenNguoiDung', 'Unknown') if user else 'Unknown'
                notify_admins(
                    f"💰 Thanh toán thành công! {user_name} đã nâng cấp Premium - PayOS OrderCode: {order_id}"
                )
        else:
            update_payment_status(order_id, 'failed', trans_id, response_data)
            
        return jsonify({"success": True, "message": "Webhook processed"}), 200
        
    except Exception as e:
        print(f"[PAYOS WEBHOOK ERROR] {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/payment/status/<order_id>", methods=["GET"])
def api_payment_status(order_id):
    """Kiểm tra trạng thái thanh toán"""
    payment = get_payment_by_order_id(order_id)
    if not payment:
        return jsonify({"success": False, "message": "Không tìm thấy đơn thanh toán"}), 404
    
    return jsonify({
        "success": True,
        "payment": {
            "order_id": payment['madonhang'],
            "status": payment['trangthai'],
            "amount": float(payment['sotien']),
            "method": payment['phuongthuc'],
            "created_at": payment['thoigiantao'].strftime('%Y-%m-%d %H:%M:%S') if payment.get('thoigiantao') else ''
        }
    })

@app.route("/api/admin/payments", methods=["GET"])
def api_admin_payments():
    """Admin: Danh sách tất cả thanh toán"""
    payments = get_all_payments_admin()
    return jsonify({"success": True, "payments": payments})

@app.route("/api/admin/payment-stats", methods=["GET"])
def api_admin_payment_stats():
    """Admin: Thống kê doanh thu"""
    stats = get_payment_stats_admin()
    return jsonify({"success": True, "stats": stats})

import json

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
