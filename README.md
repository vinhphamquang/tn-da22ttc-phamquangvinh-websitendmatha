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

# 🍜 Smart Food Analysis - Hệ Thống Nhận Diện Món Ăn Bằng Trí Tuệ Nhân Tạo

**Smart Food Analysis** là đồ án/khóa luận xây dựng một ứng dụng Web thông minh tích hợp Trí tuệ Nhân tạo (AI) để giải quyết các bài toán về nhận diện hình ảnh món ăn, phân tích dinh dưỡng và hỗ trợ lên thực đơn ăn uống khoa học.

---

## 🎯 1. Mục Tiêu Đồ Án

Đề tài được phát triển với các mục tiêu cốt lõi:
- **Nhận diện nhanh chóng:** Cho phép người dùng tải lên hoặc chụp ảnh món ăn và nhận về kết quả tên món ăn chính xác (đặc biệt hỗ trợ mạnh mẽ các món ăn Việt Nam).
- **Phân tích dinh dưỡng:** Cung cấp thông tin chi tiết về lượng Calories, và các chỉ số Macros (Protein, Carbohydrate, Chất béo) để giúp người dùng kiểm soát chế độ ăn (giảm cân, tăng cân, giữ dáng).
- **Hỗ trợ thực hành nấu nướng:** Đóng vai trò như một cẩm nang nấu ăn, tự động cung cấp danh sách nguyên liệu và hướng dẫn các bước thực hiện chi tiết cho món ăn vừa nhận diện.
- **Theo dõi sức khỏe:** Tính toán chỉ số cơ thể (BMI), lưu trữ lịch sử nhận diện và đánh giá kế hoạch tiêu thụ năng lượng hàng ngày của người dùng.

---

## 🏗️ 2. Kiến Trúc Hệ Thống

Hệ thống được thiết kế theo mô hình **Client - Server (Frontend - Backend)** kết hợp tích hợp với các hệ thống AI đám mây (Cloud AI APIs).

### Luồng Xử Lý (Workflow):
1. **Client (Trình duyệt):** Người dùng chụp ảnh món ăn và gửi yêu cầu (HTTP POST) lên máy chủ.
2. **Backend (Flask Server):** Tiếp nhận hình ảnh và gửi prompt đến Google Gemini API để bóc tách thông tin. 
3. **Xử lý Dữ liệu:** Kết quả JSON từ AI được dịch thuật, chuẩn hóa tiếng Việt và kiểm tra chéo với SQLite Database. Nếu đây là món ăn mới, hệ thống tự động lưu lại để tăng tốc độ cho các lần quét sau.
4. **Response:** Dữ liệu hoàn chỉnh được trả về để Frontend hiển thị trên giao diện đồ họa.

### Cấu Trúc Thư Mục:
```text
KLTN/
├── frontend/                    # Giao diện người dùng (Client)
│   ├── index.html, admin.html   # Các trang giao diện (SPA)
│   ├── style.css, nutrition.css # File định dạng giao diện
│   └── script.js, transitions.js# Xử lý logic Frontend
│
├── backend/                     # Máy chủ xử lý (Server)
│   ├── app.py                   # Điểm vào chính của Flask App
│   ├── db_queries.py            # Quản lý tương tác Cơ sở dữ liệu
│   ├── external_api.py          # Kết nối APIs bên ngoài (Vision, Spoonacular)
│   └── food_translator.py       # Module xử lý & chuẩn hóa tiếng Việt
│
├── food_recognition.db          # Cơ sở dữ liệu SQLite
├── requirements.txt             # Danh sách thư viện Python
└── .env                         # Các biến môi trường & API Keys bảo mật
```

---

## ⚙️ 3. Các Phần Mềm Cần Thiết Để Triển Khai

Để chạy được dự án trên máy tính cục bộ (Local environment), bạn cần cài đặt các công cụ sau:

1. **Python:** Phiên bản `3.10` hoặc `3.12` trở lên. ([Tải Python](https://www.python.org/downloads/))
2. **Git:** Dùng để clone mã nguồn từ kho lưu trữ. ([Tải Git](https://git-scm.com/))
3. **Trình duyệt Web hiện đại:** Google Chrome, Microsoft Edge, hoặc Safari.
4. **Tài khoản cung cấp API (Bắt buộc):**
   - **Google Gemini API Key:** Phục vụ cho AI sinh văn bản và phân tích ảnh chính.
   - *(Tùy chọn)* Google Cloud Vision / Spoonacular API Key cho mục đích dự phòng.

---

## 🚀 4. Cách Thức Chạy Chương Trình

Dưới đây là các bước chi tiết để khởi chạy ứng dụng từ mã nguồn:

### Bước 1: Clone Repository
Mở Terminal / Command Prompt và chạy lệnh:
```bash
git clone <https://github.com/vinhphamquang/Khoa_Luan_TN.git>
cd KLTN
```

### Bước 2: Thiết lập môi trường ảo (Khuyến nghị)
Tạo và kích hoạt môi trường ảo để không ảnh hưởng đến các dự án khác:
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Bước 3: Cài đặt các thư viện phụ thuộc
Hệ thống sử dụng Flask và các thư viện hỗ trợ (Google Generative AI, JWT, Flask-CORS,...). Cài đặt tất cả qua lệnh:
```bash
pip install -r requirements.txt
```

### Bước 4: Cấu hình biến môi trường
Tạo một file có tên `.env` tại thư mục gốc (cùng cấp với thư mục `backend` và `frontend`), sau đó cấu hình các API keys của bạn:

```env
# Mẫu file .env
GEMINI_API_KEY=điền_key_gemini_của_bạn_vào_đây
GOOGLE_VISION_API_KEY=điền_key_vision_của_bạn_vào_đây
SPOONACULAR_API_KEY=điền_key_spoonacular_của_bạn_vào_đây

# JWT Secret Key (có thể gõ chuỗi ngẫu nhiên bất kỳ)
JWT_SECRET=my_super_secret_key_123!
```

### Bước 5: Khởi động Server Backend
Đảm bảo bạn đang đứng ở thư mục gốc `KLTN`, chạy lệnh:
```bash
python backend/app.py
```
*Ghi chú: Nếu hệ thống báo lỗi thiếu Database, hãy chạy thử file `backend/init_database.py` (nếu có) hoặc đảm bảo file `food_recognition.db` đã được đặt đúng chỗ.*

### Bước 6: Trải nghiệm Ứng dụng
Khi Terminal báo dòng chữ `Running on http://127.0.0.1:5000`, hãy mở trình duyệt web và truy cập vào địa chỉ:

👉 **[http://localhost:5000](http://localhost:5000)**

---

## 🔐 5. Tài Khoản Quản Trị (Demo)

Bạn có thể sử dụng tài khoản sau để truy cập vào trang Quản trị (Admin Dashboard) kiểm duyệt phản hồi và sửa lỗi AI:
- **Email:** `admin@smartfood.com`
- **Mật khẩu:** `admin123`

---
*Đồ án Khóa luận Tốt nghiệp - Cập nhật lần cuối: Tháng 06/2026.*