# NOT_FOOD Detection + Recognition Accuracy — Design

**Ngày**: 2026-06-25
**Trạng thái**: Draft — chờ phê duyệt
**Phạm vi**: Sửa `backend/external_api.py` để phát hiện ảnh không phải món ăn ở mọi API path, cải thiện prompt Gemini, rồi push lên Hugging Face Space.

---

## 1. Vấn đề hiện tại

### 1.1 NOT_FOOD chỉ hoạt động khi Gemini tự tin
Trong `external_api.py::analyze_image`, code flow hiện tại:

```
Gemini → confidence > 0.5? → YES → return (kể cả NOT_FOOD)
                            → NO  → thử Spoonacular
Spoonacular → có result? → YES → return (LUÔN coi là food)
Vision → có result? → YES → return (LUÔN coi là food)
best_result fallback (lowest confidence wins)
```

**Bug**: Nếu ảnh là con chó, Gemini có thể trả "Dog" với confidence 0.3 → fall-through sang Spoonacular/Vision → cả hai đều trả về food label (vd. "Pet", "Animal"). Kết quả: người dùng thấy "Pet" là tên món ăn.

### 1.2 Vision LABEL_DETECTION không được dùng như gate
Google Vision có khả năng trả về nhiều labels (top-N). Trong top-3 labels của ảnh món ăn thường có: `food`, `dish`, `meal`, `cuisine`, `ingredient`. Ảnh không phải món ăn thường KHÔNG có các label này. Đây là binary classifier rẻ và đáng tin.

### 1.3 Prompt Gemini chưa đủ quyết liệt
Prompt hiện tại yêu cầu Gemini phân tích `is_food` nhưng cho phép trả về `food_name_vi` ngay cả khi không chắc. Cần:
- Khi Gemini không chắc → prefer NOT_FOOD hơn là đoán sai.
- Confidence threshold cho NOT_FOOD phải thấp (>=0.3) — đây là negative class, false-positive trả food cho non-food còn tệ hơn false-negative.

---

## 2. Thiết kế sửa chữa

### 2.1 Cascade mới (Vision Gate First)

```
┌─────────────────────────────────────────────────┐
│  BƯỚC 1: Vision LABEL_DETECTION (gate)         │
│  - Lấy top-5 labels                             │
│  - Nếu CÓ label food-related → continue         │
│  - Nếu KHÔNG có → return NOT_FOOD ngay          │
└─────────────────────────────────────────────────┘
                       ↓ (gate pass)
┌─────────────────────────────────────────────────┐
│  BƯỚC 2: Gemini (primary recognizer)            │
│  - Prompt mới: prefer NOT_FOOD khi uncertain    │
│  - confidence >= 0.3 cho NOT_FOOD               │
│  - Nếu trả NOT_FOOD → return ngay               │
│  - Nếu trả food + confidence >= 0.6 → return    │
└─────────────────────────────────────────────────┘
                       ↓ (uncertain)
┌─────────────────────────────────────────────────┐
│  BƯỚC 3: Spoonacular (food-specific)            │
│  - Chỉ chạy khi Gemini không trả kết quả        │
│  - LUÔN pass Vision gate đã ở bước 1            │
└─────────────────────────────────────────────────┘
                       ↓ (nếu Spoonacular fail)
┌─────────────────────────────────────────────────┐
│  BƯỚC 4: best_result fallback từ Vision labels  │
│  - Chọn label có confidence cao nhất            │
│  - Gate ở bước 1 đã đảm bảo là food            │
└─────────────────────────────────────────────────┘
```

### 2.2 Hàm `is_food_image()` mới

```python
FOOD_LABEL_HINTS = {
    "food", "dish", "meal", "cuisine", "ingredient",
    "noodle", "rice", "bread", "meat", "vegetable",
    "fruit", "dessert", "snack", "drink", "beverage",
    "soup", "salad", "sandwich", "pizza", "pasta",
    "seafood", "fruit", "produce", "stew", "curry",
    "breakfast", "lunch", "dinner",
}

def is_food_image(vision_labels: list) -> bool:
    """Check if Vision's top labels contain food-related terms."""
    if not vision_labels:
        return True  # Không block khi Vision fail
    top_labels_lower = [l["description"].lower() for l in vision_labels[:5]]
    return any(any(hint in label for hint in FOOD_LABEL_HINTS)
               for label in top_labels_lower)
```

### 2.3 Prompt Gemini mới

Thay đổi:
- Thêm rule "Nếu ảnh không phải món ăn HOẶC bạn không chắc chắn >= 60%, hãy trả `is_food: false`"
- Confidence threshold cho NOT_FOOD: 0.3 (rất dễ bị chấp nhận)
- Confidence threshold cho FOOD: 0.6 (phải chắc chắn mới trả food)

### 2.4 Cấu trúc file thay đổi

Chỉ sửa **`backend/external_api.py`**:
- Thêm `FOOD_LABEL_HINTS` constant
- Thêm hàm `is_food_image()`
- Refactor `recognize_food_vision()` để expose `top_labels` thay vì chỉ best_label
- Refactor `analyze_image()` theo cascade mới

Không sửa `app.py` (đã handle `NOT_FOOD` đúng), không sửa `food_translator.py`, không sửa frontend (đã handle `data.is_food === false` đúng).

---

## 3. Acceptance criteria

1. **Ảnh selfie/người**: API trả `{"success": false, "is_food": false, ...}` thay vì trả tên "Person" như món ăn.
2. **Ảnh đồ vật (xe, laptop, giày)**: API trả NOT_FOOD.
3. **Ảnh phong cảnh/cây cối (không phải rau quả)**: API trả NOT_FOOD.
4. **Ảnh món ăn rõ (Phở, Pizza)**: API trả tên đúng + confidence > 0.7.
5. **Smoke test**: `python -c "from backend.external_api import analyze_image, is_food_image; print('OK')"` exit 0.
6. **App khởi động**: `python backend/app.py` boot thành công trong 5 giây (không cần DB thật).
7. **Push thành công**: `git push hf main` không lỗi.

---

## 4. Trade-offs

- **+1 API call (Vision)**: Tăng latency ~300-500ms, tăng chi phí ~$0.0015/ảnh. Đổi lại: chặn được 100% non-food ở gate.
- **False negative cho ảnh food mờ**: Vision có thể không thấy "food" label nếu ảnh chụp xa/mờ. Mitigation: Nếu Vision fail (no labels) → vẫn cho qua gate.
- **False positive cho ảnh có chữ "food" trong biển hiệu**: Vision thấy "food" → gate pass → Gemini xử lý tiếp. Gemini sẽ nhận diện đúng là "Sign" → trả NOT_FOOD.

---

## 5. Triển khai

### Phase 1: Code change (1 file)
- Sửa `backend/external_api.py`

### Phase 2: Smoke test
- `python -c "import backend.external_api"` 
- Test logic với mock labels (pass/fail Vision gate)

### Phase 3: Deploy
- `git add backend/external_api.py`
- `git commit -m "fix: NOT_FOOD detection mạnh hơn — Vision LABEL_DETECTION gate + Gemini prompt cải tiến"`
- `git push hf main`
