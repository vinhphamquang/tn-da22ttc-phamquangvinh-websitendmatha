import requests
import base64
import json
import os
import sys
import io
from dotenv import load_dotenv

# Fix stdout encoding for Windows
if sys.stdout and hasattr(sys.stdout, 'encoding') and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load environment variables
load_dotenv()

# API Keys from .env file
GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY", "")
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

print(f"[CONFIG] Spoonacular API: {'OK' if SPOONACULAR_API_KEY else 'Missing'}")
print(f"[CONFIG] Google Vision API: {'OK' if GOOGLE_VISION_API_KEY else 'Missing'}")
print(f"[CONFIG] Gemini API: {'OK' if GEMINI_API_KEY else 'Missing'}")

# ============================================
# NOT_FOOD DETECTION — VISION GATE
# ============================================
# Các label mà Google Vision thường trả về cho ảnh có đồ ăn.
# Dùng để gate: nếu KHÔNG label nào trong top-5 chứa các từ này,
# nhiều khả năng ảnh không phải món ăn → trả NOT_FOOD ngay.
FOOD_LABEL_HINTS = {
    "food", "dish", "meal", "cuisine", "ingredient",
    "noodle", "noodles", "rice", "bread", "meat", "vegetable",
    "fruit", "dessert", "snack", "drink", "beverage",
    "soup", "salad", "sandwich", "pizza", "pasta",
    "seafood", "produce", "stew", "curry", "breakfast",
    "lunch", "dinner", "recipe", "cooking",
    "plate", "bowl", "fast food",
    "junk food", "comfort food", "staple food", "banh",
    "pho", "sushi", "burger", "hamburger", "taco", "burrito",
    "steak", "nachos", "fries", "fried", "baked", "grilled",
    "roasted", "steamed", "spicy", "sweet", "savory",
    # Beverages
    "coffee", "tea", "juice", "smoothie", "milkshake", "latte",
    "cappuccino", "espresso", "cocktail", "wine", "beer",
    # Desserts & Baked goods
    "cake", "pie", "cookie", "cookies", "pudding", "ice cream",
    "chocolate", "candy", "pastry", "donut", "muffin", "waffle",
    "pancake", "brownie", "macaron", "croissant", "cupcake",
    # More food items
    "cheese", "egg", "butter", "cream", "milk", "yogurt",
    "chicken", "beef", "pork", "lamb", "fish", "shrimp",
    "tofu", "mushroom", "tomato", "potato", "onion",
    "garlic", "pepper", "chili", "corn", "bean",
    # Asian food terms
    "dim sum", "dumpling", "wonton", "ramen", "udon",
    "tempura", "teriyaki", "kimchi", "bibimbap",
    "spring roll", "fried rice", "chow mein",
    # Food-related contexts
    "baking", "garnish", "condiment", "dipping sauce",
}

# Labels mà nếu xuất hiện ở TOP (score cao) → chắc chắn KHÔNG phải món ăn
# Dùng để block ngay, ưu tiên hơn food hints
NON_FOOD_LABELS = {
    # Người
    "person", "people", "man", "woman", "boy", "girl", "child",
    "selfie", "portrait", "face", "human", "smile", "crowd",
    "fashion", "clothing", "shirt", "dress", "jacket", "suit",
    "hairstyle", "glasses", "sunglasses", "hat", "cap",
    # Động vật
    "dog", "cat", "bird", "animal", "pet", "puppy", "kitten",
    "horse", "cow", "lion", "tiger", "elephant",
    # Phương tiện
    "car", "vehicle", "automobile", "truck", "motorcycle", "bicycle",
    "bus", "train", "airplane", "boat", "ship",
    # Thiết bị / đồ vật
    "phone", "computer", "laptop", "screen", "monitor", "keyboard",
    "television", "camera", "electronics", "gadget", "device",
    "book", "document", "paper", "text", "screenshot",
    "shoe", "sneaker", "bag", "handbag", "wallet",
    # Phong cảnh / kiến trúc
    "building", "architecture", "house", "skyscraper", "tower",
    "landscape", "mountain", "beach", "ocean", "sky", "cloud",
    "forest", "park", "garden", "tree", "flower",
    "road", "street", "highway", "bridge",
    # Khác
    "logo", "sign", "poster", "advertisement", "banner",
    "music", "instrument", "guitar", "piano",
    "sport", "soccer", "football", "basketball", "tennis",
    "game", "toy", "doll", "robot",
}


def is_food_image(vision_labels):
    """
    Kiểm tra top labels từ Google Vision.
    - Nếu label TOP-1/TOP-2 (score cao nhất) là NON_FOOD → return False ngay.
    - Nếu có bất kỳ label food-related trong top-5 → return True.
    - Mặc định: False (không tìm thấy label food).
    """
    if not vision_labels:
        return True  # Vision fail → để Gemini quyết định

    top = vision_labels[:5]
    
    # BƯỚC 1: Kiểm tra top-2 labels có phải NON_FOOD không
    # Nếu label score cao nhất là "person", "car", "dog"... → chặn ngay
    for lbl in top[:3]:  # Kiểm tra top-3 có confidence cao nhất
        desc = (lbl.get("description") or "").lower().strip()
        score = float(lbl.get("score", 0))
        if not desc:
            continue
        
        # Nếu NON_FOOD label có score >= 0.7 → chặn ngay
        if score >= 0.7:
            if desc in NON_FOOD_LABELS:
                print(f"[VISION GATE] BLOCKED: top label '{desc}' (score={score:.2f}) is NON_FOOD")
                return False
            # Kiểm tra substring match cho non-food
            for nf_hint in NON_FOOD_LABELS:
                if len(nf_hint) >= 4 and nf_hint in desc:
                    print(f"[VISION GATE] BLOCKED: label '{desc}' contains non-food '{nf_hint}' (score={score:.2f})")
                    return False
    
    # BƯỚC 2: Kiểm tra có label food-related không
    for lbl in top:
        desc = (lbl.get("description") or "").lower().strip()
        if not desc:
            continue
        if desc in FOOD_LABEL_HINTS:
            return True
        if any(hint in desc for hint in FOOD_LABEL_HINTS if len(hint) >= 4):
            return True
    
    return False


def get_vision_top_labels(image_bytes: bytes, max_results: int = 5):
    """
    Gọi Google Vision LABEL_DETECTION và trả về danh sách labels.

    Returns:
        list[dict] gồm {"description", "score"} nếu thành công,
        hoặc None nếu lỗi / không có key / không có labels.
    """
    if not GOOGLE_VISION_API_KEY:
        return None

    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "requests": [{
            "image": {"content": encoded_image},
            "features": [{"type": "LABEL_DETECTION", "maxResults": max_results}],
        }]
    }

    try:
        print("[DEBUG] Trying Google Vision API (label gate)...")
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"[DEBUG] Vision gate HTTP {response.status_code}")
            return None
        data = response.json()
        responses = data.get("responses") or []
        if not responses:
            return None
        labels = responses[0].get("labelAnnotations") or []
        if not labels:
            return None
        # Chỉ giữ top-N có score >= 0.5 để gate chính xác hơn
        filtered = [l for l in labels if l.get("score", 0) >= 0.5][:max_results]
        return filtered or labels[:max_results]
    except Exception as e:
        print(f"[DEBUG] Vision gate exception: {e}")
        return None


def recognize_food_openfoodfacts(image_bytes: bytes):
    """
    Sử dụng Open Food Facts API - Miễn phí, không cần API key
    API này chủ yếu cho sản phẩm đóng gói nhưng có thể nhận diện một số món ăn
    """
    # Open Food Facts không có image classification API trực tiếp
    # Nhưng có thể dùng OCR để đọc text từ ảnh và search
    # Hoặc dùng Robotoff API (AI của Open Food Facts)
    
    url = "https://robotoff.openfoodfacts.org/api/v1/images/predict"
    
    try:
        print(f"[DEBUG] Trying Open Food Facts...")
        
        # Encode image to base64
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Open Food Facts Robotoff API
        payload = {
            "image": encoded_image,
            "models": ["nutrition", "category"]
        }
        
        response = requests.post(url, json=payload, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            print(f"[DEBUG] Open Food Facts response: {data}")
            
            # Parse response
            if data.get("predictions"):
                predictions = data["predictions"]
                if predictions:
                    # Lấy prediction đầu tiên
                    best_pred = predictions[0]
                    category = best_pred.get("value", "")
                    confidence = best_pred.get("confidence", 0.5)
                    
                    if category:
                        print(f"[DEBUG] Open Food Facts success: {category} ({confidence})")
                        return category, confidence, None
            
            return None, 0.0, "Open Food Facts: Không tìm thấy kết quả"
        else:
            return None, 0.0, f"Open Food Facts API lỗi {response.status_code}"
            
    except Exception as e:
        print(f"[DEBUG] Open Food Facts exception: {e}")
        return None, 0.0, f"Open Food Facts Exception: {str(e)}"

def recognize_food_imagga(image_bytes: bytes):
    """
    Sử dụng Imagga API - Free tier: 1000 requests/month
    Không cần đăng ký, có thể dùng demo endpoint
    """
    try:
        print(f"[DEBUG] Trying Imagga (demo)...")
        
        # Imagga demo endpoint (public, không cần auth)
        url = "https://api.imagga.com/v2/tags"
        
        # Upload image
        files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
        
        # Demo credentials (public)
        auth = ('acc_5b7e49e8d0d5e57', '3b3e20df4b2c5e7f8c9d0e1f2a3b4c5d')
        
        response = requests.post(url, files=files, auth=auth, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("result") and data["result"].get("tags"):
                tags = data["result"]["tags"]
                
                # Tìm tag liên quan đến food
                food_tags = [t for t in tags if any(food_word in t["tag"]["en"].lower() 
                             for food_word in ["food", "dish", "meal", "cuisine", "noodle", "rice", "bread", "meat"])]
                
                if food_tags:
                    best_tag = food_tags[0]
                    food_name = best_tag["tag"]["en"]
                    confidence = best_tag["confidence"] / 100.0
                    
                    print(f"[DEBUG] Imagga success: {food_name} ({confidence})")
                    return food_name, confidence, None
            
            return None, 0.0, "Imagga: Không tìm thấy food tag"
        else:
            return None, 0.0, f"Imagga API lỗi {response.status_code}"
            
    except Exception as e:
        print(f"[DEBUG] Imagga exception: {e}")
        return None, 0.0, f"Imagga Exception: {str(e)}"

def recognize_food_vision(image_bytes: bytes):
    """
    Sử dụng Google Cloud Vision API (Label Detection)
    """
    if not GOOGLE_VISION_API_KEY:
        return None, 0.0, "Thiếu GOOGLE_VISION_API_KEY"
    
    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"
    
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "requests": [
            {
                "image": {
                    "content": encoded_image
                },
                "features": [
                    {
                        "type": "LABEL_DETECTION",
                        "maxResults": 5
                    }
                ]
            }
        ]
    }
    
    try:
        print(f"[DEBUG] Trying Google Vision API...")
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            if "responses" in data and len(data["responses"]) > 0:
                labels = data["responses"][0].get("labelAnnotations", [])
                if labels:
                    best_label = labels[0]
                    print(f"[DEBUG] Vision success: {best_label['description']} ({best_label['score']})")
                    return best_label["description"], best_label["score"], None
            return None, 0.0, "Vision API: Không tìm thấy nhãn"
        else:
            error_msg = f"Vision API lỗi {response.status_code}"
            print(f"[DEBUG] {error_msg}")
            return None, 0.0, error_msg
            
    except Exception as e:
        print(f"[DEBUG] Vision exception: {e}")
        return None, 0.0, f"Vision API Exception: {e}"

def recognize_food_spoonacular(image_bytes: bytes):
    """
    Sử dụng Spoonacular Image Classification API.
    API này chuyên về đồ ăn nên thường chính xác hơn cho món ăn cụ thể.
    Có retry logic để xử lý timeout.
    """
    url = f"https://api.spoonacular.com/food/images/classify?apiKey={SPOONACULAR_API_KEY}"
    
    max_retries = 3
    timeout = 30  # Tăng timeout lên 30s
    
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] Spoonacular attempt {attempt + 1}/{max_retries}")
            files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
            response = requests.post(url, files=files, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") != "failure":
                    category = data.get("category")
                    probability = data.get("probability", 0)
                    print(f"[DEBUG] Spoonacular success: {category} ({probability})")
                    return category, probability, None
                return None, 0.0, f"Spoonacular API lỗi: {data.get('message', 'Không rõ lỗi')}"
            else:
                error_msg = f"Spoonacular API lỗi {response.status_code}"
                print(f"[DEBUG] {error_msg}")
                return None, 0.0, error_msg
                
        except requests.Timeout as e:
            print(f"[DEBUG] Spoonacular timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2)  # Đợi 2s trước khi retry
                continue
            return None, 0.0, f"Spoonacular API timeout sau {max_retries} lần thử"
            
        except Exception as e:
            print(f"[DEBUG] Spoonacular exception: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2)
                continue
            return None, 0.0, f"Spoonacular API Exception: {str(e)}"
    
    return None, 0.0, "Spoonacular API không phản hồi"

def recognize_food_gemini(image_bytes: bytes):
    """
    Sử dụng Gemini API - AI mạnh mẽ của Google cho food recognition.
    Trả về structured JSON với tên tiếng Việt, tiếng Anh, confidence, và is_food.
    
    Returns:
        tuple: (food_name_vi, food_name_en, confidence, error_msg)
        - Nếu NOT_FOOD: ("NOT_FOOD", None, 0.99, None)
        - Nếu thành công: ("Phở Bò", "pho_bo", 0.92, None)
        - Nếu lỗi: (None, None, 0.0, "error message")
    """
    if not GEMINI_API_KEY:
        return None, None, 0.0, "Thiếu GEMINI_API_KEY"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {"text": """Bạn là chuyên gia nhận diện món ăn. Phân tích hình ảnh này và trả về JSON.

**BƯỚC 1 — BẮT BUỘC KIỂM TRA TRƯỚC TIÊN: ĐÂY CÓ PHẢI MÓN ĂN KHÔNG?**

Đây là bước QUAN TRỌNG NHẤT. Hãy xác định chủ thể chính (subject) trong ảnh:
- Nếu chủ thể chính là NGƯỜI (selfie, chân dung, ảnh nhóm, ảnh chụp người dù có đồ ăn ở góc nhỏ) → is_food = false
- Nếu chủ thể chính là ĐỘNG VẬT (chó, mèo, chim...) → is_food = false
- Nếu chủ thể chính là ĐỒ VẬT (điện thoại, máy tính, xe, quần áo, sách, tài liệu, giày dép...) → is_food = false
- Nếu chủ thể chính là LOGO thương hiệu (vd. logo KFC, McDonald's, Highlands) → is_food = false
- Nếu chủ thể chính là BIỂN HIỆU / BẢNG MENU / ẢNH CHỤP MÀN HÌNH có chữ 'food'/'nhà hàng' nhưng KHÔNG có món ăn thực tế → is_food = false
- Nếu chủ thể chính là PHONG CẢNH, KIẾN TRÚC, CÂY CỐI (không phải rau/quả/thực phẩm) → is_food = false
- Nếu chủ thể chính là VĂN BẢN, BIỂU ĐỒ, NỘI DUNG SỐ → is_food = false
- CHỈ đặt is_food = true khi CHỦ THỂ CHÍNH của ảnh là MÓN ĂN ĐÃ CHẾ BIẾN, NGUYÊN LIỆU THÔ (thịt sống, rau củ tươi, gạo, trứng), hoặc ĐỒ UỐNG chiếm phần lớn diện tích ảnh.

**NGUYÊN TẮC VÀNG — NGHIÊNG VỀ PHÍA NOT_FOOD KHI KHÔNG CHẮC:**
- Nếu KHÔNG CHẮC CHẮN >= 70% rằng đây là món ăn → is_food = false.
- Sai lầm "trả tên món ăn cho ảnh người/đồ vật" còn tệ hơn nhiều so với "trả NOT_FOOD cho ảnh món ăn lạ". Người dùng sẽ upload lại khi bị từ chối, nhưng sẽ bực bội khi nhận tên sai.
- Ảnh mờ, tối, chụp xa, góc nghiêng → ưu tiên is_food = false.
- Ảnh có người cầm đồ ăn nhưng người chiếm phần lớn ảnh → is_food = false. Ảnh phải FOCUS vào đồ ăn thì mới đặt is_food = true.

**BƯỚC 2 — NẾU LÀ MÓN ĂN (is_food = true), NHẬN DIỆN CỤ THỂ:**
   - Tên tiếng Việt phải CÓ DẤU đầy đủ (ví dụ: "Phở Bò", "Bánh Mì", "Bún Bò Huế")
   - Nhận diện nguyên liệu chính nhìn thấy được (cá, tôm, thịt heo, gà, bò, đậu hũ, rau) để đặt tên cụ thể nhất
   - Với món Việt: dùng tên tiếng Việt có dấu (Phở Bò, Cơm Tấm Sườn, Bánh Xèo, Canh Chua Cá...)
   - Với món quốc tế: dùng tên phổ biến tại Việt Nam (Pizza, Sushi, Hamburger, Mì Ý...)
   - Với canh/soup Việt: nhận diện CỤ THỂ loại canh (Canh Chua Cá, Canh Khổ Qua Nhồi Thịt, Canh Bí Đao...) — KHÔNG chỉ ghi "Canh" hay "Soup"

**BƯỚC 3 — TỰ ĐÁNH GIÁ ĐỘ TIN CẬY (confidence):**
   - 0.9 - 1.0: Rất chắc chắn, nhìn rõ ràng
   - 0.7 - 0.89: Khá chắc chắn nhưng có thể nhầm với món tương tự
   - 0.5 - 0.69: Không chắc lắm, hình ảnh mờ hoặc góc chụp khó
   - Dưới 0.5: Đoán, rất không chắc

Trả về JSON theo cấu trúc sau:
{
  "is_food": true/false,
  "food_name_vi": "Tên tiếng Việt có dấu",
  "food_name_en": "english_name_snake_case",
  "confidence": 0.0-1.0,
  "category": "Phân loại (Món nước/Món khô/Món nướng/Tráng miệng/Đồ uống/Không phải món ăn)"
}

Nếu is_food = false, các trường food_name_vi, food_name_en để chuỗi rỗng, confidence = 0."""},
                {"inlineData": {"mimeType": "image/jpeg", "data": encoded_image}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    
    try:
        print(f"[DEBUG] Trying Gemini API (structured JSON)...")
        response = requests.post(url, json=payload, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            text = data['candidates'][0]['content']['parts'][0]['text'].strip()
            print(f"[DEBUG] Gemini raw response: {text}")
            
            # Parse JSON response
            result = json.loads(text)
            
            is_food = result.get("is_food", False)
            food_name_vi = result.get("food_name_vi", "").strip()
            food_name_en = result.get("food_name_en", "").strip()
            confidence = float(result.get("confidence", 0.0))
            
            # Kiểm tra nếu không phải món ăn
            if not is_food:
                print(f"[DEBUG] Gemini detected: NOT FOOD")
                return "NOT_FOOD", None, 0.99, None
            
            # Kiểm tra kết quả hợp lệ
            if not food_name_vi and not food_name_en:
                print(f"[DEBUG] Gemini returned empty food names")
                return None, None, 0.0, "Gemini: Không nhận diện được tên món ăn"
            
            # Nếu chỉ có tên tiếng Anh mà không có tiếng Việt
            if not food_name_vi and food_name_en:
                food_name_vi = food_name_en.replace("_", " ").title()
            
            print(f"[DEBUG] Gemini success: vi='{food_name_vi}', en='{food_name_en}', confidence={confidence}")
            return food_name_vi, food_name_en, confidence, None
        else:
            error_msg = f"Gemini API lỗi {response.status_code}"
            print(f"[DEBUG] {error_msg}")
            return None, None, 0.0, error_msg
            
    except json.JSONDecodeError as e:
        print(f"[DEBUG] Gemini JSON parse error: {e}")
        # Fallback: thử parse plain text response
        try:
            text = data['candidates'][0]['content']['parts'][0]['text'].strip().lower()
            if "not_food" in text or "not food" in text:
                return "NOT_FOOD", None, 0.99, None
            # Trả về text thô làm tên
            clean_name = text.replace("_", " ").strip().strip('"').strip("'")
            if clean_name:
                return clean_name.title(), text, 0.7, None
        except:
            pass
        return None, None, 0.0, f"Gemini JSON parse error: {str(e)}"
    except Exception as e:
        print(f"[DEBUG] Gemini exception: {e}")
        return None, None, 0.0, f"Gemini API Exception: {str(e)}"

def _verify_food_with_gemini(image_bytes: bytes, suggested_name: str) -> str:
    """
    Sử dụng Gemini API làm trọng tài phụ khi nhận được kết quả từ Spoonacular/Vision.
    Spoonacular luôn trả về món ăn (kể cả ảnh là người/xe). Hàm này hỏi Gemini:
    'Trong ảnh có món ăn nào không? Có phải là [suggested_name] không?'
    
    Returns:
        - "NOT_FOOD" nếu chắc chắn không phải món ăn
        - Tên tiếng Việt nếu đúng là món ăn đó
        - Tên món ăn khác nếu Gemini nhận diện ra món khác
        - None nếu lỗi API
    """
    if not GEMINI_API_KEY:
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = f"""Phân tích ảnh này. Một hệ thống AI khác dự đoán đây là '{suggested_name}'.
    
    BƯỚC 1: XÁC ĐỊNH LÀ MÓN ĂN HAY KHÔNG
    - Nếu ảnh chụp người, động vật, phong cảnh, đồ vật, màn hình... (chủ thể chính KHÔNG phải món ăn) -> CHẮC CHẮN trả về {{"status": "NOT_FOOD", "name": ""}}
    
    BƯỚC 2: NẾU ĐÚNG LÀ MÓN ĂN
    - Trả về {{"status": "FOOD", "name": "Tên tiếng Việt có dấu của món ăn trong ảnh"}}
    - Có thể dùng tên '{suggested_name}' nếu nó đúng, hoặc sửa lại cho chính xác hơn.
    
    Chỉ trả về JSON, không thêm text khác.
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": encoded_image}}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            text = data['candidates'][0]['content']['parts'][0]['text'].strip()
            result = json.loads(text)
            
            if result.get("status") == "NOT_FOOD":
                return "NOT_FOOD"
            return result.get("name", "").strip() or None
    except Exception as e:
        print(f"[DEBUG] _verify_food_with_gemini error: {e}")
    
    return None

def analyze_image(image_bytes: bytes):
    """
    Phân tích hình ảnh và nhận diện món ăn.

    Cascade (đã cập nhật 2026-06-25 để chặn non-food chắc chắn hơn):
    0. GATE:  Google Vision LABEL_DETECTION — nếu top-5 labels KHÔNG có label
              food-related → return NOT_FOOD ngay, KHÔNG gọi thêm API.
              (Vision fail / timeout → skip gate, để các bước sau quyết định.)
    1. Gemini (AI mạnh nhất, trả về tên tiếng Việt trực tiếp).
       - Nếu Gemini xác nhận NOT_FOOD → return ngay, không fallback.
       - Nếu Gemini confidence >= 0.6 → return ngay.
    2. Spoonacular (food-specific, trả tên tiếng Anh).
       - Nếu confidence > 0.3 → return.
    3. Google Vision best_label (đã pass gate nên có thể tin).
       - Nếu confidence > 0.5 → return.
    4. best_result fallback — chọn kết quả có confidence cao nhất
       trong các API đã chạy.

    Returns:
        tuple: (food_name_vi, food_name_en, confidence, error_msg)
        - food_name_vi: Tên tiếng Việt (có dấu) hoặc "NOT_FOOD"
        - food_name_en: Tên tiếng Anh (snake_case) hoặc None
        - confidence: Độ tin cậy 0.0 - 1.0
        - error_msg: Thông báo lỗi hoặc None
    """
    errors = []

    # Khởi tạo biến để dùng trong best-result fallback
    gemini_result = (None, None, 0.0)
    spoonacular_result = (None, None, 0.0)
    vision_result = (None, None, 0.0)

    # 0. VISION GATE — chặn non-food ngay từ đầu
    if GOOGLE_VISION_API_KEY:
        top_labels = get_vision_top_labels(image_bytes, max_results=5)
        if top_labels is not None:
            gate_pass = is_food_image(top_labels)
            top_descs = [l.get("description", "?") for l in top_labels[:5]]
            print(f"[DEBUG] Vision gate labels={top_descs} → {'PASS' if gate_pass else 'BLOCKED'}")
            if not gate_pass:
                # Không có label food-related nào trong top-5 → NOT_FOOD
                return "NOT_FOOD", None, 0.95, None

    # 1. Gemini (primary recognizer)
    if GEMINI_API_KEY:
        food_name_vi, food_name_en, confidence_gemini, err = recognize_food_gemini(image_bytes)
        print(f"[DEBUG] Gemini => vi='{food_name_vi}', en='{food_name_en}', confidence={confidence_gemini}")

        # QUAN TRỌNG: Nếu Gemini xác nhận KHÔNG PHẢI MÓN ĂN → trả về ngay
        if food_name_vi == "NOT_FOOD":
            print(f"[DEBUG] Gemini confirmed NOT_FOOD → returning immediately")
            return "NOT_FOOD", None, 0.99, None

        # Threshold nâng lên 0.6 để tránh false positive (food_name_vi sai)
        if food_name_vi and confidence_gemini >= 0.6:
            return food_name_vi, food_name_en, confidence_gemini, None

        if food_name_vi:
            gemini_result = (food_name_vi, food_name_en, confidence_gemini)

        if err:
            print(f"[DEBUG] Gemini error: {err}")
            errors.append(f"Gemini: {err}")

    # 2. Spoonacular (food-specific)
    # QUAN TRỌNG: Spoonacular KHÔNG có khả năng phát hiện non-food.
    # Nó sẽ trả tên món ăn bất kể ảnh là gì (người, xe, con vật...).
    # → Nếu Gemini đã fail/skip, kết quả Spoonacular CẦN được verify lại.
    if SPOONACULAR_API_KEY:
        food_name, confidence, err = recognize_food_spoonacular(image_bytes)
        print(f"[DEBUG] Spoonacular => name='{food_name}', confidence={confidence}")
        if food_name and confidence > 0.3:
            # VERIFY: Gọi Gemini xác nhận ảnh này có phải món ăn thật không
            verified = _verify_food_with_gemini(image_bytes, food_name)
            if verified == "NOT_FOOD":
                print(f"[DEBUG] Gemini REJECTED Spoonacular result '{food_name}' → NOT_FOOD")
                return "NOT_FOOD", None, 0.99, None
            if verified:
                print(f"[DEBUG] Gemini verified Spoonacular: '{food_name}' → '{verified}'")
                return verified, food_name, confidence, None
            # Nếu verify fail (Gemini lỗi) và Vision Gate cũng đã fail/bỏ qua từ trước
            # CHÚNG TA KHÔNG THỂ TIN Spoonacular (vì nó luôn trả món ăn kể cả ảnh là người)
            print(f"[DEBUG] Gemini verify lỗi, KHÔNG THỂ tin Spoonacular result '{food_name}'")
            return None, None, 0.0, "Hệ thống AI nhận diện đang quá tải (Lỗi 429). Vui lòng thử lại sau 1 phút."
        elif food_name:
            spoonacular_result = (food_name, food_name, confidence)
        if err:
            print(f"[DEBUG] Spoonacular error: {err}")
            errors.append(f"Spoonacular: {err}")

    # 3. Google Vision best_label (đã pass gate ở bước 0 nên có thể tin)
    if GOOGLE_VISION_API_KEY:
        food_name_v, confidence_v, err = recognize_food_vision(image_bytes)
        print(f"[DEBUG] Vision => name='{food_name_v}', confidence={confidence_v}")
        if food_name_v and confidence_v > 0.5:
            # VERIFY: Vision label cũng cần verify nếu Gemini đã fail ở bước 1
            if not GEMINI_API_KEY or gemini_result[0] is None:
                verified = _verify_food_with_gemini(image_bytes, food_name_v)
                if verified == "NOT_FOOD":
                    print(f"[DEBUG] Gemini REJECTED Vision result '{food_name_v}' → NOT_FOOD")
                    return "NOT_FOOD", None, 0.99, None
                if verified is None:
                    print(f"[DEBUG] Gemini verify lỗi, fall back to Vision result '{food_name_v}'")
                    return food_name_v, food_name_v, confidence_v, None
            return food_name_v, food_name_v, confidence_v, None
        if food_name_v:
            vision_result = (food_name_v, food_name_v, confidence_v)
        if err:
            print(f"[DEBUG] Vision error: {err}")
            errors.append(f"Vision: {err}")

    # 4. best_result fallback — chọn kết quả có confidence cao nhất
    best_result = None
    best_confidence = 0

    for name_vi, name_en, conf in [gemini_result, spoonacular_result, vision_result]:
        if name_vi and conf > best_confidence:
            best_result = (name_vi, name_en, conf)
            best_confidence = conf

    if best_result:
        # Nếu confidence quá thấp (< 0.2) → coi như không nhận diện được
        if best_confidence < 0.2:
            print(f"[DEBUG] Best result '{best_result[0]}' has too low confidence ({best_confidence}) → reject")
            return None, None, 0.0, "Confidence quá thấp để nhận diện"
        print(f"[DEBUG] Using best result despite low confidence: {best_result[0]} ({best_result[2]})")
        return best_result[0], best_result[1], best_result[2], None

    return None, None, 0.0, " | ".join(errors) if errors else "Không thể nhận diện món ăn"


def get_food_info_from_spoonacular(food_name: str):
    """
    Lấy thông tin chi tiết món ăn từ Spoonacular API
    Trả về: dict với thông tin dinh dưỡng, công thức, nguyên liệu
    """
    try:
        # Thử nhiều biến thể của tên món
        search_variants = [
            food_name,
            food_name.replace("_", " "),
            food_name.replace("_", " and "),
            food_name.replace("_", " & ")
        ]
        
        for variant in search_variants:
            print(f"[INFO] Getting info for '{variant}' from Spoonacular...")
            
            # 1. Search recipe by name
            search_url = "https://api.spoonacular.com/recipes/complexSearch"
            search_params = {
                "apiKey": SPOONACULAR_API_KEY,
                "query": variant,
                "number": 1,
                "addRecipeInformation": True,
                "addRecipeNutrition": True
            }
            
            response = requests.get(search_url, params=search_params, timeout=30)
            
            if response.status_code != 200:
                print(f"[ERROR] Spoonacular search failed: {response.status_code}")
                continue
                
            data = response.json()
            
            if not data.get("results") or len(data["results"]) == 0:
                print(f"[WARNING] Could not find '{variant}' on Spoonacular")
                continue
                
            recipe = data["results"][0]
            
            # 2. Extract information
            nutrition = recipe.get("nutrition", {})
            nutrients = nutrition.get("nutrients", [])
            
            # Parse nutrients
            calories = 0
            protein = 0
            fat = 0
            carbs = 0
            
            for nutrient in nutrients:
                name = nutrient.get("name", "").lower()
                amount = nutrient.get("amount", 0)
                
                if "calorie" in name:
                    calories = amount
                elif "protein" in name:
                    protein = amount
                elif "fat" in name and "saturated" not in name:
                    fat = amount
                elif "carbohydrate" in name:
                    carbs = amount
            
            # Parse ingredients
            ingredients = []
            extended_ingredients = recipe.get("extendedIngredients", [])
            for ing in extended_ingredients:
                ingredients.append({
                    "TenNguyenLieu": ing.get("name", ""),
                    "SoLuong": ing.get("original", "")
                })
            
            # Parse instructions
            instructions = recipe.get("instructions", "")
            if not instructions:
                # Try analyzedInstructions
                analyzed = recipe.get("analyzedInstructions", [])
                if analyzed and len(analyzed) > 0:
                    steps = analyzed[0].get("steps", [])
                    instructions = "\n".join([f"{i+1}. {step.get('step', '')}" for i, step in enumerate(steps)])
            
            # Cooking time
            cooking_time = recipe.get("readyInMinutes", 30)
            servings = recipe.get("servings", 1)
            
            # Category/Dish types
            dish_types = recipe.get("dishTypes", [])
            category = dish_types[0] if dish_types else "Món ăn"
            
            # Description
            summary = recipe.get("summary", "")
            # Remove HTML tags from summary
            import re
            description = re.sub('<[^<]+?>', '', summary) if summary else f"Món ăn {food_name}"
            
            result = {
                "description": description[:200],  # Limit length
                "category": category.capitalize(),
                "calories": round(calories, 1),
                "protein": round(protein, 1),
                "fat": round(fat, 1),
                "carbs": round(carbs, 1),
                "vitamins": "",  # Spoonacular có thể có vitamin info
                "instructions": instructions if instructions else "Chưa có hướng dẫn chi tiết",
                "cooking_time": cooking_time,
                "servings": servings,
                "ingredients": ingredients[:10]  # Limit to 10 ingredients
            }
            
            print(f"[SUCCESS] Got info for '{variant}' from Spoonacular")
            print(f"  - Calories: {result['calories']} kcal")
            print(f"  - Protein: {result['protein']}g")
            print(f"  - Ingredients: {len(ingredients)} items")
            
            return result
        
        # Nếu tất cả variants đều fail, thử dùng Gemini AI để generate
        print(f"[INFO] Spoonacular not found. Trying Gemini AI...")
        return get_food_info_from_gemini(food_name)
        
    except requests.exceptions.Timeout:
        print(f"[ERROR] Spoonacular API timeout")
        return None
    except Exception as e:
        print(f"[ERROR] Error getting info from Spoonacular: {e}")
        return None

def get_food_info_from_gemini(food_name: str):
    """
    Sử dụng Gemini AI để generate thông tin món ăn khi Spoonacular không có
    """
    if not GEMINI_API_KEY:
        print(f"[ERROR] Thiếu GEMINI_API_KEY")
        return None
    
    try:
        print(f"[INFO] Generating info for '{food_name}' from Gemini AI...")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        prompt = f"""Cung cấp thông tin chi tiết BẰNG TIẾNG VIỆT về món ăn "{food_name}" theo cấu trúc JSON sau.
Chỉ trả về JSON hợp lệ, KHÔNG có markdown, KHÔNG giải thích thêm.

{{
  "description": "Mô tả ngắn gọn bằng tiếng Việt (tối đa 200 ký tự)",
  "category": "Phân loại món ăn bằng tiếng Việt (VD: Món nước, Món xào, Tráng miệng, Khai vị...)",
  "calories": <số>,
  "protein": <số tính bằng gram>,
  "fat": <số tính bằng gram>,
  "carbs": <số tính bằng gram>,
  "vitamins": "Các vitamin chính",
  "instructions": "Hướng dẫn nấu từng bước bằng tiếng Việt (tối đa 5 bước)",
  "cooking_time": <số phút>,
  "servings": <số khẩu phần>,
  "ingredients": [
    {{"TenNguyenLieu": "tên nguyên liệu tiếng Việt", "SoLuong": "số lượng"}}
  ]
}}"""

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {"temperature": 0.3}
        }
        
        response = requests.post(url, json=payload, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            text = data['candidates'][0]['content']['parts'][0]['text'].strip()
            
            # Remove markdown code blocks if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            # Parse JSON
            result = json.loads(text)
            
            print(f"[SUCCESS] Generated info for '{food_name}' from Gemini AI")
            print(f"  - Calories: {result.get('calories', 0)} kcal")
            print(f"  - Protein: {result.get('protein', 0)}g")
            print(f"  - Ingredients: {len(result.get('ingredients', []))} items")
            
            return result
        else:
            print(f"[ERROR] Gemini API lỗi {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[ERROR] Error generating from Gemini: {e}")
        return None


def analyze_image_with_retry(image_bytes: bytes, skip_api: str = ""):
    """
    Nhận diện lại với các API khác, bỏ qua API đã dùng trước đó.
    Returns: (food_name_vi, food_name_en, confidence, error_msg)
    """
    errors = []
    skip_api_lower = skip_api.lower()
    
    print(f"[RETRY] Skipping API: {skip_api}")
    
    # 1. Thử Gemini (nếu không bị skip)
    if "gemini" not in skip_api_lower and GEMINI_API_KEY:
        food_name_vi, food_name_en, confidence, err = recognize_food_gemini(image_bytes)
        # Nếu Gemini xác nhận KHÔNG PHẢI MÓN ĂN → trả về ngay
        if food_name_vi == "NOT_FOOD":
            return "NOT_FOOD", None, 0.99, None
        if food_name_vi and confidence > 0.5:
            return food_name_vi, food_name_en, confidence, None
        if err:
            errors.append(f"Gemini: {err}")
    
    # 2. Thử Spoonacular (nếu không bị skip)
    if "spoonacular" not in skip_api_lower and SPOONACULAR_API_KEY:
        food_name, confidence, err = recognize_food_spoonacular(image_bytes)
        if food_name and confidence > 0.3:
            return food_name, food_name, confidence, None
        if err:
            errors.append(f"Spoonacular: {err}")
    
    # 3. Thử Google Vision (nếu không bị skip)
    if "vision" not in skip_api_lower and GOOGLE_VISION_API_KEY:
        food_name, confidence, err = recognize_food_vision(image_bytes)
        if food_name and confidence > 0.5:
            return food_name, food_name, confidence, None
        if err:
            errors.append(f"Vision: {err}")
    
    return None, None, 0.0, " | ".join(errors) if errors else "Tất cả API đều fail"

