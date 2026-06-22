import requests
import base64
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys from .env file
GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY", "")
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

print(f"[CONFIG] Spoonacular API: {'OK' if SPOONACULAR_API_KEY else 'Missing'}")
print(f"[CONFIG] Google Vision API: {'OK' if GOOGLE_VISION_API_KEY else 'Missing'}")
print(f"[CONFIG] Gemini API: {'OK' if GEMINI_API_KEY else 'Missing'}")


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
    Sử dụng Gemini API - AI mạnh mẽ của Google cho food recognition
    """
    if not GEMINI_API_KEY:
        return None, 0.0, "Thiếu GEMINI_API_KEY"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {"text": """Analyze this food image carefully. 

If the image does NOT contain any food or dish (e.g., person, animal, object, scenery, text), reply with ONLY: NOT_FOOD

If the image DOES contain food, identify the SPECIFIC dish name. Reply with ONLY the dish name in snake_case, nothing else.

IMPORTANT RULES:
- For Vietnamese soups/canh dishes, identify the SPECIFIC type. Do NOT just say "soup" or "sour_soup". Instead identify:
  + canh_chua_ca (sour fish soup), canh_chua_tom (sour shrimp soup)
  + canh_kho_qua (bitter melon soup), canh_kho_qua_nhoi_thit (stuffed bitter melon soup)
  + canh_bi_dao (winter melon soup), canh_bi_do (pumpkin soup)
  + canh_mong_toi (Malabar spinach soup), canh_cai_xoong (watercress soup)
  + canh_bau (gourd soup), canh_bap_cai (cabbage soup)
  + canh_suon (pork rib soup), canh_rau (vegetable soup)
  + canh_ca_chua_trung (tomato egg soup), canh_rong_bien (seaweed soup)
- For Vietnamese noodle soups: pho_bo, pho_ga, bun_bo_hue, bun_rieu, hu_tieu, banh_canh, mi_quang
- For Vietnamese stews/braised: thit_kho, ca_kho_to, bo_kho
- For hotpots: lau_thai, lau_hai_san, lau_nam
- For other Vietnamese dishes, use Vietnamese romanized names without diacritics: com_tam, banh_mi, bun_cha, goi_cuon, banh_xeo
- For non-Vietnamese dishes, use English: pizza, sushi, hamburger, pasta, steak

Identify the KEY INGREDIENT visible in the dish (fish, shrimp, pork, chicken, beef, tofu, vegetables) to give the most specific name possible.

Reply with ONLY the dish name, nothing else."""},
                {"inlineData": {"mimeType": "image/jpeg", "data": encoded_image}}
            ]
        }],
        "generationConfig": {"temperature": 0.1}
    }
    
    try:
        print(f"[DEBUG] Trying Gemini API...")
        response = requests.post(url, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            label = data['candidates'][0]['content']['parts'][0]['text'].strip().lower()
            print(f"[DEBUG] Gemini success: {label}")
            
            # Kiểm tra nếu không phải món ăn
            if label == "not_food":
                print(f"[DEBUG] Gemini detected: NOT FOOD")
                return "NOT_FOOD", 0.99, None
            
            return label, 0.95, None
        else:
            error_msg = f"Gemini API lỗi {response.status_code}"
            print(f"[DEBUG] {error_msg}")
            return None, 0.0, error_msg
            
    except Exception as e:
        print(f"[DEBUG] Gemini exception: {e}")
        return None, 0.0, f"Gemini API Exception: {str(e)}"

def analyze_image(image_bytes: bytes):
    """
    Thứ tự ưu tiên (5 API):
    1. Gemini (AI mạnh nhất, độ chính xác cao)
    2. Spoonacular (chuyên về food)
    3. Google Vision (general purpose, reliable)
    4. Imagga (free tier, có food tags)
    5. Open Food Facts (miễn phí hoàn toàn)
    """
    errors = []
    
    # 1. Thử Gemini trước (AI mạnh nhất)
    if GEMINI_API_KEY:
        food_name_gemini, confidence_gemini, err = recognize_food_gemini(image_bytes)
        print(f"[DEBUG] Gemini => name='{food_name_gemini}', confidence={confidence_gemini}")
        if food_name_gemini and confidence_gemini > 0.5:  # Gemini rất chính xác
            return food_name_gemini, confidence_gemini, None
        if err:
            print(f"[DEBUG] Gemini error: {err}")
            errors.append(f"Gemini: {err}")
    
    # 2. Thử Spoonacular (chuyên về đồ ăn)
    if SPOONACULAR_API_KEY:
        food_name, confidence, err = recognize_food_spoonacular(image_bytes)
        print(f"[DEBUG] Spoonacular => name='{food_name}', confidence={confidence}")
        if food_name and confidence > 0.3:
            return food_name, confidence, None
        if err: 
            print(f"[DEBUG] Spoonacular error: {err}")
            errors.append(f"Spoonacular: {err}")
    
    # 3. Thử Google Vision (reliable, general purpose)
    if GOOGLE_VISION_API_KEY:
        food_name_v, confidence_v, err = recognize_food_vision(image_bytes)
        print(f"[DEBUG] Vision => name='{food_name_v}', confidence={confidence_v}")
        if food_name_v and confidence_v > 0.5:
            return food_name_v, confidence_v, None
        if err: 
            print(f"[DEBUG] Vision error: {err}")
            errors.append(f"Vision: {err}")
    
    # 4. Fallback sang Imagga (có food detection)
    food_name_img, confidence_img, err = recognize_food_imagga(image_bytes)
    print(f"[DEBUG] Imagga => name='{food_name_img}', confidence={confidence_img}")
    if food_name_img and confidence_img > 0.3:
        return food_name_img, confidence_img, None
    if err:
        print(f"[DEBUG] Imagga error: {err}")
        errors.append(f"Imagga: {err}")
    
    # 5. Fallback sang Open Food Facts
    food_name_off, confidence_off, err = recognize_food_openfoodfacts(image_bytes)
    print(f"[DEBUG] Open Food Facts => name='{food_name_off}', confidence={confidence_off}")
    if food_name_off and confidence_off > 0.3:
        return food_name_off, confidence_off, None
    if err:
        print(f"[DEBUG] Open Food Facts error: {err}")
        errors.append(f"Open Food Facts: {err}")
    
    # Nếu tất cả API có kết quả nhưng confidence thấp, chọn kết quả tốt nhất
    best_result = None
    best_confidence = 0
    
    if food_name_gemini and confidence_gemini > best_confidence:
        best_result = (food_name_gemini, confidence_gemini)
        best_confidence = confidence_gemini
    
    if food_name and confidence > best_confidence:
        best_result = (food_name, confidence)
        best_confidence = confidence
    
    if food_name_v and confidence_v > best_confidence:
        best_result = (food_name_v, confidence_v)
        best_confidence = confidence_v
    
    if food_name_img and confidence_img > best_confidence:
        best_result = (food_name_img, confidence_img)
        best_confidence = confidence_img
    
    if food_name_off and confidence_off > best_confidence:
        best_result = (food_name_off, confidence_off)
        best_confidence = confidence_off
    
    if best_result:
        print(f"[DEBUG] Using best result despite low confidence: {best_result[0]} ({best_result[1]})")
        return best_result[0], best_result[1], None
    
    return None, 0.0, " | ".join(errors) if errors else "Không thể nhận diện món ăn"


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
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
        
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
    Nhận diện lại với các API khác, bỏ qua API đã dùng trước đó
    """
    errors = []
    skip_api_lower = skip_api.lower()
    
    print(f"[RETRY] Skipping API: {skip_api}")
    
    # 1. Thử Gemini (nếu không bị skip)
    if "gemini" not in skip_api_lower and GEMINI_API_KEY:
        food_name, confidence, err = recognize_food_gemini(image_bytes)
        if food_name and confidence > 0.5:
            return food_name, confidence, None
        if err:
            errors.append(f"Gemini: {err}")
    
    # 2. Thử Spoonacular (nếu không bị skip)
    if "spoonacular" not in skip_api_lower and SPOONACULAR_API_KEY:
        food_name, confidence, err = recognize_food_spoonacular(image_bytes)
        if food_name and confidence > 0.3:
            return food_name, confidence, None
        if err:
            errors.append(f"Spoonacular: {err}")
    
    # 3. Thử Google Vision (nếu không bị skip)
    if "vision" not in skip_api_lower and GOOGLE_VISION_API_KEY:
        food_name, confidence, err = recognize_food_vision(image_bytes)
        if food_name and confidence > 0.5:
            return food_name, confidence, None
        if err:
            errors.append(f"Vision: {err}")
    
    # 4. Thử Imagga (nếu không bị skip)
    if "imagga" not in skip_api_lower:
        food_name, confidence, err = recognize_food_imagga(image_bytes)
        if food_name and confidence > 0.3:
            return food_name, confidence, None
        if err:
            errors.append(f"Imagga: {err}")
    
    # 5. Thử Open Food Facts (nếu không bị skip)
    if "openfoodfacts" not in skip_api_lower:
        food_name, confidence, err = recognize_food_openfoodfacts(image_bytes)
        if food_name and confidence > 0.3:
            return food_name, confidence, None
        if err:
            errors.append(f"Open Food Facts: {err}")
    
    return None, 0.0, " | ".join(errors) if errors else "Tất cả API đều fail"
