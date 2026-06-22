---
title: Smart Food Analysis
emoji: 🍜
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 5000
pinned: false
short_description: AI food recognition & nutrition analysis
---

# 🍜 Smart Food Analysis - Hệ Thống Nhận Diện Món Ăn AI

Ứng dụng web nhận diện món ăn từ hình ảnh, sử dụng AI và API bên ngoài kết hợp cơ sở dữ liệu SQLite để cung cấp thông tin dinh dưỡng, công thức nấu và nguyên liệu chi tiết.

## ✨ Tính Năng Chính

- 🤖 **Nhận diện món ăn bằng AI** - Upload ảnh và nhận kết quả ngay lập tức
- 🌐 **Hỗ trợ đa ngôn ngữ** - Tự động dịch tên món ăn sang tiếng Việt
- 📊 **Thông tin dinh dưỡng** - Calo, Protein, Carbs, Chất béo
- 📝 **Công thức nấu chi tiết** - Hướng dẫn từng bước với nguyên liệu cụ thể
- 👤 **Quản lý tài khoản** - Đăng ký, đăng nhập, lịch sử tra cứu
- 🔐 **Trang Admin** - Quản lý người dùng và món ăn
- 🎨 **Giao diện đẹp mắt** - Light theme với accordion UI

## 🏗️ Kiến Trúc Hệ Thống

```
KLTN/
├── frontend/                    # Giao diện người dùng
│   ├── index.html              # Trang chính (SPA)
│   ├── style.css               # Thiết kế giao diện
│   ├── script.js               # Logic frontend
│   └── images/                 # Hình ảnh slider
│
├── backend/                     # Server Flask
│   ├── app.py                  # ⭐ Flask server chính
│   ├── external_api.py         # API nhận diện ảnh
│   ├── db_queries.py           # Truy vấn database
│   ├── food_translator.py      # Dịch tên món ăn
│   ├── unicode_utils.py        # Xử lý tiếng Việt
│   └── ai_generator.py         # AI generator (optional)
│
├── food_recognition.db          # Database SQLite (67 món)
├── schema.sql                   # Cấu trúc database
├── .env                         # API keys (không commit)
├── .env.example                 # Mẫu file .env
├── requirements.txt             # Dependencies
├── README.md                    # File này
├── DOCS.md                      # Tài liệu chi tiết
└── PROJECT_STRUCTURE.md         # Cấu trúc dự án
```

## 🚀 Cài Đặt Nhanh

### 1. Clone Repository
```bash
cd d:\KLTN
```

### 2. Cài Đặt Dependencies
```bash
pip install -r requirements.txt
```

### 3. Cấu Hình API Keys
Tạo file `.env` từ `.env.example`:
```bash
copy .env.example .env
```

Thêm API keys vào `.env`:
```
SPOONACULAR_API_KEY=your_key_here
GOOGLE_VISION_API_KEY=your_key_here
```

### 4. Khởi Động Server
```bash
python backend/app.py
```

### 5. Truy Cập Ứng Dụng
Mở trình duyệt: **http://localhost:5000**

## 📊 Database

Database hiện có **67 món ăn** với thông tin đầy đủ:
- Món Việt Nam: Phở, Bánh Mì, Bún Chả, Cơm Tấm...
- Món Trung Quốc: Mì Xào, Cơm Chiên, Há Cảo...
- Món Nhật Bản: Sushi, Ramen, Tempura...
- Món Hàn Quốc: Kim Chi, Bibimbap...
- Món Tây: Pizza, Burger, Pasta...

Mỗi món có:
- ✅ Mô tả chi tiết (5 dòng)
- ✅ Hướng dẫn nấu (5 bước)
- ✅ Nguyên liệu đầy đủ với số lượng
- ✅ Thông tin dinh dưỡng
- ✅ Thời gian nấu & khẩu phần

## 🎯 Luồng Hoạt Động

1. **Upload ảnh** → Frontend gửi đến `/predict`
2. **Nhận diện** → Spoonacular API (fallback: Imagga, Open Food Facts)
3. **Dịch tên** → Tiếng Anh → Tiếng Việt
4. **Tìm kiếm** → Database với normalized search
5. **Tự động thêm** → Nếu không có, lấy từ API và thêm vào DB
6. **Hiển thị** → Kết quả với accordion UI

## 🛠️ Công Nghệ

| Thành phần | Công nghệ |
|-----------|-----------|
| Frontend | HTML5, CSS3, JavaScript (Vanilla) |
| Backend | Python 3.12, Flask, Flask-CORS |
| Database | SQLite |
| AI/API | Spoonacular, Imagga, Open Food Facts |
| Authentication | Session-based |
| UI Design | Light theme, Glassmorphism, Accordion |

## 📖 Tài Liệu

- **README.md** (file này) - Hướng dẫn cài đặt và sử dụng
- **DOCS.md** - Tài liệu chi tiết về API, database, features
- **PROJECT_STRUCTURE.md** - Cấu trúc dự án chi tiết

## 🔐 Tài Khoản Demo

**Admin:**
- Email: admin@smartfood.com
- Password: admin123

**User:**
- Đăng ký tài khoản mới trên giao diện

## ⚠️ Lưu Ý

1. **API Keys**: Cần có API keys hợp lệ trong file `.env`
2. **Port**: Server chạy trên port 5000
3. **Database**: File `food_recognition.db` phải có trong thư mục gốc
4. **Browser**: Khuyến nghị Chrome hoặc Edge (phiên bản mới)

## 🐛 Troubleshooting

### Server không khởi động
```bash
# Kiểm tra port 5000 có bị chiếm không
netstat -ano | findstr :5000

# Kill process nếu cần
taskkill /PID <PID> /F
```

### API timeout
- Kiểm tra kết nối internet
- Thử upload ảnh khác
- Sử dụng Demo Mode (nút Phở, Bánh Mì, Bún Chả)

### Không nhận diện được
- Kiểm tra API keys trong `.env`
- Xem console log của backend
- Thử với ảnh rõ nét hơn

## 📝 License

MIT License - Tự do sử dụng cho mục đích học tập và nghiên cứu.

## 👥 Contributors

- Sinh viên KLTN - Đại học XYZ

---

**Phiên bản:** 2.0  
**Cập nhật:** 15/04/2026