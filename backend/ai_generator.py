import os
import json
import requests
from dotenv import load_dotenv

# Load biến môi trường từ file .env ở thư mục gốc (hoặc thư mục hiện tại)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def generate_food_data_vietnamese(food_name_english: str):
    """
    Sử dụng Gemini REST API để sinh dữ liệu dinh dưỡng, công thức tiếng Việt
    cho một món ăn vừa được nhận diện bằng tiếng Anh.
    Trả về định dạng JSON đã được parse thành dict.
    """
    if not GEMINI_API_KEY:
        print("[Lỗi] Chưa cấu hình GEMINI_API_KEY trong file .env")
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    Hệ thống AI nhận diện hình ảnh món ăn trả về tên tiếng Anh là: "{food_name_english}".
    Món ăn này có thể là món Tây, Á, hoặc Việt Nam (nếu từ tiếng Việt không dấu, ví dụ bun bo hue).
    
    Hãy đóng vai một chuyên gia dinh dưỡng và đầu bếp chuyên nghiệp, cung cấp thông tin chi tiết BẰNG TIẾNG VIỆT về món ăn này theo đúng cấu trúc JSON sau đây. Không trả lời thêm bất kỳ câu nào khác, chỉ trả về JSON hợp lệ.
    
    Cấu trúc JSON bắt buộc:
    {{
        "TenMonAn": "Tên tiếng Việt hoặc tên phổ biến ở VN của món ăn",
        "MoTa": "Mô tả ngắn gọn, hấp dẫn về điểm đặc trưng của món ăn (khoảng 2-3 câu)",
        "PhanLoai": "Ví dụ: Món nước, Món nướng, Món ăn vặt, Món tráng miệng, Khai vị, Món Tây...",
        "DinhDuong": {{
            "Calo": 500,
            "Protein": 25.5,
            "ChatBeo": 15.0,
            "Carbohydrate": 45.0,
            "Vitamin": "Ví dụ: Vitamin A, B6, Sắt"
        }},
        "CongThuc": {{
            "HuongDan": "Hướng dẫn các bước nấu tóm tắt thành 1 đoạn văn liên tục nhưng rõ ràng từng khâu.",
            "ThoiGianNau": 45,
            "KhauPhan": 2,
            "NguyenLieu": [
                {{"TenNguyenLieu": "Thịt bò", "SoLuong": "500g"}},
                {{"TenNguyenLieu": "Hành tây", "SoLuong": "1 củ"}}
            ]
        }}
    }}
    """
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            try:
                text_response = data['candidates'][0]['content']['parts'][0]['text'].strip()
                
                # Bỏ markdown block nếu AI trả về kèm theo ```json ... ```
                if text_response.startswith("```"):
                    text_response = text_response.split("```")[1]
                    if text_response.startswith("json"):
                        text_response = text_response[4:]
                    text_response = text_response.strip()
                    
                data_dict = json.loads(text_response)
                return data_dict
            except Exception as e:
                print(f"[JSON Parse Error] Lỗi khi đọc kết quả từ AI: {e}")
        else:
            print(f"[Gemini API Error] {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"[Network Error] {e}")

    # --- FALLBACK TO SPOONACULAR IF GEMINI FAILS ---
    print("[INFO] Trying Spoonacular as fallback...")
    try:
        from external_api import get_food_info_from_spoonacular
        sp_data = get_food_info_from_spoonacular(food_name_english)
        if sp_data:
            # Spoonacular trả về tiếng Anh → dùng Gemini để dịch sang tiếng Việt
            translated = _translate_spoonacular_to_vietnamese(food_name_english, sp_data)
            if translated:
                return translated
            
            # Nếu không dịch được, vẫn trả về bản gốc với tên tiếng Việt
            data_dict = {
                "TenMonAn": food_name_english.replace("_", " ").title(),
                "MoTa": sp_data.get("description", f"Món ăn {food_name_english}"),
                "PhanLoai": sp_data.get("category", "Món ăn"),
                "DinhDuong": {
                    "Calo": sp_data.get("calories", 0),
                    "Protein": sp_data.get("protein", 0),
                    "ChatBeo": sp_data.get("fat", 0),
                    "Carbohydrate": sp_data.get("carbs", 0),
                    "Vitamin": sp_data.get("vitamins", "")
                },
                "CongThuc": {
                    "HuongDan": sp_data.get("instructions", "Chưa có hướng dẫn"),
                    "ThoiGianNau": sp_data.get("cooking_time", 30),
                    "KhauPhan": sp_data.get("servings", 1),
                    "NguyenLieu": sp_data.get("ingredients", [])
                }
            }
            return data_dict
    except Exception as fallback_err:
        print(f"[Fallback Error] Spoonacular failed too: {fallback_err}")
        
    return None


def _translate_spoonacular_to_vietnamese(food_name_english: str, sp_data: dict):
    """
    Dùng Gemini để dịch dữ liệu Spoonacular (tiếng Anh) sang tiếng Việt.
    Giữ nguyên số liệu dinh dưỡng, chỉ dịch text.
    """
    if not GEMINI_API_KEY:
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    # Lấy thông tin cần dịch
    description = sp_data.get("description", "")
    instructions = sp_data.get("instructions", "")
    category = sp_data.get("category", "")
    ingredients_list = sp_data.get("ingredients", [])
    ingredients_text = ", ".join([ing.get("TenNguyenLieu", "") for ing in ingredients_list])
    
    prompt = f"""Dịch thông tin món ăn "{food_name_english}" từ tiếng Anh sang tiếng Việt.
Trả về JSON hợp lệ, KHÔNG có markdown, KHÔNG giải thích thêm.

Thông tin gốc (tiếng Anh):
- Description: {description[:300]}
- Category: {category}
- Instructions: {instructions[:500]}
- Ingredients: {ingredients_text[:300]}

Trả về JSON theo cấu trúc:
{{
    "TenMonAn": "Tên tiếng Việt phổ biến của món ăn",
    "MoTa": "Mô tả ngắn gọn bằng tiếng Việt (2-3 câu)",
    "PhanLoai": "Phân loại bằng tiếng Việt (VD: Món nước, Món xào, Tráng miệng...)",
    "HuongDan": "Hướng dẫn nấu bằng tiếng Việt",
    "NguyenLieu": [
        {{"TenNguyenLieu": "Tên nguyên liệu tiếng Việt", "SoLuong": "số lượng"}}
    ]
}}"""
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            data = response.json()
            text_response = data['candidates'][0]['content']['parts'][0]['text'].strip()
            
            if text_response.startswith("```"):
                text_response = text_response.split("```")[1]
                if text_response.startswith("json"):
                    text_response = text_response[4:]
                text_response = text_response.strip()
            
            translated = json.loads(text_response)
            
            # Kết hợp dữ liệu dịch với số liệu dinh dưỡng gốc (giữ nguyên số)
            result = {
                "TenMonAn": translated.get("TenMonAn", food_name_english.replace("_", " ").title()),
                "MoTa": translated.get("MoTa", description),
                "PhanLoai": translated.get("PhanLoai", category),
                "DinhDuong": {
                    "Calo": sp_data.get("calories", 0),
                    "Protein": sp_data.get("protein", 0),
                    "ChatBeo": sp_data.get("fat", 0),
                    "Carbohydrate": sp_data.get("carbs", 0),
                    "Vitamin": sp_data.get("vitamins", "")
                },
                "CongThuc": {
                    "HuongDan": translated.get("HuongDan", instructions),
                    "ThoiGianNau": sp_data.get("cooking_time", 30),
                    "KhauPhan": sp_data.get("servings", 1),
                    "NguyenLieu": translated.get("NguyenLieu", sp_data.get("ingredients", []))
                }
            }
            
            print(f"[SUCCESS] Đã dịch dữ liệu Spoonacular sang tiếng Việt: {result['TenMonAn']}")
            return result
    except Exception as e:
        print(f"[TRANSLATE ERROR] Không thể dịch dữ liệu Spoonacular: {e}")
    
    return None

if __name__ == "__main__":
    res = generate_food_data_vietnamese("salad")
    print(json.dumps(res, indent=2, ensure_ascii=False))
