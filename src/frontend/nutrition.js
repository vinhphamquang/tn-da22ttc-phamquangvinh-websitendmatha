// Nutrition Plan JavaScript

document.addEventListener('DOMContentLoaded', () => {
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    
    if (!loggedUser) {
        window.location.href = '/';
        return;
    }

    // --- Navbar Setup ---
    const displayUsername = document.getElementById('display-username');
    if (displayUsername) displayUsername.textContent = loggedUser.name;

    if (loggedUser.role === 'admin') {
        const adminLink = document.getElementById('nav-admin-link');
        if (adminLink) {
            adminLink.style.display = '';
            adminLink.classList.remove('hidden');
        }
    }



    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) {
        btnLogout.addEventListener('click', () => {
            if (typeof window.gracefulLogout === 'function') {
                window.gracefulLogout();
            } else {
                localStorage.removeItem('smartfood_user');
                window.location.href = '/';
            }
        });
    }

    const navToggle = document.getElementById('nav-toggle');
    const navLinks = document.getElementById('nav-links');
    if (navToggle && navLinks) {
        navToggle.addEventListener('click', () => navLinks.classList.toggle('show'));
    }

    loadHealthProfile();
    loadPlanHistory();
    loadWeightHistory();
    // initNutritionNotifications(loggedUser.id); (Moved to notifications.js)
    initWeightModal();

    const form = document.getElementById('health-profile-form');
    form.addEventListener('submit', handleFormSubmit);
});

let currentPlan = null;

// Meal distribution config
const MEAL_CONFIG = {
    breakfast: { percent: 0.25, name: 'Bữa Sáng', emoji: '🌅' },
    lunch:     { percent: 0.35, name: 'Bữa Trưa', emoji: '☀️' },
    dinner:    { percent: 0.30, name: 'Bữa Tối', emoji: '🌙' },
    snack:     { percent: 0.10, name: 'Bữa Phụ', emoji: '🍎' }
};

// Track selected foods per meal
let selectedFoods = {
    breakfast: null,
    lunch: null,
    dinner: null,
    snack: null
};

// Store all available foods per meal for swap suggestions
let mealFoodLists = {
    breakfast: [],
    lunch: [],
    dinner: [],
    snack: []
};

async function loadHealthProfile() {
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    try {
        const response = await fetch(`/api/health-profile/${loggedUser.id}`);
        const data = await response.json();
        if (data.success && data.profile) {
            const profile = data.profile;
            document.getElementById('weight').value = profile.CanNang;
            document.getElementById('height').value = profile.ChieuCao;
            document.getElementById('age').value = profile.Tuoi;
            document.getElementById('gender').value = profile.GioiTinh;
            document.getElementById('activity').value = profile.MucDoVanDong;
            document.getElementById('goal').value = profile.MucTieu;
            if (profile.BMR && profile.TDEE) {
                displayResults(profile);
            }
        }
    } catch (error) {
        console.error('Error loading health profile:', error);
    }
}

async function handleFormSubmit(e) {
    e.preventDefault();
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    const data = {
        CanNang: parseFloat(document.getElementById('weight').value),
        ChieuCao: parseFloat(document.getElementById('height').value),
        Tuoi: parseInt(document.getElementById('age').value),
        GioiTinh: document.getElementById('gender').value,
        MucDoVanDong: document.getElementById('activity').value,
        MucTieu: document.getElementById('goal').value
    };
    try {
        const response = await fetch(`/api/health-profile/${loggedUser.id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) {
            const profileResponse = await fetch(`/api/health-profile/${loggedUser.id}`);
            const profileData = await profileResponse.json();
            if (profileData.success) {
                // Reset selections when recalculating
                selectedFoods = { breakfast: null, lunch: null, dinner: null, snack: null };
                mealFoodLists = { breakfast: [], lunch: [], dinner: [], snack: [] };
                displayResults(profileData.profile);
            }
            // Show weight change modal if there was a previous entry
            const wc = result.weightChange;
            if (wc && !wc.is_first_entry && wc.old_weight !== null && typeof wc.diff === 'number') {
                showWeightChangeModal(wc);
            }
            // Refresh weight history & chart
            loadWeightHistory();
        } else {
            alert('Có lỗi xảy ra: ' + result.message);
        }
    } catch (error) {
        console.error('Error saving health profile:', error);
        alert('Lỗi kết nối server');
    }
}

function displayResults(profile) {
    currentPlan = profile;

    const resultsSection = document.getElementById('results-section');
    resultsSection.classList.remove('hidden');

    animateValue('bmr-value', 0, Math.round(profile.BMR), 800);
    animateValue('tdee-value', 0, Math.round(profile.TDEE), 800);
    animateValue('target-value', 0, Math.round(profile.CaloDuKien), 800);

    const bmi = profile.CanNang / ((profile.ChieuCao / 100) ** 2);
    animateValue('bmi-value', 0, bmi, 800, 1);

    let bmiCategory = '', bmiColor = '';
    if (bmi < 18.5) { bmiCategory = 'Gầy'; bmiColor = '#3b82f6'; }
    else if (bmi < 25) { bmiCategory = 'Bình thường'; bmiColor = '#22c55e'; }
    else if (bmi < 30) { bmiCategory = 'Thừa cân'; bmiColor = '#f59e0b'; }
    else { bmiCategory = 'Béo phì'; bmiColor = '#ef4444'; }

    const bmiCategoryEl = document.getElementById('bmi-category');
    bmiCategoryEl.textContent = bmiCategory;
    bmiCategoryEl.style.color = bmiColor;
    bmiCategoryEl.style.fontWeight = '600';

    // Render detailed BMI assessment
    renderBmiAssessment(bmi, bmiCategory, bmiColor, profile.MucTieu);

    // Apply premium lock on BMI assessment for free users
    applyPremiumLocks();

    const targetCalo = profile.CaloDuKien;
    for (const [mealType, config] of Object.entries(MEAL_CONFIG)) {
        const mealCalo = Math.round(targetCalo * config.percent);
        const caloEl = document.getElementById(`${mealType}-calo`);
        if (caloEl) caloEl.textContent = `${mealCalo} kcal`;
        const targetEl = document.getElementById(`${mealType}-target`);
        if (targetEl) targetEl.textContent = mealCalo;
    }

    loadAllMealSuggestions(targetCalo);

    setTimeout(() => {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 200);
}

// BMI category meta — mirror backend classify_bmi
const BMI_META = {
    'Gầy': {
        color: '#3b82f6',
        range: '< 18.5',
        rec: 'Bạn đang ở thể trạng gầy. Hãy tăng khẩu phần ăn lành mạnh, ưu tiên thực phẩm giàu protein (thịt, cá, trứng, sữa), carbs phức hợp (gạo lứt, yến mạch) và chất béo tốt (bơ, hạt).',
        suggestedGoal: 'Tăng cân'
    },
    'Bình thường': {
        color: '#22c55e',
        range: '18.5 - 24.9',
        rec: 'Bạn đang ở thể trạng bình thường — duy trì rất tốt! Hãy giữ chế độ ăn cân đối (50% carbs, 25% protein, 25% chất béo) và vận động đều đặn.',
        suggestedGoal: 'Duy trì'
    },
    'Thừa cân': {
        color: '#f59e0b',
        range: '25 - 29.9',
        rec: 'Bạn đang ở thể trạng thừa cân. Hãy giảm lượng calo nạp vào khoảng 300-500 kcal/ngày, ưu tiên rau xanh, protein nạc (gà, cá), giảm tinh bột tinh chế và đồ ngọt.',
        suggestedGoal: 'Giảm cân'
    },
    'Béo phì': {
        color: '#ef4444',
        range: '≥ 30',
        rec: 'Bạn đang ở thể trạng béo phì. Nên giảm cân an toàn 0.5-1kg/tuần, ưu tiên thực phẩm giàu chất xơ, protein nạc; hạn chế đồ chiên rán, đồ ngọt; tham vấn bác sĩ nếu có bệnh nền.',
        suggestedGoal: 'Giảm cân'
    }
};

function renderBmiAssessment(bmi, category, color, mucTieu) {
    const meta = BMI_META[category];
    if (!meta) return;

    const goalMap = {
        'tang_can': 'Tăng cân',
        'giam_can': 'Giảm cân',
        'giu_dang': 'Duy trì'
    };
    const displayMucTieu = goalMap[mucTieu] || mucTieu;

    const numberEl = document.getElementById('bmi-number');
    const badgeEl = document.getElementById('bmi-badge');
    const rangeEl = document.getElementById('bmi-range-text');
    const recEl = document.getElementById('bmi-recommendation');
    const mainCard = document.getElementById('bmi-main-card');
    const markerEl = document.getElementById('bmi-scale-marker');
    const banner = document.getElementById('bmi-goal-banner');
    const bannerText = document.getElementById('bmi-goal-text');

    if (numberEl) numberEl.textContent = bmi.toFixed(1);
    if (badgeEl) {
        badgeEl.textContent = category;
        badgeEl.style.background = color;
    }
    if (rangeEl) rangeEl.textContent = meta.range;
    if (recEl) recEl.textContent = meta.rec;
    if (mainCard) {
        mainCard.style.borderColor = color;
        mainCard.style.background = `linear-gradient(135deg, ${hexToRgba(color, 0.12)}, ${hexToRgba(color, 0.04)})`;
    }
    if (markerEl) {
        // Map bmi (15-40) → 0-100%
        const clamped = Math.max(15, Math.min(40, bmi));
        const pct = ((clamped - 15) / (40 - 15)) * 100;
        markerEl.style.left = `${pct}%`;
        markerEl.style.background = color;
    }

    // Show goal mismatch banner if user's goal doesn't match recommended
    if (banner && bannerText) {
        if (displayMucTieu && displayMucTieu !== meta.suggestedGoal) {
            bannerText.innerHTML = `Với thể trạng <strong>${category}</strong>, mục tiêu phù hợp hơn là <strong>${meta.suggestedGoal}</strong> thay vì "${displayMucTieu}".`;
            banner.classList.remove('hidden');
        } else {
            banner.classList.add('hidden');
        }
    }
}

function hexToRgba(hex, alpha) {
    const h = hex.replace('#', '');
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function animateValue(elementId, start, end, duration, decimals = 0) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const startTime = performance.now();
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        el.textContent = (start + (end - start) * easeOut).toFixed(decimals);
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

async function loadAllMealSuggestions(totalCalo) {
    const promises = Object.entries(MEAL_CONFIG).map(([mealType, config]) => {
        return loadMealSuggestions(mealType, Math.round(totalCalo * config.percent));
    });
    await Promise.all(promises);
}

async function loadMealSuggestions(mealType, mealCalo) {
    const container = document.getElementById(`${mealType}-suggestions`);
    if (!container) return;
    
    container.innerHTML = '<div class="np-loading"><i class="fa-solid fa-spinner fa-spin"></i> Đang tải đề xuất...</div>';
    
    try {
        const response = await fetch(`/api/meal-suggestions?meal_type=${mealType}&target_calo=${mealCalo}`);
        const data = await response.json();
        
        if (data.success && data.suggestions && data.suggestions.length > 0) {
            mealFoodLists[mealType] = data.suggestions;
            renderFoodCards(container, data.suggestions, mealCalo, mealType);
        } else {
            container.innerHTML = `<div class="np-no-data"><i class="fa-solid fa-bowl-food"></i><p>Chưa có đề xuất phù hợp</p></div>`;
        }
    } catch (error) {
        console.error(`Error loading ${mealType}:`, error);
        container.innerHTML = `<div class="np-no-data"><i class="fa-solid fa-exclamation-triangle"></i><p>Lỗi khi tải đề xuất</p></div>`;
    }
}

function renderFoodCards(container, suggestions, targetCalo, mealType) {
    // Find the best match (closest to target calo)
    let bestIndex = 0;
    let bestDiff = Infinity;
    suggestions.forEach((food, i) => {
        const diff = Math.abs(food.calories - targetCalo);
        if (diff < bestDiff) {
            bestDiff = diff;
            bestIndex = i;
        }
    });
    
    // Auto-select the best match
    selectedFoods[mealType] = suggestions[bestIndex];
    const bestFood = suggestions[bestIndex];
    const otherFoods = suggestions.filter((_, i) => i !== bestIndex);
    
    // Build main recommended card (always visible)
    let html = `
        <div class="np-food-card selected recommended good-match" 
             data-meal="${mealType}" data-food-id="${bestFood.id}"
             onclick="selectFood('${mealType}', ${JSON.stringify(bestFood).replace(/"/g, '&quot;')})"
             style="animation: pageFadeIn 0.4s ease both; cursor: pointer;">
            <div class="np-recommended-badge"><i class="fa-solid fa-star"></i> Đề xuất tốt nhất</div>
            <div class="np-food-header">
                <div class="np-food-name">${bestFood.name}</div>
                <div class="np-food-calo-badge">${bestFood.calories} kcal</div>
            </div>
            <div class="np-food-category"><i class="fa-solid fa-tag"></i> ${bestFood.category}</div>
            ${bestFood.description ? `<p class="np-food-desc">${bestFood.description}</p>` : ''}
            <div class="np-food-nutrition">
                <div class="np-nutrition-item">
                    <div class="np-nutrition-label">Protein</div>
                    <div class="np-nutrition-value" style="color: var(--c-prot);">${bestFood.protein}g</div>
                </div>
                <div class="np-nutrition-item">
                    <div class="np-nutrition-label">Carbs</div>
                    <div class="np-nutrition-value" style="color: var(--c-carb);">${bestFood.carbs}g</div>
                </div>
                <div class="np-nutrition-item">
                    <div class="np-nutrition-label">Chất béo</div>
                    <div class="np-nutrition-value" style="color: var(--c-fat);">${bestFood.fats}g</div>
                </div>
            </div>
            <div class="np-select-indicator">
                <i class="fa-solid fa-check-circle"></i>
                <span>Đã chọn</span>
            </div>
        </div>
    `;
    
    // "Xem thêm" button + collapsible list
    if (otherFoods.length > 0) {
        html += `
            <div class="np-more-section">
                <button class="np-more-btn" onclick="toggleMoreFoods('${mealType}', this)">
                    <i class="fa-solid fa-chevron-down"></i>
                    <span>Xem thêm ${otherFoods.length} món khác</span>
                </button>
                <div class="np-more-list" id="more-${mealType}" style="display:none;">
        `;
        otherFoods.forEach((food, index) => {
            const isSelected = selectedFoods[mealType] && selectedFoods[mealType].id === food.id;
            const caloriesDiff = Math.abs(food.calories - targetCalo);
            const isGoodMatch = caloriesDiff <= targetCalo * 0.2;
            
            html += `
                <div class="np-food-card ${isSelected ? 'selected' : ''} ${isGoodMatch ? 'good-match' : ''}" 
                     data-meal="${mealType}" data-food-id="${food.id}"
                     onclick="selectFood('${mealType}', ${JSON.stringify(food).replace(/"/g, '&quot;')})"
                     style="animation: pageFadeIn 0.3s ${index * 0.04}s ease both; cursor: pointer;">
                    <div class="np-food-header">
                        <div class="np-food-name">${food.name}</div>
                        <div class="np-food-calo-badge">${food.calories} kcal</div>
                    </div>
                    <div class="np-food-category"><i class="fa-solid fa-tag"></i> ${food.category}</div>
                    ${food.description ? `<p class="np-food-desc">${food.description}</p>` : ''}
                    <div class="np-food-nutrition">
                        <div class="np-nutrition-item">
                            <div class="np-nutrition-label">Protein</div>
                            <div class="np-nutrition-value" style="color: var(--c-prot);">${food.protein}g</div>
                        </div>
                        <div class="np-nutrition-item">
                            <div class="np-nutrition-label">Carbs</div>
                            <div class="np-nutrition-value" style="color: var(--c-carb);">${food.carbs}g</div>
                        </div>
                        <div class="np-nutrition-item">
                            <div class="np-nutrition-label">Chất béo</div>
                            <div class="np-nutrition-value" style="color: var(--c-fat);">${food.fats}g</div>
                        </div>
                    </div>
                    <div class="np-select-indicator">
                        <i class="fa-solid ${isSelected ? 'fa-check-circle' : 'fa-circle-plus'}"></i>
                        <span>${isSelected ? 'Đã chọn' : 'Nhấn để chọn'}</span>
                    </div>
                </div>
            `;
        });
        html += `</div></div>`;
    }
    
    container.innerHTML = html;

    // Apply premium restrictions on food suggestions
    applyMealSuggestionLocks(container, mealType, suggestions.length);
    
    // Update daily summary after rendering
    updateDailySummary();
}

// Toggle "Xem thêm" section
window.toggleMoreFoods = function(mealType, btn) {
    const list = document.getElementById(`more-${mealType}`);
    const icon = btn.querySelector('i');
    const text = btn.querySelector('span');
    const isHidden = list.style.display === 'none';
    
    list.style.display = isHidden ? 'grid' : 'none';
    icon.className = isHidden ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down';
    text.textContent = isHidden 
        ? 'Ẩn bớt' 
        : `Xem thêm ${list.querySelectorAll('.np-food-card').length} món khác`;
    btn.classList.toggle('expanded', isHidden);
};

// Global function for selecting a food from a meal
window.selectFood = function(mealType, food) {
    // Toggle: if same food clicked, deselect
    if (selectedFoods[mealType] && selectedFoods[mealType].id === food.id) {
        selectedFoods[mealType] = null;
    } else {
        selectedFoods[mealType] = food;
    }
    
    // Update card selection visuals
    const container = document.getElementById(`${mealType}-suggestions`);
    const cards = container.querySelectorAll('.np-food-card');
    cards.forEach(card => {
        const cardId = parseInt(card.dataset.foodId);
        const isSelected = selectedFoods[mealType] && selectedFoods[mealType].id === cardId;
        card.classList.toggle('selected', isSelected);
        
        const indicator = card.querySelector('.np-select-indicator');
        if (indicator) {
            indicator.innerHTML = isSelected
                ? '<i class="fa-solid fa-check-circle"></i><span>Đã chọn</span>'
                : '<i class="fa-solid fa-circle-plus"></i><span>Nhấn để chọn</span>';
        }
    });
    
    updateDailySummary();
};

function updateDailySummary() {
    const summarySection = document.getElementById('daily-summary');
    const summaryContent = document.getElementById('summary-content');
    const summaryTotal = document.getElementById('summary-total');
    
    const hasAnySelection = Object.values(selectedFoods).some(f => f !== null);
    
    if (!hasAnySelection) {
        summarySection.classList.add('hidden');
        return;
    }
    
    summarySection.classList.remove('hidden');
    
    let totalCalo = 0, totalProtein = 0, totalCarbs = 0, totalFats = 0;
    let contentHtml = '<div class="np-summary-meals">';
    
    for (const [mealType, config] of Object.entries(MEAL_CONFIG)) {
        const food = selectedFoods[mealType];
        const mealCalo = currentPlan ? Math.round(currentPlan.CaloDuKien * config.percent) : 0;
        
        contentHtml += `
            <div class="np-summary-meal-row ${food ? 'has-food' : 'empty'}">
                <div class="np-summary-meal-label">
                    <span class="np-summary-emoji">${config.emoji}</span>
                    <span class="np-summary-meal-name">${config.name}</span>
                    <span class="np-summary-meal-target">(${mealCalo} kcal)</span>
                </div>
                <div class="np-summary-meal-food">
        `;
        
        if (food) {
            totalCalo += food.calories;
            totalProtein += food.protein;
            totalCarbs += food.carbs;
            totalFats += food.fats;
            
            const diff = food.calories - mealCalo;
            const diffClass = Math.abs(diff) <= mealCalo * 0.2 ? 'good' : (diff > 0 ? 'over' : 'under');
            const diffText = diff > 0 ? `+${diff}` : `${diff}`;
            
            contentHtml += `
                <span class="np-summary-food-name">${food.name}</span>
                <span class="np-summary-food-calo">${food.calories} kcal</span>
                <span class="np-summary-diff ${diffClass}">${diffText}</span>
            `;
        } else {
            contentHtml += '<span class="np-summary-empty">Chưa chọn món</span>';
        }
        
        contentHtml += '</div></div>';
    }
    
    contentHtml += '</div>';
    summaryContent.innerHTML = contentHtml;
    
    // Total summary
    const targetTotal = currentPlan ? Math.round(currentPlan.CaloDuKien) : 0;
    const totalDiff = totalCalo - targetTotal;
    const totalDiffClass = Math.abs(totalDiff) <= targetTotal * 0.1 ? 'good' : (totalDiff > 0 ? 'over' : 'under');
    const totalDiffText = totalDiff > 0 ? `+${totalDiff}` : `${totalDiff}`;
    const progressPercent = targetTotal > 0 ? Math.min((totalCalo / targetTotal) * 100, 120) : 0;
    
    summaryTotal.innerHTML = `
        <div class="np-summary-progress-bar">
            <div class="np-summary-progress-fill ${totalDiffClass}" style="width: ${progressPercent}%"></div>
        </div>
        <div class="np-summary-total-row">
            <div class="np-summary-total-label">
                <i class="fa-solid fa-fire-flame-curved"></i> Tổng calo ngày
            </div>
            <div class="np-summary-total-values">
                <span class="np-summary-total-number">${totalCalo}</span>
                <span class="np-summary-total-separator">/</span>
                <span class="np-summary-total-target">${targetTotal} kcal</span>
                <span class="np-summary-total-diff ${totalDiffClass}">(${totalDiffText})</span>
            </div>
        </div>
        <div class="np-summary-macros">
            <div class="np-summary-macro">
                <span class="np-summary-macro-label">Protein</span>
                <span class="np-summary-macro-value" style="color: var(--c-prot);">${totalProtein.toFixed(1)}g</span>
            </div>
            <div class="np-summary-macro">
                <span class="np-summary-macro-label">Carbs</span>
                <span class="np-summary-macro-value" style="color: var(--c-carb);">${totalCarbs.toFixed(1)}g</span>
            </div>
            <div class="np-summary-macro">
                <span class="np-summary-macro-label">Chất béo</span>
                <span class="np-summary-macro-value" style="color: var(--c-fat);">${totalFats.toFixed(1)}g</span>
            </div>
        </div>
    `;

    // Generate adjustment suggestions if total is off
    const adjustHtml = generateAdjustmentSuggestion(totalCalo, targetTotal);
    if (adjustHtml) {
        summaryTotal.innerHTML += adjustHtml;
    }
}

function generateAdjustmentSuggestion(totalCalo, targetTotal) {
    const diff = totalCalo - targetTotal;
    const threshold = targetTotal * 0.1; // 10% tolerance
    
    if (Math.abs(diff) <= threshold) {
        // Within acceptable range
        return `
            <div class="np-adjust-box good">
                <div class="np-adjust-icon"><i class="fa-solid fa-circle-check"></i></div>
                <div class="np-adjust-content">
                    <div class="np-adjust-title">Thực đơn phù hợp!</div>
                    <div class="np-adjust-desc">Tổng calo đã chọn nằm trong khoảng cho phép (±10%) so với mục tiêu ${targetTotal} kcal/ngày.</div>
                </div>
            </div>
        `;
    }
    
    const needReduce = diff > 0;
    const absDiff = Math.abs(diff);
    
    // Find the best swap across all meals
    let bestSwap = null;
    
    for (const [mealType, config] of Object.entries(MEAL_CONFIG)) {
        const currentFood = selectedFoods[mealType];
        if (!currentFood) continue;
        
        const alternatives = mealFoodLists[mealType];
        if (!alternatives || alternatives.length < 2) continue;
        
        for (const alt of alternatives) {
            if (alt.id === currentFood.id) continue;
            
            const calChange = alt.calories - currentFood.calories;
            
            // If we need to reduce, find food with fewer calories (negative calChange)
            // If we need to increase, find food with more calories (positive calChange)
            if (needReduce && calChange >= 0) continue;
            if (!needReduce && calChange <= 0) continue;
            
            // Calculate how well this swap fixes the problem
            const newTotal = totalCalo + calChange;
            const newDiff = Math.abs(newTotal - targetTotal);
            
            if (!bestSwap || newDiff < bestSwap.newDiff) {
                bestSwap = {
                    mealType,
                    mealName: config.name,
                    mealEmoji: config.emoji,
                    currentFood: currentFood,
                    newFood: alt,
                    calChange,
                    newTotal,
                    newDiff
                };
            }
        }
    }
    
    if (!bestSwap) {
        return `
            <div class="np-adjust-box ${needReduce ? 'over' : 'under'}">
                <div class="np-adjust-icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
                <div class="np-adjust-content">
                    <div class="np-adjust-title">${needReduce ? 'Vượt' : 'Thiếu'} ${absDiff} kcal so với mục tiêu</div>
                    <div class="np-adjust-desc">Hãy thử chọn các món ${needReduce ? 'ít' : 'nhiều'} calo hơn ở các bữa để cân chỉnh.</div>
                </div>
            </div>
        `;
    }
    
    const changeText = bestSwap.calChange > 0 ? `+${bestSwap.calChange}` : `${bestSwap.calChange}`;
    const actionText = needReduce ? 'giảm' : 'tăng';
    
    return `
        <div class="np-adjust-box ${needReduce ? 'over' : 'under'}">
            <div class="np-adjust-icon"><i class="fa-solid fa-lightbulb"></i></div>
            <div class="np-adjust-content">
                <div class="np-adjust-title">
                    ${needReduce ? 'Vượt' : 'Thiếu'} <strong>${absDiff} kcal</strong> — Gợi ý điều chỉnh:
                </div>
                <div class="np-adjust-suggestion" 
                     onclick="applySwap('${bestSwap.mealType}', ${JSON.stringify(bestSwap.newFood).replace(/"/g, '&quot;')})">
                    <div class="np-swap-detail">
                        <span class="np-swap-emoji">${bestSwap.mealEmoji}</span>
                        <span class="np-swap-meal">${bestSwap.mealName}:</span>
                        <span class="np-swap-from">${bestSwap.currentFood.name} (${bestSwap.currentFood.calories} kcal)</span>
                        <i class="fa-solid fa-arrow-right"></i>
                        <span class="np-swap-to">${bestSwap.newFood.name} (${bestSwap.newFood.calories} kcal)</span>
                        <span class="np-swap-change ${needReduce ? 'reduce' : 'increase'}">${changeText} kcal</span>
                    </div>
                    <button class="np-swap-btn">
                        <i class="fa-solid fa-arrows-rotate"></i> Áp dụng
                    </button>
                </div>
            </div>
        </div>
    `;
}

window.applySwap = function(mealType, newFood) {
    selectFood(mealType, newFood);
    
    // Scroll to the summary
    setTimeout(() => {
        document.getElementById('daily-summary').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 300);
};

// ============================================
// SAVE & HISTORY
// ============================================

window.saveMealPlan = async function() {
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    if (!loggedUser || !currentPlan) return;
    
    const hasAny = Object.values(selectedFoods).some(f => f !== null);
    if (!hasAny) {
        alert('Hãy chọn ít nhất một món ăn trước khi lưu!');
        return;
    }
    
    const btn = document.getElementById('btn-save-plan');
    const status = document.getElementById('save-status');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...';
    
    let totalCalo = 0;
    for (const food of Object.values(selectedFoods)) {
        if (food) totalCalo += food.calories;
    }
    
    const payload = {
        caloDuKien: currentPlan.CaloDuKien,
        tongCaloChon: totalCalo,
        buaSang: selectedFoods.breakfast?.name || '',
        buaSangCalo: selectedFoods.breakfast?.calories || 0,
        buaTrua: selectedFoods.lunch?.name || '',
        buaTruaCalo: selectedFoods.lunch?.calories || 0,
        buaToi: selectedFoods.dinner?.name || '',
        buaToiCalo: selectedFoods.dinner?.calories || 0,
        buaPhu: selectedFoods.snack?.name || '',
        buaPhuCalo: selectedFoods.snack?.calories || 0
    };
    
    try {
        const res = await fetch(`/api/meal-plans/${loggedUser.id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (data.success) {
            status.innerHTML = '<i class="fa-solid fa-check-circle" style="color: #16a34a;"></i> Đã lưu thành công!';
            status.className = 'np-save-status show success';
            loadPlanHistory();
        } else {
            status.innerHTML = '<i class="fa-solid fa-xmark-circle" style="color: #ef4444;"></i> Lỗi: ' + data.message;
            status.className = 'np-save-status show error';
        }
    } catch (err) {
        status.innerHTML = '<i class="fa-solid fa-xmark-circle" style="color: #ef4444;"></i> Lỗi kết nối';
        status.className = 'np-save-status show error';
    }
    
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Lưu Kế Hoạch Hôm Nay';
    
    setTimeout(() => { status.className = 'np-save-status'; }, 4000);
};

async function loadPlanHistory() {
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    if (!loggedUser) return;
    
    const container = document.getElementById('plan-history-content');
    
    try {
        const res = await fetch(`/api/meal-plans/${loggedUser.id}`);
        const data = await res.json();
        
        if (data.success && data.plans.length > 0) {
            renderPlanHistory(container, data.plans);
        } else {
            container.innerHTML = `
                <div class="np-no-data">
                    <i class="fa-solid fa-calendar-xmark"></i>
                    <p>Chưa có kế hoạch nào được lưu</p>
                </div>
            `;
        }
    } catch (err) {
        console.error('Error loading plan history:', err);
        container.innerHTML = `<div class="np-no-data"><i class="fa-solid fa-exclamation-triangle"></i><p>Lỗi tải lịch sử</p></div>`;
    }
}

function renderPlanHistory(container, plans) {
    // Group by month
    const months = {};
    plans.forEach(plan => {
        const key = plan.month;
        if (!months[key]) months[key] = [];
        months[key].push(plan);
    });
    
    let html = '';
    for (const [month, monthPlans] of Object.entries(months)) {
        const [year, mon] = month.split('-');
        const monthName = `Tháng ${parseInt(mon)}/${year}`;
        
        // Monthly stats
        const avgTarget = monthPlans.reduce((s, p) => s + p.caloDuKien, 0) / monthPlans.length;
        const avgActual = monthPlans.reduce((s, p) => s + p.tongCaloChon, 0) / monthPlans.length;
        const totalDays = monthPlans.length;
        const goodDays = monthPlans.filter(p => Math.abs(p.tongCaloChon - p.caloDuKien) <= p.caloDuKien * 0.1).length;
        
        html += `
            <div class="np-month-group">
                <div class="np-month-header">
                    <div class="np-month-title">
                        <i class="fa-solid fa-calendar"></i>
                        <span>${monthName}</span>
                        <span class="np-month-count">${totalDays} ngày</span>
                    </div>
                    <div class="np-month-stats">
                        <div class="np-month-stat">
                            <span class="np-month-stat-label">TB Mục tiêu</span>
                            <span class="np-month-stat-value">${Math.round(avgTarget)} kcal</span>
                        </div>
                        <div class="np-month-stat">
                            <span class="np-month-stat-label">TB Thực tế</span>
                            <span class="np-month-stat-value">${Math.round(avgActual)} kcal</span>
                        </div>
                        <div class="np-month-stat">
                            <span class="np-month-stat-label">Đạt mục tiêu</span>
                            <span class="np-month-stat-value good">${goodDays}/${totalDays}</span>
                        </div>
                    </div>
                </div>
                <div class="np-month-plans">
        `;
        
        monthPlans.forEach(plan => {
            const diff = plan.tongCaloChon - plan.caloDuKien;
            const statusClass = Math.abs(diff) <= plan.caloDuKien * 0.1 ? 'good' : (diff > 0 ? 'over' : 'under');
            const diffText = diff > 0 ? `+${Math.round(diff)}` : `${Math.round(diff)}`;
            const date = plan.date.split(' ')[0]; // Just the date part
            const time = plan.date.split(' ')[1] || '';
            
            html += `
                <div class="np-plan-card">
                    <div class="np-plan-date">
                        <span class="np-plan-day">${date}</span>
                        <span class="np-plan-time">${time}</span>
                    </div>
                    <div class="np-plan-meals">
                        <div class="np-plan-meal"><span class="np-plan-meal-emoji">🌅</span> ${plan.buaSang || '—'} <span class="np-plan-meal-calo">${plan.buaSangCalo} kcal</span></div>
                        <div class="np-plan-meal"><span class="np-plan-meal-emoji">☀️</span> ${plan.buaTrua || '—'} <span class="np-plan-meal-calo">${plan.buaTruaCalo} kcal</span></div>
                        <div class="np-plan-meal"><span class="np-plan-meal-emoji">🌙</span> ${plan.buaToi || '—'} <span class="np-plan-meal-calo">${plan.buaToiCalo} kcal</span></div>
                        <div class="np-plan-meal"><span class="np-plan-meal-emoji">🍎</span> ${plan.buaPhu || '—'} <span class="np-plan-meal-calo">${plan.buaPhuCalo} kcal</span></div>
                    </div>
                    <div class="np-plan-total">
                        <span class="np-plan-total-number">${Math.round(plan.tongCaloChon)}</span>
                        <span class="np-plan-total-sep">/</span>
                        <span class="np-plan-total-target">${Math.round(plan.caloDuKien)}</span>
                        <span class="np-plan-diff ${statusClass}">${diffText}</span>
                    </div>
                </div>
            `;
        });
        
        html += '</div></div>';
    }
    
    container.innerHTML = html;
}

// ============================================
// NOTIFICATIONS (Moved to notifications.js)
// ============================================


// ============================================
// WEIGHT TRACKING
// ============================================

let weightChart = null;

function buildWeightMessage(mucTieu, diff) {
    const absDiff = Math.abs(diff).toFixed(1);
    if (mucTieu === 'Giảm cân') {
        if (diff < -0.3) {
            return { type: 'success', icon: '🎉',
                     title: 'Chúc mừng giảm cân thành công!',
                     desc: `Bạn đã giảm ${absDiff}kg so với lần trước. Tiếp tục duy trì kế hoạch dinh dưỡng nhé!` };
        }
        if (diff > 0.3) {
            return { type: 'warning', icon: '💪',
                     title: 'Cần cải thiện',
                     desc: `Cân nặng tăng ${absDiff}kg, ngược với mục tiêu giảm cân. Hãy xem lại lượng calo và tăng cường vận động.` };
        }
        return { type: 'info', icon: '🌱',
                 title: 'Hãy kiên trì!',
                 desc: 'Cân nặng chưa thay đổi đáng kể, tiếp tục bám sát kế hoạch để đạt mục tiêu nhé.' };
    }
    if (mucTieu === 'Tăng cân') {
        if (diff > 0.3) {
            return { type: 'success', icon: '🎉',
                     title: 'Chúc mừng tăng cân thành công!',
                     desc: `Bạn đã tăng ${absDiff}kg so với lần trước. Tiếp tục bổ sung dinh dưỡng đầy đủ nhé!` };
        }
        if (diff < -0.3) {
            return { type: 'warning', icon: '💪',
                     title: 'Cần cải thiện',
                     desc: `Cân nặng giảm ${absDiff}kg, ngược với mục tiêu tăng cân. Hãy bổ sung thêm calo và protein.` };
        }
        return { type: 'info', icon: '🌱',
                 title: 'Hãy kiên trì!',
                 desc: 'Cân nặng chưa thay đổi đáng kể, tiếp tục bám sát kế hoạch để đạt mục tiêu nhé.' };
    }
    // Duy trì
    if (Math.abs(diff) <= 1.0) {
        return { type: 'success', icon: '🎯',
                 title: 'Duy trì tốt!',
                 desc: `Cân nặng dao động ${absDiff}kg, vẫn nằm trong khoảng duy trì lành mạnh. Cố lên nhé!` };
    }
    return { type: 'warning', icon: '⚠️',
             title: 'Cần điều chỉnh',
             desc: `Cân nặng biến động ${absDiff}kg, vượt khoảng duy trì cho phép. Hãy xem lại kế hoạch dinh dưỡng.` };
}

function initWeightModal() {
    const overlay = document.getElementById('weight-modal-overlay');
    const closeBtn = document.getElementById('weight-modal-close');
    const okBtn = document.getElementById('weight-modal-ok');
    if (!overlay) return;

    const hide = () => overlay.classList.add('hidden');
    closeBtn?.addEventListener('click', hide);
    okBtn?.addEventListener('click', hide);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) hide();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !overlay.classList.contains('hidden')) hide();
    });
}

function showWeightChangeModal(wc) {
    const overlay = document.getElementById('weight-modal-overlay');
    if (!overlay) return;

    const msg = buildWeightMessage(wc.muc_tieu, wc.diff);
    const modal = document.getElementById('weight-modal');

    document.getElementById('weight-modal-icon').textContent = msg.icon;
    document.getElementById('weight-modal-title').textContent = msg.title;
    document.getElementById('weight-modal-desc').textContent = msg.desc;
    document.getElementById('weight-modal-old-val').textContent = `${wc.old_weight.toFixed(1)} kg`;
    document.getElementById('weight-modal-new-val').textContent = `${wc.new_weight.toFixed(1)} kg`;

    const diffEl = document.getElementById('weight-modal-diff');
    const diffSign = wc.diff > 0 ? '+' : '';
    diffEl.textContent = `${diffSign}${wc.diff.toFixed(1)} kg`;
    diffEl.className = 'np-weight-modal-diff';
    if (msg.type === 'success') diffEl.classList.add('success');
    else if (msg.type === 'warning') diffEl.classList.add('warning');
    else diffEl.classList.add('info');

    // Apply modal theme color
    modal.classList.remove('np-modal-success', 'np-modal-warning', 'np-modal-info');
    modal.classList.add(`np-modal-${msg.type}`);

    overlay.classList.remove('hidden');
}

async function loadWeightHistory() {
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    if (!loggedUser) return;

    const section = document.getElementById('weight-history-section');
    const listEl = document.getElementById('weight-history-list');
    if (!section || !listEl) return;

    try {
        const res = await fetch(`/api/weight-history/${loggedUser.id}`);
        const data = await res.json();
        const history = (data.success && data.history) ? data.history : [];

        if (history.length === 0) {
            section.style.display = 'none';
            return;
        }
        section.style.display = '';

        // Stats
        const first = history[0];
        const last = history[history.length - 1];
        const totalChange = last.can_nang - first.can_nang;
        const changeSign = totalChange > 0 ? '+' : '';

        document.getElementById('wh-current').textContent = last.can_nang.toFixed(1);
        const changeEl = document.getElementById('wh-change');
        changeEl.textContent = `${changeSign}${totalChange.toFixed(1)}`;
        changeEl.classList.remove('positive', 'negative');
        if (totalChange > 0.1) changeEl.classList.add('positive');
        else if (totalChange < -0.1) changeEl.classList.add('negative');
        document.getElementById('wh-count').textContent = history.length;

        // Chart
        renderWeightChart(history);

        // List (latest first, top 8)
        const reversed = [...history].reverse().slice(0, 8);
        listEl.innerHTML = `
            <table class="np-weight-table">
                <thead>
                    <tr>
                        <th>Thời gian</th>
                        <th>Cân nặng</th>
                        <th>BMI</th>
                        <th>Thể trạng</th>
                    </tr>
                </thead>
                <tbody>
                    ${reversed.map((h, idx) => {
                        const prev = reversed[idx + 1];
                        let diffHtml = '';
                        if (prev) {
                            const d = h.can_nang - prev.can_nang;
                            if (Math.abs(d) >= 0.1) {
                                const sign = d > 0 ? '+' : '';
                                const cls = d > 0 ? 'positive' : 'negative';
                                diffHtml = ` <span class="np-weight-table-diff ${cls}">${sign}${d.toFixed(1)}</span>`;
                            }
                        }
                        const color = h.phan_loai ? (BMI_META[h.phan_loai]?.color || '#888') : '#888';
                        return `
                            <tr>
                                <td>${formatDateTime(h.thoi_gian)}</td>
                                <td><strong>${h.can_nang.toFixed(1)} kg</strong>${diffHtml}</td>
                                <td>${h.bmi !== null ? h.bmi.toFixed(1) : '--'}</td>
                                <td><span class="np-weight-cat-badge" style="background:${color}">${h.phan_loai || '--'}</span></td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    } catch (err) {
        console.error('Error loading weight history:', err);
        listEl.innerHTML = `<div class="np-no-data"><i class="fa-solid fa-exclamation-triangle"></i><p>Lỗi tải lịch sử cân nặng</p></div>`;
    }
}

function formatDateTime(dtStr) {
    if (!dtStr) return '--';
    try {
        const d = new Date(dtStr.replace(' ', 'T'));
        return d.toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return dtStr;
    }
}

function renderWeightChart(history) {
    const canvas = document.getElementById('weight-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    const labels = history.map(h => {
        const d = new Date(h.thoi_gian.replace(' ', 'T'));
        return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
    });
    const weights = history.map(h => h.can_nang);
    const categories = history.map(h => h.phan_loai || '--');
    const pointColors = history.map(h => BMI_META[h.phan_loai]?.color || '#22c55e');

    if (weightChart) {
        weightChart.destroy();
        weightChart = null;
    }

    weightChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Cân nặng (kg)',
                data: weights,
                borderColor: '#22c55e',
                backgroundColor: 'rgba(34, 197, 94, 0.12)',
                borderWidth: 3,
                pointBackgroundColor: pointColors,
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8,
                tension: 0.35,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const i = ctx.dataIndex;
                            return [
                                `Cân nặng: ${weights[i].toFixed(1)} kg`,
                                `Thể trạng: ${categories[i]}`
                            ];
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    title: { display: true, text: 'kg' },
                    grid: { color: 'rgba(0,0,0,0.06)' }
                },
                x: {
                    grid: { display: false }
                }
            }
        }
    });
}

// ============================================
// PREMIUM ACCOUNT RESTRICTIONS
// ============================================

function isUserPremium() {
    const user = JSON.parse(localStorage.getItem('smartfood_user'));
    return user && user.account_type === 'premium';
}

function createLockOverlay(message, small = false) {
    const overlay = document.createElement('div');
    overlay.className = 'premium-lock-overlay';
    overlay.innerHTML = `
        <i class="fa-solid fa-lock lock-icon" style="font-size:${small ? '22px' : '28px'}"></i>
        <span class="lock-text">${message}</span>
        <button class="lock-cta" onclick="window.location.href='/?upgrade=true'">
            <i class="fa-solid fa-crown"></i> Nâng cấp Premium
        </button>
    `;
    return overlay;
}

function applyPremiumLocks() {
    if (isUserPremium()) return;

    // Lock BMI assessment detail
    setTimeout(() => {
        const bmiAssessment = document.getElementById('bmi-assessment-section');
        if (bmiAssessment) {
            // Lock the entire grid
            const grid = bmiAssessment.querySelector('.np-bmi-grid');
            if (grid && !grid.classList.contains('premium-lock-wrapper')) {
                grid.classList.add('premium-lock-wrapper', 'locked');
                grid.appendChild(createLockOverlay('Nâng cấp Premium để xem đánh giá thể trạng chi tiết', false));
            }
        }
    }, 300);
}

function applyMealSuggestionLocks(container, mealType, totalCount) {
    if (isUserPremium()) return;
    
    // For free users: only show first 3 suggestions, lock the rest
    const moreList = document.getElementById(`more-${mealType}`);
    if (moreList) {
        const cards = moreList.querySelectorAll('.np-food-card');
        // Free users can see max 2 more (total 3 with best match)
        cards.forEach((card, index) => {
            if (index >= 2) {
                card.classList.add('premium-lock-wrapper', 'locked');
                card.style.position = 'relative';
                card.appendChild(createLockOverlay('Nâng cấp để xem thêm đề xuất', true));
            }
        });
    }
}

// Add premium upgrade banner on nutrition page
function addNutritionUpgradeBanner() {
    if (isUserPremium()) return;
    
    const mainContainer = document.querySelector('.nutrition-container') || document.querySelector('main');
    if (!mainContainer) return;
    
    // Check if banner already exists
    if (document.getElementById('nutrition-upgrade-banner')) return;
    
    const banner = document.createElement('div');
    banner.id = 'nutrition-upgrade-banner';
    banner.className = 'nutrition-upgrade-banner';
    banner.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:center;">
            <span style="display:flex;align-items:center;gap:6px;">
                <i class="fa-solid fa-crown" style="color:#f59e0b;"></i>
                <strong>Tài khoản miễn phí</strong> — Một số tính năng bị giới hạn
            </span>
            <button onclick="window.location.href='/?upgrade=true'" style="
                padding:6px 16px;border-radius:20px;border:none;
                background:linear-gradient(135deg,#f59e0b,#d97706);
                color:white;font-size:12px;font-weight:700;cursor:pointer;
                font-family:inherit;transition:all 0.2s;
            ">Nâng cấp Premium — 2.000đ</button>
        </div>
    `;
    banner.style.cssText = `
        background: rgba(245,158,11,0.06);
        border: 1px solid rgba(245,158,11,0.2);
        border-radius: 12px;
        padding: 12px 20px;
        margin-bottom: 20px;
        text-align: center;
        font-size: 14px;
        color: var(--text-secondary);
    `;
    
    mainContainer.prepend(banner);
}

// Initialize on load
document.addEventListener('DOMContentLoaded', addNutritionUpgradeBanner);
