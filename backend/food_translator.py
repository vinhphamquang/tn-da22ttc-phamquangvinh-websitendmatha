#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Food Name Translator - English to Vietnamese
Chuyển đổi tên món ăn từ tiếng Anh sang tiếng Việt
"""

import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Dictionary ánh xạ tên món ăn Anh - Việt
FOOD_TRANSLATION = {
    # Vietnamese dishes
    "pho": "Phở",
    "pho bo": "Phở Bò",
    "beef pho": "Phở Bò",
    "chicken pho": "Phở Gà",
    "banh mi": "Bánh Mì",
    "vietnamese sandwich": "Bánh Mì",
    "bun cha": "Bún Chả",
    "grilled pork with noodles": "Bún Chả",
    "spring rolls": "Gỏi Cuốn",
    "fresh spring rolls": "Gỏi Cuốn",
    "summer rolls": "Gỏi Cuốn",
    "fried spring rolls": "Chả Giò",
    "egg rolls": "Nem Rán",
    "bun bo hue": "Bún Bò Huế",
    "hue beef noodle": "Bún Bò Huế",
    "cao lau": "Cao Lầu",
    "mi quang": "Mì Quảng",
    "quang noodles": "Mì Quảng",
    "banh xeo": "Bánh Xèo",
    "vietnamese pancake": "Bánh Xèo",
    "sizzling pancake": "Bánh Xèo",
    "banh cuon": "Bánh Cuốn",
    "steamed rice rolls": "Bánh Cuốn",
    "com tam": "Cơm Tấm",
    "broken rice": "Cơm Tấm",
    "com ga": "Cơm Gà",
    "chicken rice": "Cơm Gà Hải Nam",
    "hainanese chicken rice": "Cơm Gà Hải Nam",
    "hu tieu": "Hủ Tiếu",
    "hu tieu nam vang": "Hủ Tiếu Nam Vang",
    "bun rieu": "Bún Riêu",
    "crab noodle soup": "Bún Riêu",
    "bun thit nuong": "Bún Thịt Nướng",
    "grilled pork vermicelli": "Bún Thịt Nướng",
    "bun mam": "Bún Mắm",
    "bun dau mam tom": "Bún Đậu Mắm Tôm",
    "fried tofu with shrimp paste": "Bún Đậu Mắm Tôm",
    "banh canh": "Bánh Canh",
    "banh canh cua": "Bánh Canh Cua",
    "thick noodle soup": "Bánh Canh",
    "xoi": "Xôi",
    "sticky rice": "Xôi",
    "xoi xeo": "Xôi Xéo",
    "xoi gac": "Xôi Gấc",
    "banh bao": "Bánh Bao",
    "steamed bun": "Bánh Bao",
    "banh bot loc": "Bánh Bột Lọc",
    "banh khot": "Bánh Khọt",
    "mini pancakes": "Bánh Khọt",
    "cha ca": "Chả Cá",
    "cha ca la vong": "Chả Cá Lã Vọng",
    "grilled fish": "Chả Cá",
    "nem ran": "Nem Rán",
    "cha gio": "Chả Giò",
    "goi ngo sen": "Gỏi Ngó Sen",
    "lotus root salad": "Gỏi Ngó Sen",
    "bo luc lac": "Bò Lúc Lắc",
    "shaking beef": "Bò Lúc Lắc",
    "canh chua": "Canh Chua",
    "canh chua ca": "Canh Chua Cá",
    "canh chua ca loc": "Canh Chua Cá Lóc",
    "canh chua tom": "Canh Chua Tôm",
    "canh chua ca tre": "Canh Chua Cá Trê",
    "sour soup": "Canh Chua",
    "fish sour soup": "Canh Chua Cá",
    "shrimp sour soup": "Canh Chua Tôm",
    
    # Các loại canh cụ thể
    "canh kho qua": "Canh Khổ Qua",
    "canh kho qua nhoi thit": "Canh Khổ Qua Nhồi Thịt",
    "bitter melon soup": "Canh Khổ Qua",
    "stuffed bitter melon soup": "Canh Khổ Qua Nhồi Thịt",
    "canh bi dao": "Canh Bí Đao",
    "winter melon soup": "Canh Bí Đao",
    "canh bi do": "Canh Bí Đỏ",
    "pumpkin soup": "Canh Bí Đỏ",
    "canh mong toi": "Canh Mồng Tơi",
    "spinach soup": "Canh Mồng Tơi",
    "malabar spinach soup": "Canh Mồng Tơi",
    "canh cai xoong": "Canh Cải Xoong",
    "watercress soup": "Canh Cải Xoong",
    "canh bau": "Canh Bầu",
    "gourd soup": "Canh Bầu",
    "canh bap cai": "Canh Bắp Cải",
    "cabbage soup": "Canh Bắp Cải",
    "canh suon": "Canh Sườn",
    "pork rib soup": "Canh Sườn",
    "canh rau": "Canh Rau",
    "vegetable soup": "Canh Rau",
    "canh ca chua trung": "Canh Cà Chua Trứng",
    "tomato egg soup": "Canh Cà Chua Trứng",
    "canh rong bien": "Canh Rong Biển",
    "seaweed soup": "Canh Rong Biển",
    "canh cai": "Canh Cải",
    "canh cai thia": "Canh Cải Thìa",
    "canh hen": "Canh Hến",
    "canh ngao": "Canh Ngao",
    "clam soup": "Canh Ngao",
    "thit kho": "Thịt Kho",
    "thit kho tau": "Thịt Kho Tàu",
    "braised pork": "Thịt Kho Tàu",
    "ca kho to": "Cá Kho Tộ",
    "braised fish": "Cá Kho Tộ",
    "com chien": "Cơm Chiên",
    "fried rice": "Cơm Chiên Dương Châu",
    "lau thai": "Lẩu Thái",
    "thai hotpot": "Lẩu Thái",
    "ga nuong": "Gà Nướng",
    "grilled chicken": "Gà Nướng Mật Ong",
    "muc xao": "Mực Xào",
    "stir fried squid": "Mực Xào Sa Tế",
    "tom rang": "Tôm Rang",
    "salt and pepper shrimp": "Tôm Rang Muối",
    "suon xao": "Sườn Xào",
    "sweet and sour ribs": "Sườn Xào Chua Ngọt",
    "ca chien": "Cá Chiên",
    "fried fish": "Cá Chiên Xù",
    "rau muong": "Rau Muống",
    "water spinach": "Rau Muống Xào Tỏi",
    "dau hu": "Đậu Hũ",
    "tofu": "Đậu Hũ Sốt Cà",
    "chao long": "Cháo Lòng",
    "pork organ porridge": "Cháo Lòng",
    "banh uot": "Bánh Ướt",
    "banh duc": "Bánh Đúc",
    "banh trang tron": "Bánh Tráng Trộn",
    "rice paper salad": "Bánh Tráng Trộn",
    "com hen": "Cơm Hến",
    "clam rice": "Cơm Hến",
    
    # Seafood & Sandwiches
    "lobster_roll": "Bánh Mì Tôm Hùm",
    "lobster roll": "Bánh Mì Tôm Hùm",
    "crab roll": "Bánh Mì Cua",
    "shrimp roll": "Bánh Mì Tôm",
    
    # Chinese dishes
    "chow mein": "Mì Xào",
    "chow_mein": "Mì Xào",
    "lo mein": "Mì Lộn",
    "fried noodles": "Mì Xào",
    "stir fried noodles": "Mì Xào",
    "fried rice": "Cơm Chiên",
    "yangzhou fried rice": "Cơm Chiên Dương Châu",
    "egg fried rice": "Cơm Chiên Trứng",
    "dim sum": "Dimsum",
    "dumpling": "Há Cảo",
    "dumplings": "Há Cảo",
    "wonton": "Hoành Thánh",
    "spring roll": "Chả Giò",
    "peking duck": "Vịt Quay Bắc Kinh",
    "sweet and sour pork": "Thịt Lợn Xào Chua Ngọt",
    "kung pao chicken": "Gà Kung Pao",
    "mapo tofu": "Đậu Hũ Tứ Xuyên",
    "hot pot": "Lẩu",
    "hotpot": "Lẩu",
    "congee": "Cháo",
    "porridge": "Cháo",
    "char siu": "Xá Xíu",
    "bbq pork": "Thịt Nướng",
    
    # Japanese dishes
    "sushi": "Sushi",
    "sashimi": "Sashimi",
    "ramen": "Ramen",
    "udon": "Udon",
    "tempura": "Tempura",
    "teriyaki": "Teriyaki",
    "yakitori": "Yakitori",
    "tonkatsu": "Tonkatsu",
    "okonomiyaki": "Okonomiyaki",
    "takoyaki": "Takoyaki",
    "miso soup": "Súp Miso",
    "edamame": "Đậu Nành Luộc",
    
    # Korean dishes
    "kimchi": "Kim Chi",
    "bibimbap": "Cơm Trộn Hàn Quốc",
    "bulgogi": "Thịt Bò Nướng Hàn Quốc",
    "korean bbq": "BBQ Hàn Quốc",
    "tteokbokki": "Bánh Gạo Cay Hàn Quốc",
    "japchae": "Miến Xào Hàn Quốc",
    "samgyeopsal": "Thịt Ba Chỉ Nướng",
    
    # Western dishes
    "pizza": "Pizza",
    "burger": "Burger",
    "hamburger": "Hamburger",
    "pasta": "Mì Ý",
    "spaghetti": "Mì Ý Spaghetti",
    "lasagna": "Lasagna",
    "steak": "Bít Tết",
    "salad": "Salad",
    "sandwich": "Sandwich",
    "hot dog": "Xúc Xích",
    "taco": "Taco",
    "burrito": "Burrito",
    "beef stew": "Bò Kho",
    "beef_stew": "Bò Kho",
    "stew": "Món Hầm",
    "nachos": "Nachos",
    "french fries": "Khoai Tây Chiên",
    "fish and chips": "Cá Chiên Khoai Tây",
    "fish_and_chips": "Cá Chiên Khoai Tây",
    "fried fish": "Cá Chiên",
    "fish fillet": "Phi Lê Cá",

    "fries": "Khoai Tây Chiên",
    "chicken wings": "Cánh Gà Chiên",
    "fried chicken": "Gà Rán",
    
    # Desserts (continued)
    "che": "Chè",
    "sweet soup": "Chè",
    "che buoi": "Chè Bưởi",
    "che dau xanh": "Chè Đậu Xanh",
    "che thai": "Chè Thái",
    "banh flan": "Bánh Flan",
    "flan": "Bánh Flan",
    "creme caramel": "Bánh Flan",
    "banh chuoi": "Bánh Chuối",
    "banana cake": "Bánh Chuối Nướng",
    "sua chua": "Sữa Chua",
    "yogurt": "Sữa Chua",
    "banh bong lan": "Bánh Bông Lan",
    "sponge cake": "Bánh Bông Lan",
    "banh tieu": "Bánh Tiêu",
    "hollow donuts": "Bánh Tiêu",
    "banh tet": "Bánh Tét",
    "cylindrical rice cake": "Bánh Tét",
    
    # Common foods
    "rice": "Cơm",
    "noodles": "Bún",
    "soup": "Canh",
    "salad": "Gỏi",
    "porridge": "Cháo",
}

def translate_food_name(english_name: str) -> str:
    """
    Chuyển đổi tên món ăn từ tiếng Anh sang tiếng Việt
    
    Args:
        english_name: Tên món ăn bằng tiếng Anh
        
    Returns:
        Tên món ăn bằng tiếng Việt (nếu có trong dictionary)
        Hoặc tên gốc (nếu không tìm thấy)
    """
    if not english_name:
        return english_name
    
    # Chuyển về lowercase để so sánh
    english_lower = english_name.lower().strip()
    
    # Tìm trong dictionary
    if english_lower in FOOD_TRANSLATION:
        vietnamese_name = FOOD_TRANSLATION[english_lower]
        print(f"[TRANSLATE] '{english_name}' -> '{vietnamese_name}'")
        return vietnamese_name
    
    # Thử tìm partial match - chấm điểm để chọn kết quả tốt nhất
    best_match = None
    best_score = 0
    for eng_key, viet_value in FOOD_TRANSLATION.items():
        score = 0
        if eng_key in english_lower:
            # Key nằm trong input: ưu tiên key dài hơn (cụ thể hơn)
            score = len(eng_key) * 2
        elif english_lower in eng_key:
            # Input nằm trong key: điểm thấp hơn (match ngược)
            score = len(english_lower)
        
        if score > best_score:
            best_match = viet_value
            best_score = score
    
    if best_match:
        print(f"[TRANSLATE] '{english_name}' -> '{best_match}' (best partial match, score={best_score})")
        return best_match
    
    # Không tìm thấy, giữ nguyên tên gốc
    print(f"[TRANSLATE] '{english_name}' -> Giu nguyen (khong tim thay ban dich)")
    return english_name

def get_search_variants(food_name: str) -> list:
    """
    Tạo danh sách các biến thể tên món ăn để tìm kiếm
    
    Args:
        food_name: Tên món ăn
        
    Returns:
        List các biến thể tên để tìm kiếm
    """
    variants = [food_name]
    
    # Thêm bản dịch nếu là tiếng Anh
    translated = translate_food_name(food_name)
    if translated != food_name:
        variants.append(translated)
    
    # Thêm các biến thể viết hoa/thường
    variants.append(food_name.lower())
    variants.append(food_name.upper())
    variants.append(food_name.capitalize())
    
    # Remove duplicates
    return list(set(variants))

# Test function
if __name__ == "__main__":
    test_foods = [
        "pho",
        "Banh Mi",
        "spring rolls",
        "Bun Cha",
        "Pizza",
        "Sushi"
    ]
    
    print("=" * 60)
    print("TEST FOOD TRANSLATOR")
    print("=" * 60)
    
    for food in test_foods:
        translated = translate_food_name(food)
        variants = get_search_variants(food)
        print(f"\nOriginal: {food}")
        print(f"Translated: {translated}")
        print(f"Search variants: {variants}")
