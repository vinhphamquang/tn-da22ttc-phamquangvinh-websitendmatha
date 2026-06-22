/* ============================================
   SMART FOOD ANALYSIS — Main Script
   SPA Routing + Upload + API + Animations
   ============================================ */

// ---- SPA ROUTING ----
const pages = document.querySelectorAll('.page');
const navLinks = document.querySelectorAll('.nav-link');
const navToggle = document.getElementById('nav-toggle');
const navLinksContainer = document.getElementById('nav-links');
const navbar = document.getElementById('navbar');

const PAGE_LEAVE_MS = 220;
let _pageSwapTimer = null;

function navigateTo(pageId) {
    const target = document.getElementById('page-' + pageId);
    if (!target) return;

    const current = document.querySelector('.page.active');

    // Always sync nav-link active state and close mobile menu immediately.
    navLinks.forEach(l => {
        l.classList.toggle('active', l.dataset.page === pageId);
    });
    navLinksContainer.classList.remove('open');

    // Clicking the active page again — no-op
    if (current === target) return;

    const commit = () => {
        pages.forEach(p => p.classList.remove('active', 'is-leaving'));
        target.classList.add('active');
        window.scrollTo({ top: 0 });
        initRevealAnimations();
    };

    if (_pageSwapTimer) { clearTimeout(_pageSwapTimer); _pageSwapTimer = null; }

    if (current && current !== target) {
        // Fade out current section, then swap in target.
        current.classList.remove('active');
        current.classList.add('is-leaving');
        _pageSwapTimer = setTimeout(() => {
            _pageSwapTimer = null;
            commit();
        }, PAGE_LEAVE_MS);
    } else {
        commit();
    }
}

function handleHashChange() {
    const hash = window.location.hash.replace('#', '') || 'intro';

    if(hash === 'profile') {
        const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
        if(!loggedUser) {
            window.location.hash = 'intro';
            return;
        }
    }

    navigateTo(hash);
    
    if(hash === 'profile') {
        initProfilePage();
    }
}

window.addEventListener('hashchange', handleHashChange);
window.addEventListener('DOMContentLoaded', handleHashChange);

// Nav link clicks
navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        // Let the hash change handle page switching
        const page = link.dataset.page;
        if (page) {
            window.location.hash = page;
        }
    });
});

// Hero CTA button
const heroCta = document.getElementById('hero-cta');
if (heroCta) {
    heroCta.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.hash = 'analyze';
    });
}

// Mobile toggle
if (navToggle) {
    navToggle.addEventListener('click', () => {
        navLinksContainer.classList.toggle('open');
    });
}

// Navbar scroll effect
window.addEventListener('scroll', () => {
    if (window.scrollY > 30) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// ---- FOOD BANNER SLIDER ----
function initFoodSlider() {
    const sliderTrack = document.getElementById('slider-track');
    const slides = document.querySelectorAll('.slide');
    const prevBtn = document.getElementById('slider-prev');
    const nextBtn = document.getElementById('slider-next');
    const dots = document.querySelectorAll('.dot');
    
    if (!sliderTrack || slides.length === 0) return;
    
    let currentSlide = 0;
    const totalSlides = slides.length;
    let autoSlideInterval;
    
    function goToSlide(index) {
        // Remove active class from all slides
        slides.forEach(slide => slide.classList.remove('active'));
        dots.forEach(dot => dot.classList.remove('active'));
        
        // Add active class to current slide
        currentSlide = index;
        slides[currentSlide].classList.add('active');
        dots[currentSlide].classList.add('active');
        
        // Move slider track
        sliderTrack.style.transform = `translateX(-${currentSlide * 100}%)`;
    }
    
    function nextSlide() {
        const next = (currentSlide + 1) % totalSlides;
        goToSlide(next);
    }
    
    function prevSlide() {
        const prev = (currentSlide - 1 + totalSlides) % totalSlides;
        goToSlide(prev);
    }
    
    function startAutoSlide() {
        autoSlideInterval = setInterval(nextSlide, 5000); // Change slide every 5 seconds
    }
    
    function stopAutoSlide() {
        clearInterval(autoSlideInterval);
    }
    
    // Event listeners
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            nextSlide();
            stopAutoSlide();
            startAutoSlide(); // Restart auto slide after manual interaction
        });
    }
    
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            prevSlide();
            stopAutoSlide();
            startAutoSlide();
        });
    }
    
    dots.forEach((dot, index) => {
        dot.addEventListener('click', () => {
            goToSlide(index);
            stopAutoSlide();
            startAutoSlide();
        });
    });
    
    // Pause auto slide on hover
    sliderTrack.addEventListener('mouseenter', stopAutoSlide);
    sliderTrack.addEventListener('mouseleave', startAutoSlide);
    
    // Start auto slide
    startAutoSlide();
}

// ---- SCROLL REVEAL ANIMATIONS ----
function initRevealAnimations() {
    const reveals = document.querySelectorAll('.reveal');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    reveals.forEach(el => {
        el.classList.remove('visible');
        observer.observe(el);
    });
}

// ---- UPLOAD & ANALYSIS LOGIC ----
function initAnalyzePage() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadContent = document.getElementById('upload-content');
    const previewContainer = document.getElementById('image-preview-container');
    const previewImg = document.getElementById('preview-img');
    const removeBtn = document.getElementById('remove-btn');
    const analyzeBtn = document.getElementById('analyze-btn');
    const loading = document.getElementById('loading');
    const resultSection = document.getElementById('result-section');

    if (!dropZone) return;

    let currentFile = null;
    let stream = null;
    let currentMode = 'upload'; // 'upload' or 'camera'

    const modeUploadBtn = document.getElementById('mode-upload-btn');
    const modeCameraBtn = document.getElementById('mode-camera-btn');
    const cameraSection = document.getElementById('camera-section');
    const cameraVideo = document.getElementById('camera-video');
    const cameraCanvas = document.getElementById('camera-canvas');
    const captureBtn = document.getElementById('capture-btn');

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }
    }

    async function startCamera() {
        try {
            // Thử mở camera sau (environment)
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
            cameraVideo.srcObject = stream;
        } catch (err) {
            console.warn("Không tìm thấy camera sau, thử camera mặc định...", err);
            try {
                // Fallback: Mở camera bất kỳ (thường là camera trước trên laptop)
                stream = await navigator.mediaDevices.getUserMedia({ video: true });
                cameraVideo.srcObject = stream;
            } catch (fallbackErr) {
                console.error("Camera error:", fallbackErr);
                alert("Lỗi truy cập Camera: " + fallbackErr.name + " - " + fallbackErr.message + "\nVui lòng kiểm tra xem camera có đang bị ứng dụng khác sử dụng không.");
                if (modeUploadBtn) modeUploadBtn.click();
            }
        }
    }

    modeUploadBtn?.addEventListener('click', () => {
        currentMode = 'upload';
        modeUploadBtn.classList.add('btn-primary');
        modeUploadBtn.classList.remove('btn-outline');
        modeUploadBtn.style.color = '';
        modeUploadBtn.style.borderColor = '';

        modeCameraBtn.classList.add('btn-outline');
        modeCameraBtn.classList.remove('btn-primary');
        modeCameraBtn.style.color = 'var(--text-main)';
        modeCameraBtn.style.borderColor = 'var(--glass-border)';

        cameraSection.classList.add('hidden');
        if (!currentFile) {
            uploadContent.classList.remove('hidden');
        }
        stopCamera();
    });

    modeCameraBtn?.addEventListener('click', () => {
        currentMode = 'camera';
        modeCameraBtn.classList.add('btn-primary');
        modeCameraBtn.classList.remove('btn-outline');
        modeCameraBtn.style.color = '';
        modeCameraBtn.style.borderColor = '';

        modeUploadBtn.classList.add('btn-outline');
        modeUploadBtn.classList.remove('btn-primary');
        modeUploadBtn.style.color = 'var(--text-main)';
        modeUploadBtn.style.borderColor = 'var(--glass-border)';

        uploadContent.classList.add('hidden');
        previewContainer.classList.add('hidden');
        resultSection.classList.add('hidden');
        
        currentFile = null;
        fileInput.value = '';
        previewImg.src = '';
        
        cameraSection.classList.remove('hidden');
        startCamera();
    });

    captureBtn?.addEventListener('click', () => {
        if (!stream) return;
        
        const context = cameraCanvas.getContext('2d');
        cameraCanvas.width = cameraVideo.videoWidth;
        cameraCanvas.height = cameraVideo.videoHeight;
        
        context.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
        
        cameraCanvas.toBlob((blob) => {
            if (blob) {
                const file = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
                handleFiles([file]);
                stopCamera();
                cameraSection.classList.add('hidden');
            }
        }, 'image/jpeg', 0.9);
    });

    // Drag & Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, e => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-active'), false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-active'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', function () {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length > 0) {
            currentFile = files[0];
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImg.src = e.target.result;
                uploadContent.classList.add('hidden');
                previewContainer.classList.remove('hidden');
                resultSection.classList.add('hidden');
            };
            reader.readAsDataURL(currentFile);
        }
    }

    removeBtn.addEventListener('click', () => {
        currentFile = null;
        fileInput.value = '';
        previewImg.src = '';
        previewContainer.classList.add('hidden');
        resultSection.classList.add('hidden');
        
        if (currentMode === 'camera') {
            cameraSection.classList.remove('hidden');
            startCamera();
        } else {
            uploadContent.classList.remove('hidden');
        }
    });

    analyzeBtn.addEventListener('click', async () => {
        if (!currentFile) return;

        const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));

        // Kiểm tra quota cho khách vãng lai
        if (!loggedUser) {
            let guestCount = parseInt(localStorage.getItem('guest_analysis_count')) || 0;
            if (guestCount >= 5) {
                alert('Bạn đã sử dụng hết 5 lượt phân tích dành cho khách vãng lai.\nVui lòng đăng nhập hoặc đăng ký để tiếp tục sử dụng miễn phí!');
                document.getElementById('auth-modal').classList.remove('hidden');
                return;
            }
            localStorage.setItem('guest_analysis_count', guestCount + 1);
            updatePremiumUI();
        }

        // Kiểm tra quota trước khi phân tích (cho user thường)
        if (loggedUser && loggedUser.account_type !== 'premium') {
            try {
                const quotaRes = await fetch(`/api/user/${loggedUser.id}/quota`);
                const quotaData = await quotaRes.json();
                if (quotaData.success && !quotaData.quota.allowed) {
                    document.getElementById('quota-exceeded-modal').style.display = 'flex';
                    return;
                }
                // Cập nhật quota counter
                updateQuotaCounter(quotaData.quota);
            } catch(e) { console.warn('Quota check failed:', e); }
        }

        // Show loading
        previewContainer.classList.add('hidden');
        loading.classList.remove('hidden');
        resultSection.classList.add('hidden');
        
        let loaderText = loading.querySelector('.loader-text');
        if (loaderText) {
            loaderText.innerHTML = 'AI đang nhận diện hình ảnh<span class="dots"></span>';
        }
        
        // Update loading text after 3 seconds
        let loadingTimer = setTimeout(() => {
            if (loaderText) {
                loaderText.innerHTML = 'Đang xử lý dữ liệu, vui lòng chờ<span class="dots"></span>';
            }
        }, 3000);
        
        // Update again after 6 seconds (for AI generation)
        let loadingTimer2 = setTimeout(() => {
            if (loaderText) {
                loaderText.innerHTML = 'Đang phân tích món ăn bằng AI, có thể mất thêm vài giây<span class="dots"></span>';
            }
        }, 6000);

        const formData = new FormData();
        formData.append('file', currentFile);
        
        if (loggedUser) {
            formData.append('user_id', loggedUser.id);
        }

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });

            // Kiểm tra nếu server trả về lỗi (HTML thay vì JSON)
            const contentType = response.headers.get('content-type') || '';
            if (!contentType.includes('application/json')) {
                throw new Error(`Server trả về lỗi ${response.status}. Kiểm tra console Backend.`);
            }

            const data = await response.json();

            clearTimeout(loadingTimer);
            clearTimeout(loadingTimer2);
            loading.classList.add('hidden');
            previewContainer.classList.remove('hidden');

            if (data.success) {
                showResult(data);
                // Cập nhật quota sau khi phân tích thành công
                if (loggedUser && loggedUser.account_type !== 'premium') {
                    fetch(`/api/user/${loggedUser.id}/quota`).then(r=>r.json()).then(q=>{
                        if(q.success) updateQuotaCounter(q.quota);
                    }).catch(()=>{});
                }
            } else if (data.quota_exceeded) {
                // Hết lượt nhận diện
                document.getElementById('quota-exceeded-modal').style.display = 'flex';
            } else if (data.is_food === false) {
                // Hình ảnh không phải món ăn
                showNotFoodError(data.message, data.suggestion);
            } else {
                showError(
                    data.message || 'Lỗi từ Backend Server!',
                    data.suggestion || null
                );
            }

        } catch (err) {
            console.error('Fetch error:', err);
            clearTimeout(loadingTimer);
            clearTimeout(loadingTimer2);
            loading.classList.add('hidden');
            previewContainer.classList.remove('hidden');
            showError('Lỗi kết nối tới Server: ' + err.message);
        }
    });

    // ---- COMMENT / FEEDBACK SYSTEM ----
    const commentInput = document.getElementById('comment-input');
    const charCount = document.getElementById('comment-char-count');
    const submitBtn = document.getElementById('btn-submit-comment');

    if (commentInput) {
        commentInput.addEventListener('input', () => {
            const len = commentInput.value.length;
            charCount.textContent = `${len}/1000`;
            submitBtn.disabled = len === 0;
        });
    }

    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const content = commentInput.value.trim();
            if (!content || !window._currentHistoryId) return;
            
            const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
            if (!loggedUser) {
                alert('Vui lòng đăng nhập để gửi bình luận');
                return;
            }

            submitBtn.disabled = true;
            const origHTML = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang gửi...';

            try {
                const res = await fetch('/api/comments', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        history_id: window._currentHistoryId,
                        user_id: loggedUser.id,
                        content: content
                    })
                });
                const data = await res.json();
                if (data.success) {
                    commentInput.value = '';
                    charCount.textContent = '0/1000';
                    loadComments(window._currentHistoryId);
                } else {
                    alert(data.message || 'Lỗi khi gửi bình luận');
                }
            } catch (e) {
                console.error('Comment submit error:', e);
                alert('Lỗi kết nối server');
            }
            submitBtn.innerHTML = origHTML;
            submitBtn.disabled = false;
        });
    }
}

// Helper: safely set textContent (prevents crash if element missing)
function _setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}
function _setStyle(id, prop, value) {
    const el = document.getElementById(id);
    if (el) el.style[prop] = value;
}

function showResult(data) {
    const resultSection = document.getElementById('result-section');
    const sysMsg = document.getElementById('sys-msg');

    resultSection.classList.remove('hidden');
    sysMsg.textContent = '';
    sysMsg.classList.remove('visible');


    if (data.food_data) {
        document.getElementById('food-name').textContent = data.food_data.name;
        
        // Mô tả: ưu tiên description từ data, nhưng thêm ghi chú nếu dữ liệu từ AI
        const descEl = document.getElementById('food-desc');
        if (data.is_new && !data.found_in_db) {
            descEl.textContent = data.food_data.description || 'Dữ liệu sơ bộ từ AI (Chưa có dữ liệu ánh xạ món ăn này trong Database).';
        } else {
            descEl.textContent = data.food_data.description || 'Chưa có thông tin mô tả chi tiết.';
        }
        
        document.getElementById('val-cal').textContent = data.food_data.calories;
        document.getElementById('val-prot').textContent = data.food_data.proteins;
        document.getElementById('val-carb').textContent = data.food_data.carbs;
        document.getElementById('val-fat').textContent = data.food_data.fats;

        // Hiển thị thông báo hệ thống nếu có
        if (data.message) {
            sysMsg.textContent = data.message;
            sysMsg.classList.add('visible');
        }

        // Ingredients
        const ingredientsList = document.getElementById('ingredients-list');
        const ingredientsAccordion = document.getElementById('ingredients-accordion');
        ingredientsList.innerHTML = '';

        if (data.food_data.ingredients && data.food_data.ingredients.length > 0) {
            ingredientsAccordion.style.display = 'block';
            data.food_data.ingredients.forEach(item => {
                const li = document.createElement('li');
                li.textContent = `${item.TenNguyenLieu} — ${item.SoLuong}`;
                ingredientsList.appendChild(li);
            });
        } else {
            ingredientsAccordion.style.display = 'none';
        }

        // Recipe
        const recipeInstructions = document.getElementById('recipe-instructions');
        const recipeTime = document.getElementById('recipe-time');
        const recipeAccordion = document.getElementById('recipe-accordion');

        if (data.food_data.recipe_instructions) {
            recipeAccordion.style.display = 'block';
            recipeInstructions.textContent = data.food_data.recipe_instructions;
            
            if (data.food_data.recipe_time) {
                recipeTime.textContent = `⏱ ${data.food_data.recipe_time} phút`;
            } else {
                recipeTime.textContent = '';
            }
        } else {
            recipeAccordion.style.display = 'none';
        }
    } else {
        // API recognized but no DB match
        document.getElementById('food-name').textContent = data.predicted_class_name || 'Không xác định';
        document.getElementById('food-desc').textContent = 'Dữ liệu sơ bộ từ AI (Chưa có dữ liệu ánh xạ món ăn này trong Database).';

        if (data.message) {
            sysMsg.textContent = data.message;
            sysMsg.classList.add('visible');
        }

        ['val-cal', 'val-prot', 'val-carb', 'val-fat'].forEach(id => {
            document.getElementById(id).textContent = '--';
        });
        
        // Hide recipe and ingredients accordions
        document.getElementById('ingredients-accordion').style.display = 'none';
        document.getElementById('recipe-accordion').style.display = 'none';
    }

    // Health Recommendation Rendering
    const recBox = document.getElementById('health-recommendation-box');
    if (data.health_recommendation && recBox) {
        document.getElementById('rec-bmi').textContent = data.health_recommendation.bmi;
        document.getElementById('rec-bmi-cat').textContent = data.health_recommendation.bmi_category;
        const statusSpan = document.getElementById('rec-status');
        statusSpan.textContent = data.health_recommendation.recommendation;
        document.getElementById('rec-reason').textContent = data.health_recommendation.reason;
        
        // Color coding for status
        statusSpan.style.color = "var(--text-main)";
        if (data.health_recommendation.recommendation.includes("Hạn chế")) {
            statusSpan.style.color = "var(--c-fat)";
            statusSpan.style.background = "rgba(239, 68, 68, 0.1)";
        } else if (data.health_recommendation.recommendation.includes("Nên ăn")) {
            statusSpan.style.color = "var(--c-carb)";
            statusSpan.style.background = "rgba(34, 197, 94, 0.1)";
        } else {
            statusSpan.style.color = "var(--primary)";
            statusSpan.style.background = "rgba(249, 115, 22, 0.1)";
        }
        
        recBox.style.display = 'block';
    } else if (recBox) {
        recBox.style.display = 'none';
    }

    // Plan Advice Rendering (Kế hoạch dinh dưỡng)
    const planBox = document.getElementById('plan-advice-box');
    const planAdvice = data.health_recommendation?.plan_advice;
    if (planAdvice && planBox) {
        const iconEl = document.getElementById('plan-advice-icon');
        const statusEl = document.getElementById('plan-advice-status');
        const msgEl = document.getElementById('plan-advice-message');
        const consumedEl = document.getElementById('plan-consumed');
        const totalEl = document.getElementById('plan-total');
        const fillEl = document.getElementById('plan-progress-fill');
        const foodEl = document.getElementById('plan-progress-food');

        // Status mapping
        const statusMap = {
            'phu_hop': { text: '✅ Phù hợp', cls: 'plan-status-good', color: '#22c55e' },
            'an_it': { text: '⚠️ Ăn vừa phải', cls: 'plan-status-warn', color: '#f59e0b' },
            'khong_nen': { text: '❌ Không nên ăn', cls: 'plan-status-bad', color: '#ef4444' }
        };
        const st = statusMap[planAdvice.plan_status] || statusMap['an_it'];

        statusEl.textContent = st.text;
        statusEl.className = 'plan-advice-status ' + st.cls;
        msgEl.textContent = planAdvice.plan_message;
        consumedEl.textContent = planAdvice.plan_consumed_calo;
        totalEl.textContent = planAdvice.plan_total_calo;

        // Progress bar
        const total = planAdvice.plan_total_calo || 1;
        const consumedPct = Math.min(100, (planAdvice.plan_consumed_calo / total) * 100);
        const foodPct = Math.min(100 - consumedPct, (planAdvice.food_calo / total) * 100);

        planBox.style.borderLeftColor = st.color;
        iconEl.style.background = st.color + '20';
        iconEl.querySelector('i').style.color = st.color;

        setTimeout(() => {
            fillEl.style.width = consumedPct + '%';
            foodEl.style.width = foodPct + '%';
            foodEl.style.left = consumedPct + '%';
        }, 200);

        planBox.style.display = '';
    } else if (planBox) {
        planBox.style.display = 'none';
    }
    // Show food action buttons (Đánh dấu đã ăn / Thử món khác)
    const foodActionsEl = document.getElementById('analysis-food-actions');
    const loggedForActions = JSON.parse(localStorage.getItem('smartfood_user'));
    if (foodActionsEl && loggedForActions && data.food_data && data.history_id) {
        foodActionsEl.style.display = '';
        // Reset button state
        const markBtn = document.getElementById('btn-mark-eaten');
        if (markBtn) {
            markBtn.disabled = false;
            markBtn.classList.remove('eaten');
            markBtn.innerHTML = '<i class="fa-solid fa-utensils"></i><span>Đánh dấu đã ăn</span>';
        }
        // Store data for marking
        window._currentFoodHistoryId = data.history_id;
        window._currentFoodCalories = data.food_data.calories || 0;
    } else if (foodActionsEl) {
        foodActionsEl.style.display = 'none';
    }

    // Initialize accordion functionality
    initAccordion();

    // Show comment section if logged in
    const commentSection = document.getElementById('user-comment-section');
    const loggedForComment = JSON.parse(localStorage.getItem('smartfood_user'));
    
    if (commentSection && loggedForComment && data.history_id) {
        window._currentHistoryId = data.history_id;
        commentSection.style.display = '';
        // Reset form
        const cInput = document.getElementById('comment-input');
        if (cInput) cInput.value = '';
        const cCount = document.getElementById('comment-char-count');
        if (cCount) cCount.textContent = '0/1000';
        const cBtn = document.getElementById('btn-submit-comment');
        if (cBtn) cBtn.disabled = true;
        // Load existing comments
        loadComments(data.history_id);
    } else if (commentSection) {
        commentSection.style.display = 'none';
    }

    // Scroll result into view
    resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ---- MARK AS EATEN ----
function markAsEaten() {
    const historyId = window._currentFoodHistoryId;
    if (!historyId) {
        if (typeof window.appToast === 'function') {
            window.appToast('Không có dữ liệu để đánh dấu', 'error');
        }
        return;
    }

    const btn = document.getElementById('btn-mark-eaten');
    if (!btn || btn.disabled) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Đang xử lý...</span>';

    fetch(`/api/history/${historyId}/mark-eaten`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Update button to "eaten" state
            btn.classList.add('eaten');
            btn.innerHTML = '<i class="fa-solid fa-circle-check"></i><span>Đã đánh dấu ăn ✓</span>';

            // Update plan advice progress bar if visible
            const planBox = document.getElementById('plan-advice-box');
            if (planBox && planBox.style.display !== 'none') {
                const foodCalo = window._currentFoodCalories || 0;
                const consumedEl = document.getElementById('plan-consumed');
                const fillEl = document.getElementById('plan-progress-fill');
                const totalEl = document.getElementById('plan-total');

                if (consumedEl && fillEl && totalEl) {
                    const oldConsumed = parseInt(consumedEl.textContent) || 0;
                    const newConsumed = oldConsumed + parseInt(foodCalo);
                    const total = parseInt(totalEl.textContent) || 1;

                    consumedEl.textContent = newConsumed;

                    const newPct = Math.min(100, (newConsumed / total) * 100);
                    fillEl.style.width = newPct + '%';

                    // Remove food segment since it's now part of consumed
                    const foodEl = document.getElementById('plan-progress-food');
                    if (foodEl) {
                        foodEl.style.width = '0%';
                    }
                }
            }

            if (typeof window.appToast === 'function') {
                window.appToast('Đã đánh dấu món ăn đã ăn! Calo được cộng vào kế hoạch.', 'success', 3000);
            }
        } else {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-utensils"></i><span>Đánh dấu đã ăn</span>';
            if (typeof window.appToast === 'function') {
                window.appToast(data.message || 'Lỗi khi đánh dấu', 'error');
            }
        }
    })
    .catch(err => {
        console.error('Error marking as eaten:', err);
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-utensils"></i><span>Đánh dấu đã ăn</span>';
        if (typeof window.appToast === 'function') {
            window.appToast('Lỗi kết nối server', 'error');
        }
    });
}

// ---- TRY ANOTHER FOOD ----
function tryAnotherFood() {
    // Hide result section
    const resultSection = document.getElementById('result-section');
    if (resultSection) resultSection.classList.add('hidden');

    // Hide food action buttons
    const foodActions = document.getElementById('analysis-food-actions');
    if (foodActions) foodActions.style.display = 'none';

    // Reset sys message
    const sysMsg = document.getElementById('sys-msg');
    if (sysMsg) {
        sysMsg.textContent = '';
        sysMsg.classList.remove('visible');
    }

    // Reset image preview
    const previewContainer = document.getElementById('image-preview-container');
    const uploadContent = document.getElementById('upload-content');
    const fileInput = document.getElementById('file-input');
    const previewImg = document.getElementById('preview-img');
    const cameraSection = document.getElementById('camera-section');
    const modeCameraBtn = document.getElementById('mode-camera-btn');

    if (previewContainer) previewContainer.classList.add('hidden');
    if (fileInput) fileInput.value = '';
    if (previewImg) previewImg.src = '';

    // Check current mode and restore appropriate view
    if (modeCameraBtn && modeCameraBtn.classList.contains('btn-primary')) {
        if (cameraSection) cameraSection.classList.remove('hidden');
    } else {
        if (uploadContent) uploadContent.classList.remove('hidden');
    }

    // Clear stored data
    window._currentFoodHistoryId = null;
    window._currentFoodCalories = null;

    // Scroll back to upload zone
    const dropZone = document.getElementById('drop-zone');
    if (dropZone) {
        dropZone.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function initAccordion() {
    const accordionHeaders = document.querySelectorAll('.accordion-header');
    
    accordionHeaders.forEach(header => {
        // Remove old listeners by cloning
        const newHeader = header.cloneNode(true);
        header.parentNode.replaceChild(newHeader, header);
        
        newHeader.addEventListener('click', function() {
            const accordionItem = this.parentElement;
            const isActive = accordionItem.classList.contains('active');
            
            // Close all accordions
            document.querySelectorAll('.accordion-item').forEach(item => {
                item.classList.remove('active');
            });
            
            // Open clicked accordion if it wasn't active
            if (!isActive) {
                accordionItem.classList.add('active');
            }
        });
    });
}


function showError(message, suggestion = null) {
    const sysMsg = document.getElementById('sys-msg');
    const resultSection = document.getElementById('result-section');

    if (resultSection) resultSection.classList.remove('hidden');
    _setText('food-name', 'Lỗi Phân Tích');
    
    let fullMessage = message;
    if (suggestion) {
        fullMessage += `\n\n💡 ${suggestion}`;
    }
    
    _setText('food-desc', fullMessage);
    if (sysMsg) {
        sysMsg.textContent = fullMessage;
        sysMsg.classList.add('visible');
    }

    ['val-cal', 'val-prot', 'val-carb', 'val-fat'].forEach(id => {
        _setText(id, '--');
    });
    
    // Hide recipe and ingredients accordions
    _setStyle('ingredients-accordion', 'display', 'none');
    _setStyle('recipe-accordion', 'display', 'none');
    
    // Initialize accordion (for nutrition section)
    initAccordion();
}

function showNotFoodError(message, suggestion = null) {
    const resultSection = document.getElementById('result-section');
    const sysMsg = document.getElementById('sys-msg');

    if (resultSection) resultSection.classList.remove('hidden');

    // Tạo nội dung đặc biệt cho "không phải món ăn"
    _setText('food-name', '⚠️ Không phải món ăn');
    _setText('food-desc', '');
    // Hiển thị thông báo chi tiết trong sys-msg
    if (sysMsg) {
        sysMsg.innerHTML = `
            <div class="not-food-alert">
                <div class="not-food-icon">
                    <i class="fa-solid fa-circle-exclamation"></i>
                </div>
                <h3 class="not-food-title">${message || 'Hình ảnh này không phải là món ăn!'}</h3>
                <p class="not-food-desc">${suggestion || 'Vui lòng chụp hoặc tải lên hình ảnh một món ăn để hệ thống có thể nhận diện và phân tích dinh dưỡng.'}</p>
                <button class="btn btn-primary not-food-retake-btn" id="not-food-retake-btn">
                    <i class="fa-solid fa-camera-rotate"></i> Chụp / Chọn Ảnh Khác
                </button>
            </div>
        `;
        sysMsg.classList.add('visible');

        // Gắn sự kiện cho nút "Chụp lại"
        const retakeBtn = document.getElementById('not-food-retake-btn');
        if (retakeBtn) {
            retakeBtn.addEventListener('click', () => {
                // Reset trạng thái về upload
                resultSection.classList.add('hidden');
                sysMsg.textContent = '';
                sysMsg.classList.remove('visible');

                const previewContainer = document.getElementById('image-preview-container');
                const uploadContent = document.getElementById('upload-content');
                const fileInput = document.getElementById('file-input');
                const previewImg = document.getElementById('preview-img');
                const cameraSection = document.getElementById('camera-section');
                const modeUploadBtn = document.getElementById('mode-upload-btn');
                const modeCameraBtn = document.getElementById('mode-camera-btn');

                if (previewContainer) previewContainer.classList.add('hidden');
                if (fileInput) fileInput.value = '';
                if (previewImg) previewImg.src = '';

                // Kiểm tra mode hiện tại
                if (modeCameraBtn && modeCameraBtn.classList.contains('btn-primary')) {
                    // Đang ở mode camera → mở lại camera
                    if (cameraSection) cameraSection.classList.remove('hidden');
                } else {
                    // Mode upload → hiện lại upload zone
                    if (uploadContent) uploadContent.classList.remove('hidden');
                }
            });
        }
    }

    // Ẩn các section dinh dưỡng
    ['val-cal', 'val-prot', 'val-carb', 'val-fat'].forEach(id => {
        _setText(id, '--');
    });

    _setStyle('ingredients-accordion', 'display', 'none');
    _setStyle('recipe-accordion', 'display', 'none');

    // Ẩn comment section cho trường hợp không phải món ăn
    const commentSection = document.getElementById('user-comment-section');
    if (commentSection) commentSection.style.display = 'none';

    // Ẩn health recommendation
    const recBox = document.getElementById('health-recommendation-box');
    if (recBox) recBox.style.display = 'none';

    // Scroll tới kết quả
    resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function togglePassword(inputId, iconElement) {
    const input = document.getElementById(inputId);
    if (input.type === "password") {
        input.type = "text";
        iconElement.classList.remove("fa-eye-slash");
        iconElement.classList.add("fa-eye");
    } else {
        input.type = "password";
        iconElement.classList.remove("fa-eye");
        iconElement.classList.add("fa-eye-slash");
    }
}

// ---- AUTH LOGIC ----
function checkLoginState() {
    const authSection = document.getElementById('auth-section');
    const userSection = document.getElementById('user-section');
    const userNameDisplay = document.getElementById('user-name-display');
    const navAdminLink = document.getElementById('nav-admin-link');
    const navNutritionLink = document.getElementById('nav-nutrition-link');
    
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    
    if (loggedUser) {
        if(authSection) authSection.classList.add('hidden');
        if(userSection) userSection.classList.remove('hidden');
        if(userNameDisplay) {
            userNameDisplay.innerHTML = `<i class="fa-solid fa-user"></i> ${loggedUser.name}`;
            userNameDisplay.style.cursor = 'pointer';
        }
        if(navAdminLink) {
            if(loggedUser.role === 'admin') navAdminLink.classList.remove('hidden');
            else navAdminLink.classList.add('hidden');
        }
        // Show nutrition link for logged in users
        if(navNutritionLink) {
            navNutritionLink.style.display = 'flex';
        }
        // Init notifications
        initNotifications(loggedUser.id);
    } else {
        if(authSection) authSection.classList.remove('hidden');
        if(userSection) userSection.classList.add('hidden');
        if(navAdminLink) navAdminLink.classList.add('hidden');
        // Hide nutrition link for guests
        if(navNutritionLink) {
            navNutritionLink.style.display = 'none';
        }
    }
}

function initAuth() {
    const modalOverlay = document.getElementById('auth-modal');
    const loginBox = document.getElementById('login-box');
    const registerBox = document.getElementById('register-box');
    
    // Shows
    document.getElementById('btn-show-login')?.addEventListener('click', () => {
        modalOverlay.classList.remove('hidden');
        loginBox.classList.remove('hidden');
        registerBox.classList.add('hidden');
    });
    
    document.getElementById('btn-show-register')?.addEventListener('click', () => {
        modalOverlay.classList.remove('hidden');
        registerBox.classList.remove('hidden');
        loginBox.classList.add('hidden');
    });
    
    // Switch
    document.getElementById('switch-to-register')?.addEventListener('click', (e) => {
        e.preventDefault();
        loginBox.classList.add('hidden');
        registerBox.classList.remove('hidden');
    });
    
    document.getElementById('switch-to-login')?.addEventListener('click', (e) => {
        e.preventDefault();
        registerBox.classList.add('hidden');
        loginBox.classList.remove('hidden');
    });
    
    // Close
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            modalOverlay.classList.add('hidden');
        });
    });
    
    // Forms
    const loginForm = document.getElementById('login-form');
    loginForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const errDiv = document.getElementById('login-error');
        errDiv.classList.add('hidden');
        
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        
        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            
            if (data.success) {
                localStorage.setItem('smartfood_user', JSON.stringify(data.user));
                window.location.href = '/';
            } else {
                errDiv.textContent = data.message;
                errDiv.classList.remove('hidden', 'success');
            }
        } catch (error) {
            errDiv.textContent = "Lỗi kết nối máy chủ";
            errDiv.classList.remove('hidden', 'success');
        }
    });

    const regForm = document.getElementById('register-form');
    regForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const errDiv = document.getElementById('reg-error');
        errDiv.classList.add('hidden');
        
        const name = document.getElementById('reg-name').value;
        const email = document.getElementById('reg-email').value;
        const password = document.getElementById('reg-password').value;
        
        const payload = { 
            name, 
            email, 
            password,
            hp_age: document.getElementById('reg-age')?.value,
            hp_height: document.getElementById('reg-height')?.value,
            hp_weight: document.getElementById('reg-weight')?.value,
            hp_gender: document.getElementById('reg-gender')?.value,
            hp_goal: document.getElementById('reg-goal')?.value
        };
        
        try {
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (data.success) {
                errDiv.textContent = data.message + " - Vui lòng đăng nhập.";
                errDiv.classList.remove('hidden');
                errDiv.classList.add('success');
                regForm.reset();
                setTimeout(() => {
                    document.getElementById('switch-to-login').click();
                    errDiv.classList.add('hidden');
                }, 1500);
            } else {
                errDiv.textContent = data.message;
                errDiv.classList.remove('hidden', 'success');
            }
        } catch (error) {
            errDiv.textContent = "Lỗi kết nối máy chủ";
            errDiv.classList.remove('hidden', 'success');
        }
    });
    
    // Logout
    document.getElementById('btn-logout')?.addEventListener('click', () => {
        if (typeof window.appToast === 'function') {
            window.appToast('Đăng xuất thành công. Hẹn gặp lại!', 'success', 2200);
        }
        localStorage.removeItem('smartfood_user');
        checkLoginState();
        // Stay on the home page but ensure we land on the intro section
        if (window.location.hash && window.location.hash !== '#intro') {
            window.location.hash = 'intro';
        }
    });
    
    // Google Sign-In
    initGoogleSignIn();
}

// ---- GOOGLE SIGN-IN ----
function initGoogleSignIn() {
    // Callback xử lý khi Google trả về credential
    window.handleGoogleCredentialResponse = async function(response) {
        const modalOverlay = document.getElementById('auth-modal');
        const loginErrDiv = document.getElementById('login-error');
        const regErrDiv = document.getElementById('reg-error');
        
        try {
            const res = await fetch('/api/google-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_token: response.credential })
            });
            const data = await res.json();
            
            if (data.success) {
                localStorage.setItem('smartfood_user', JSON.stringify(data.user));
                if (modalOverlay) modalOverlay.classList.add('hidden');
                checkLoginState();
            } else {
                const errMsg = data.message || 'Lỗi đăng nhập Google';
                if (loginErrDiv && !loginErrDiv.closest('.hidden')) {
                    loginErrDiv.textContent = errMsg;
                    loginErrDiv.classList.remove('hidden', 'success');
                } else if (regErrDiv) {
                    regErrDiv.textContent = errMsg;
                    regErrDiv.classList.remove('hidden', 'success');
                }
            }
        } catch (error) {
            console.error('Google login error:', error);
            if (loginErrDiv) {
                loginErrDiv.textContent = 'Lỗi kết nối máy chủ khi đăng nhập Google';
                loginErrDiv.classList.remove('hidden', 'success');
            }
        }
    };
    
    // Khởi tạo Google Identity Services khi thư viện đã load
    function tryInitGSI() {
        if (typeof google !== 'undefined' && google.accounts) {
            google.accounts.id.initialize({
                client_id: window._GOOGLE_CLIENT_ID || '',
                callback: handleGoogleCredentialResponse,
                auto_select: false,
                cancel_on_tap_outside: true
            });
            
            // Gắn sự kiện cho nút Google login
            document.getElementById('btn-google-login')?.addEventListener('click', () => {
                google.accounts.id.prompt((notification) => {
                    if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
                        // Fallback: dùng popup nếu One Tap không hiện
                        google.accounts.oauth2.initCodeClient({
                            client_id: window._GOOGLE_CLIENT_ID || '',
                            scope: 'email profile',
                            callback: () => {}
                        });
                        // Dùng renderButton fallback
                        const tmpDiv = document.createElement('div');
                        tmpDiv.style.display = 'none';
                        document.body.appendChild(tmpDiv);
                        google.accounts.id.renderButton(tmpDiv, {
                            type: 'standard',
                            size: 'large'
                        });
                        tmpDiv.querySelector('div[role=button]')?.click();
                        setTimeout(() => tmpDiv.remove(), 1000);
                    }
                });
            });
            
            // Gắn sự kiện cho nút Google register (cùng flow)
            document.getElementById('btn-google-register')?.addEventListener('click', () => {
                google.accounts.id.prompt((notification) => {
                    if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
                        const tmpDiv = document.createElement('div');
                        tmpDiv.style.display = 'none';
                        document.body.appendChild(tmpDiv);
                        google.accounts.id.renderButton(tmpDiv, {
                            type: 'standard',
                            size: 'large'
                        });
                        tmpDiv.querySelector('div[role=button]')?.click();
                        setTimeout(() => tmpDiv.remove(), 1000);
                    }
                });
            });
            
            console.log('[Google Sign-In] Initialized successfully');
        } else {
            // Thư viện chưa load, thử lại sau
            setTimeout(tryInitGSI, 500);
        }
    }
    
    // Fetch Google Client ID từ server
    fetch('/api/google-client-id')
        .then(r => r.json())
        .then(data => {
            if (data.client_id) {
                window._GOOGLE_CLIENT_ID = data.client_id;
                tryInitGSI();
            } else {
                console.warn('[Google Sign-In] No client ID configured');
            }
        })
        .catch(() => {
            console.warn('[Google Sign-In] Failed to fetch client ID');
        });
}

// ---- PROFILE LOGIC ----
let dailyChart = null;
let weeklyChart = null;

async function initProfilePage() {
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    if (!loggedUser) return;

    // Set UI Info
    const nameEl = document.getElementById('profile-page-name');
    const emailEl = document.getElementById('profile-page-email');
    if (nameEl) nameEl.textContent = loggedUser.name;
    if (emailEl) emailEl.textContent = loggedUser.email;

    // Ẩn phần đổi mật khẩu nếu user đăng nhập bằng Google
    const pwSection = document.getElementById('change-pw-form');
    const pwTitle = pwSection?.previousElementSibling; // h4 title
    const pwDivider = pwTitle?.previousElementSibling; // hr divider
    if (loggedUser.auth_provider === 'google') {
        if (pwSection) pwSection.style.display = 'none';
        if (pwTitle && pwTitle.tagName === 'H4') pwTitle.style.display = 'none';
        if (pwDivider && pwDivider.tagName === 'HR') pwDivider.style.display = 'none';
    } else {
        if (pwSection) pwSection.style.display = '';
        if (pwTitle && pwTitle.tagName === 'H4') pwTitle.style.display = '';
        if (pwDivider && pwDivider.tagName === 'HR') pwDivider.style.display = '';
    }

    // Hiển thị avatar Google nếu có
    const avatarCircle = document.querySelector('.avatar-circle');
    if (avatarCircle && loggedUser.picture) {
        avatarCircle.innerHTML = `<img src="${loggedUser.picture}" alt="Avatar" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;">`;
    } else if (avatarCircle) {
        avatarCircle.innerHTML = '<i class="fa-solid fa-user"></i>';
    }

    // Fetch user info for premium remaining days
    try {
        const infoRes = await fetch('/api/user/' + loggedUser.id + '/info');
        const infoData = await infoRes.json();
        if (infoData.success && infoData.user) {
            // Update local storage if account type changed
            if (infoData.user.account_type !== loggedUser.account_type) {
                loggedUser.account_type = infoData.user.account_type;
                localStorage.setItem('smartfood_user', JSON.stringify(loggedUser));
                updatePremiumUI();
            }

            const daysEl = document.getElementById('profile-premium-days');
            if (daysEl) {
                if (infoData.user.account_type === 'premium') {
                    daysEl.style.display = 'block';
                    daysEl.querySelector('span').textContent = infoData.user.remaining_days;
                } else {
                    daysEl.style.display = 'none';
                }
            }
        }
    } catch (e) {
        console.error("Lỗi lấy thông tin user:", e);
    }

    // Load Health Profile
    try {
        const hpRes = await fetch('/api/health-profile/' + loggedUser.id);
        const hpData = await hpRes.json();
        if (hpData.success && hpData.profile) {
            document.getElementById('hp-age').value = hpData.profile.Tuoi || '';
            document.getElementById('hp-gender').value = hpData.profile.GioiTinh || 'Nam';
            document.getElementById('hp-height').value = hpData.profile.ChieuCao || '';
            document.getElementById('hp-weight').value = hpData.profile.CanNang || '';
            document.getElementById('hp-goal').value = hpData.profile.MucTieu || 'giu_dang';
        }
    } catch (e) {
        console.error("Lỗi tải hồ sơ sức khỏe", e);
    }

    // Health Profile Form Handler
    const hpForm = document.getElementById('health-profile-form');
    if (hpForm && !hpForm.dataset.initialized) {
        hpForm.dataset.initialized = 'true';
        hpForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgDiv = document.getElementById('hp-message');
            msgDiv.classList.add('hidden');
            
            const payload = {
                Tuoi: document.getElementById('hp-age').value,
                GioiTinh: document.getElementById('hp-gender').value,
                ChieuCao: document.getElementById('hp-height').value,
                CanNang: document.getElementById('hp-weight').value,
                MucTieu: document.getElementById('hp-goal').value
            };
            
            try {
                const res = await fetch('/api/health-profile/' + loggedUser.id, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const responseData = await res.json();
                
                msgDiv.textContent = responseData.message;
                msgDiv.classList.remove('hidden');
                if (responseData.success) {
                    msgDiv.classList.add('success');
                } else {
                    msgDiv.classList.remove('success');
                }
                setTimeout(() => msgDiv.classList.add('hidden'), 3000);
            } catch (err) {
                msgDiv.textContent = 'Lỗi kết nối';
                msgDiv.classList.remove('hidden', 'success');
            }
        });
    }

    // ---- TAB SWITCHING ----
    const profileTabs = document.querySelectorAll('.profile-tab');
    if (profileTabs.length > 0 && !profileTabs[0].dataset.initialized) {
        profileTabs.forEach(tab => {
            tab.dataset.initialized = 'true';
            tab.addEventListener('click', () => {
                profileTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                document.querySelectorAll('.profile-tab-content').forEach(c => c.classList.remove('active'));
                const targetId = tab.getAttribute('data-tab');
                document.getElementById(targetId)?.classList.add('active');

                // Load stats when switching to stats tab
                if (targetId === 'tab-stats') {
                    loadFoodStats(loggedUser.id);
                }
                // Load nutrition plans when switching to plans tab
                if (targetId === 'tab-nutrition-plans') {
                    loadProfilePlanHistory(loggedUser.id);
                }
            });
        });
    }

    // ---- LOAD HISTORY (with images) ----
    await loadFoodHistory(loggedUser.id);

    // Handlers (only attach once)
    const pwForm = document.getElementById('change-pw-form');
    if (pwForm && !pwForm.dataset.initialized) {
        pwForm.dataset.initialized = 'true';
        pwForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const errDiv = document.getElementById('pw-error');
            errDiv.classList.add('hidden');
            
            const oldPw = document.getElementById('pw-old').value;
            const newPw = document.getElementById('pw-new').value;
            
            try {
                const res = await fetch('/api/change-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: loggedUser.id, old_password: oldPw, new_password: newPw })
                });
                const responseData = await res.json();
                
                if (responseData.success) {
                    errDiv.textContent = responseData.message;
                    errDiv.classList.remove('hidden');
                    errDiv.classList.add('success');
                    pwForm.reset();
                    setTimeout(() => errDiv.classList.add('hidden'), 3000);
                } else {
                    errDiv.textContent = responseData.message;
                    errDiv.classList.remove('hidden', 'success');
                }
            } catch (err) {
                errDiv.textContent = 'Lỗi kết nối';
                errDiv.classList.remove('hidden', 'success');
            }
        });
    }

    const btnPageLogout = document.getElementById('btn-page-logout');
    if (btnPageLogout && !btnPageLogout.dataset.initialized) {
        btnPageLogout.dataset.initialized = 'true';
        btnPageLogout.addEventListener('click', () => {
            if (typeof window.appToast === 'function') {
                window.appToast('Đăng xuất thành công. Hẹn gặp lại!', 'success', 2200);
            }
            localStorage.removeItem('smartfood_user');
            checkLoginState();
            window.location.hash = 'intro';
        });
    }
}

// ---- LOAD FOOD HISTORY ----
async function loadFoodHistory(userId) {
    const historyContainer = document.getElementById('history-container');
    const historyCount = document.getElementById('history-count');
    if (!historyContainer) return;

    try {
        historyContainer.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 40px 0; grid-column: 1 / -1;"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><p style="margin-top: 10px;">Đang tải lịch sử...</p></div>';
        
        const res = await fetch('/api/history/' + userId);
        const data = await res.json();
        
        if (data.success && data.history && data.history.length > 0) {
            historyContainer.innerHTML = '';
            if (historyCount) historyCount.textContent = data.history.length + ' món';
            
            data.history.forEach(item => {
                const card = document.createElement('div');
                card.className = 'history-card';
                card.style.cursor = 'pointer';
                card.onclick = () => openHistoryCommentModal(item.id, item.food_name, item.plan_advice);
                
                const timeStr = item.time ? new Date(item.time).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
                const calStr = item.calories > 0 ? Math.round(item.calories) + ' kcal' : '--';
                
                // Image section
                let imgHTML = '';
                if (item.image && item.image.startsWith('data:')) {
                    imgHTML = `<div class="history-card-img"><img src="${item.image}" alt="${item.food_name}" loading="lazy"></div>`;
                } else {
                    imgHTML = `<div class="history-card-img"><div class="no-img"><i class="fa-solid fa-bowl-food"></i></div></div>`;
                }
                
                // Comment badge
                const commentBadge = item.comment_count > 0
                    ? `<span class="history-comment-badge"><i class="fa-solid fa-comments"></i> ${item.comment_count}</span>`
                    : `<span class="history-comment-badge history-comment-badge-empty"><i class="fa-regular fa-comment"></i> Phản hồi</span>`;
                
                // Plan advice badge
                let planBadge = '';
                if (item.plan_advice) {
                    const pm = {
                        'phu_hop': { icon: '✅', text: 'Phù hợp KH', cls: 'plan-badge-good' },
                        'an_it': { icon: '⚠️', text: 'Ăn vừa phải', cls: 'plan-badge-warn' },
                        'khong_nen': { icon: '❌', text: 'Không nên', cls: 'plan-badge-bad' }
                    };
                    const ps = pm[item.plan_advice.plan_status] || pm['an_it'];
                    planBadge = `<span class="history-plan-badge ${ps.cls}">${ps.icon} ${ps.text}</span>`;
                }
                
                card.innerHTML = `
                    ${imgHTML}
                    <div class="history-card-body">
                        <div class="history-card-name" title="${item.food_name}">${item.food_name}</div>
                        ${planBadge}
                        <div class="history-card-meta">
                            <span class="history-card-cal"><i class="fa-solid fa-fire"></i> ${calStr}</span>
                            ${commentBadge}
                        </div>
                        <div class="history-card-time"><i class="fa-regular fa-clock"></i> ${timeStr}</div>
                    </div>
                `;
                historyContainer.appendChild(card);
            });
        } else {
            historyContainer.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 40px 0; grid-column: 1 / -1;">Chưa có lịch sử tra cứu nào. Hãy bắt đầu nhận diện món ăn!</p>';
            if (historyCount) historyCount.textContent = '0 món';
        }
    } catch (e) {
        historyContainer.innerHTML = '<p style="text-align: center; color: var(--c-fat); padding: 40px 0; grid-column: 1 / -1;">Lỗi tải dữ liệu.</p>';
    }
}

// ---- LOAD FOOD STATS ----
async function loadFoodStats(userId) {
    try {
        const res = await fetch('/api/food-stats/' + userId);
        const data = await res.json();
        
        if (!data.success) return;
        const stats = data.stats;

        // Update summary cards
        document.getElementById('stats-today-cal').textContent = Math.round(stats.today_calories);
        document.getElementById('stats-today-count').textContent = stats.today_count;
        document.getElementById('stats-total-foods').textContent = stats.total_foods;
        document.getElementById('stats-total-cal').textContent = Math.round(stats.total_calories);

        // ---- DAILY CHART ----
        renderDailyChart(stats.daily);

        // ---- WEEKLY CHART ----
        renderWeeklyChart(stats.weekly);

        // ---- TOP FOODS ----
        renderTopFoods(stats.top_foods);

    } catch (e) {
        console.error('Lỗi tải thống kê:', e);
    }
}

function renderDailyChart(dailyData) {
    const ctx = document.getElementById('chart-daily-calories');
    if (!ctx) return;

    // Prepare last 7 days data
    const labels = [];
    const values = [];
    const today = new Date();
    
    for (let i = 6; i >= 0; i--) {
        const d = new Date(today);
        d.setDate(d.getDate() - i);
        const dateStr = d.toISOString().split('T')[0];
        const dayLabel = d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
        labels.push(dayLabel);
        
        const found = dailyData.find(item => item.date === dateStr);
        values.push(found ? Math.round(found.total_calories) : 0);
    }

    if (dailyChart) dailyChart.destroy();

    dailyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Calo',
                data: values,
                backgroundColor: 'rgba(34, 197, 94, 0.6)',
                borderColor: 'rgba(34, 197, 94, 1)',
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    padding: 12,
                    titleFont: { size: 13, weight: '600' },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: ctx => ctx.parsed.y + ' kcal'
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0,0,0,0.06)' },
                    ticks: { font: { size: 12 } }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 11 } }
                }
            }
        }
    });
}

function renderWeeklyChart(weeklyData) {
    const ctx = document.getElementById('chart-weekly-calories');
    if (!ctx) return;

    const labels = weeklyData.map(w => {
        const d = new Date(w.week_start);
        return 'Tuần ' + d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
    }).reverse();
    
    const values = weeklyData.map(w => Math.round(w.total_calories)).reverse();
    const counts = weeklyData.map(w => w.food_count).reverse();

    if (weeklyChart) weeklyChart.destroy();

    weeklyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.length > 0 ? labels : ['Tuần này'],
            datasets: [{
                label: 'Tổng Calo',
                data: values.length > 0 ? values : [0],
                backgroundColor: 'rgba(59, 130, 246, 0.6)',
                borderColor: 'rgba(59, 130, 246, 1)',
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    padding: 12,
                    callbacks: {
                        afterLabel: (ctx) => {
                            const idx = ctx.dataIndex;
                            return counts[idx] ? counts[idx] + ' món' : '';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0,0,0,0.06)' },
                    ticks: { font: { size: 12 } }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 11 } }
                }
            }
        }
    });
}

function renderTopFoods(topFoods) {
    const container = document.getElementById('top-foods-container');
    if (!container) return;

    if (!topFoods || topFoods.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 20px;">Chưa có dữ liệu thống kê</p>';
        return;
    }

    container.innerHTML = '';
    topFoods.forEach((food, idx) => {
        const item = document.createElement('div');
        item.className = 'top-food-item';
        item.innerHTML = `
            <div class="top-food-rank">${idx + 1}</div>
            <div class="top-food-info">
                <div class="top-food-name">${food.name}</div>
                <div class="top-food-detail">${food.count} lần nhận diện</div>
            </div>
            <div class="top-food-cal">~${food.avg_calories} kcal</div>
        `;
        container.appendChild(item);
    });
}

// ---- PROFILE: NUTRITION PLAN HISTORY ----
async function loadProfilePlanHistory(userId) {
    const container = document.getElementById('profile-plan-history');
    if (!container) return;
    
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><p style="margin-top:10px;">Đang tải...</p></div>';
    
    try {
        const res = await fetch(`/api/meal-plans/${userId}`);
        const data = await res.json();
        
        if (data.success && data.plans && data.plans.length > 0) {
            renderProfilePlans(container, data.plans);
        } else {
            container.innerHTML = `
                <div style="text-align:center;padding:50px 20px;color:var(--text-muted);">
                    <i class="fa-solid fa-calendar-xmark" style="font-size:48px;margin-bottom:16px;opacity:0.4;display:block;"></i>
                    <p style="font-size:15px;font-weight:500;">Chưa có kế hoạch dinh dưỡng nào được lưu</p>
                    <p style="font-size:13px;margin-top:8px;">Hãy vào trang <a href="/nutrition" style="color:var(--primary);font-weight:600;">Kế Hoạch Dinh Dưỡng</a> để tạo kế hoạch</p>
                </div>
            `;
        }
    } catch (err) {
        console.error('Error loading plan history:', err);
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--c-fat);"><i class="fa-solid fa-exclamation-triangle"></i> Lỗi tải lịch sử kế hoạch</div>';
    }
}

function renderProfilePlans(container, plans) {
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
        const pct = totalDays > 0 ? Math.round((goodDays / totalDays) * 100) : 0;
        
        html += `
            <div style="margin-bottom: 24px; border: 1px solid var(--glass-border); border-radius: var(--radius-md); overflow: hidden;">
                <div style="padding: 16px 20px; background: linear-gradient(135deg, rgba(139,92,246,0.08), rgba(99,102,241,0.05)); border-bottom: 1px solid var(--glass-border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <i class="fa-solid fa-calendar" style="color:#8b5cf6;font-size:18px;"></i>
                        <span style="font-weight:700;font-size:17px;">${monthName}</span>
                        <span style="background:rgba(139,92,246,0.15);color:#8b5cf6;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600;">${totalDays} ngày</span>
                    </div>
                    <div style="display:flex;gap:20px;font-size:13px;color:var(--text-muted);">
                        <span>TB Mục tiêu: <strong style="color:var(--text-main);">${Math.round(avgTarget)}</strong> kcal</span>
                        <span>TB Thực tế: <strong style="color:var(--text-main);">${Math.round(avgActual)}</strong> kcal</span>
                        <span>Đạt: <strong style="color:${pct >= 70 ? '#22c55e' : '#f59e0b'};">${goodDays}/${totalDays}</strong></span>
                    </div>
                </div>
                <div style="max-height: 400px; overflow-y: auto;">
        `;
        
        monthPlans.forEach(plan => {
            const diff = plan.tongCaloChon - plan.caloDuKien;
            const isGood = Math.abs(diff) <= plan.caloDuKien * 0.1;
            const diffText = diff > 0 ? `+${Math.round(diff)}` : `${Math.round(diff)}`;
            const date = plan.date.split(' ')[0];
            const statusColor = isGood ? '#22c55e' : (diff > 0 ? '#ef4444' : '#f59e0b');
            const statusIcon = isGood ? 'fa-check-circle' : (diff > 0 ? 'fa-arrow-up' : 'fa-arrow-down');
            
            html += `
                <div style="display:flex;align-items:center;padding:12px 20px;border-bottom:1px solid rgba(0,0,0,0.04);gap:16px;transition:background 0.2s;" onmouseenter="this.style.background='rgba(139,92,246,0.03)'" onmouseleave="this.style.background='transparent'">
                    <div style="min-width:90px;font-weight:600;font-size:14px;color:var(--text-main);">${date}</div>
                    <div style="flex:1;display:flex;gap:10px;flex-wrap:wrap;font-size:13px;color:var(--text-secondary);">
                        <span title="Bữa sáng">🌅 ${plan.buaSang || '—'} <span style="color:var(--text-muted);font-size:11px;">(${plan.buaSangCalo})</span></span>
                        <span>|</span>
                        <span title="Bữa trưa">☀️ ${plan.buaTrua || '—'} <span style="color:var(--text-muted);font-size:11px;">(${plan.buaTruaCalo})</span></span>
                        <span>|</span>
                        <span title="Bữa tối">🌙 ${plan.buaToi || '—'} <span style="color:var(--text-muted);font-size:11px;">(${plan.buaToiCalo})</span></span>
                        <span>|</span>
                        <span title="Bữa phụ">🍎 ${plan.buaPhu || '—'} <span style="color:var(--text-muted);font-size:11px;">(${plan.buaPhuCalo})</span></span>
                    </div>
                    <div style="min-width:130px;text-align:right;">
                        <span style="font-weight:700;font-size:15px;">${Math.round(plan.tongCaloChon)}</span>
                        <span style="color:var(--text-muted);font-size:13px;">/ ${Math.round(plan.caloDuKien)}</span>
                        <span style="color:${statusColor};font-size:12px;font-weight:600;margin-left:4px;"><i class="fa-solid ${statusIcon}"></i> ${diffText}</span>
                    </div>
                </div>
            `;
        });
        
        html += '</div></div>';
    }
    
    container.innerHTML = html;
}


// ---- INIT ----
document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    checkLoginState();
    initAnalyzePage();
    initRevealAnimations();
    initFoodSlider();
    initRatingButtons();
});

// ============================================
// USER RATING BUTTONS
// ============================================
function initRatingButtons() {
    const btns = document.querySelectorAll('.rating-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const rating = btn.dataset.rating;
            const historyId = window._currentHistoryId;
            if (!historyId) return;

            // Disable all buttons
            btns.forEach(b => { b.disabled = true; });
            btn.classList.add('selected');

            try {
                await fetch('/api/user-rating', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ history_id: historyId, rating })
                });
            } catch (e) {
                console.error('Rating error:', e);
            }

            // Show thank you
            const ratingBtns = document.getElementById('rating-buttons');
            const ratingDone = document.getElementById('rating-done');
            if (ratingBtns) ratingBtns.classList.add('hidden');
            if (ratingDone) ratingDone.classList.remove('hidden');
        });
    });
}

// ============================================
// NOTIFICATIONS
// ============================================
let notifPollTimer = null;

function initNotifications(userId) {
    const bellWrap = document.getElementById('notif-bell-wrap');
    const bellBtn = document.getElementById('notif-bell-btn');
    const dropdown = document.getElementById('notif-dropdown');
    const readAllBtn = document.getElementById('notif-read-all');

    if (!bellWrap) return;
    bellWrap.style.display = '';

    // Toggle dropdown
    bellBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('hidden');
    });

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!bellWrap.contains(e.target)) {
            dropdown.classList.add('hidden');
        }
    });

    // Mark all read
    readAllBtn?.addEventListener('click', async () => {
        try {
            await fetch(`/api/notifications/${userId}/read-all`, { method: 'PUT' });
            fetchNotifications(userId);
        } catch (e) { console.error(e); }
    });

    // Initial fetch + polling every 30s
    fetchNotifications(userId);
    if (notifPollTimer) clearInterval(notifPollTimer);
    notifPollTimer = setInterval(() => fetchNotifications(userId), 30000);
}

async function fetchNotifications(userId) {
    try {
        const res = await fetch(`/api/notifications/${userId}`);
        const data = await res.json();
        if (!data.success) return;

        const badge = document.getElementById('notif-badge');
        const body = document.getElementById('notif-dropdown-body');

        // Update badge
        if (data.unread_count > 0) {
            badge.textContent = data.unread_count > 9 ? '9+' : data.unread_count;
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }

        // Only show unread notifications
        const unread = data.notifications.filter(n => !n.is_read);

        if (unread.length === 0) {
            body.innerHTML = '<div class="notif-empty"><i class="fa-solid fa-bell-slash"></i><p>Không có thông báo mới</p></div>';
            return;
        }

        body.innerHTML = unread.map(n => {
            const timeStr = n.time ? new Date(n.time).toLocaleString('vi-VN') : '';
            
            // Detect icon based on content
            let icon = 'fa-pen-to-square';
            if (n.content.includes('bình luận') || n.content.includes('phản hồi')) icon = 'fa-comments';
            else if (n.content.includes('chỉnh sửa') || n.content.includes('sửa')) icon = 'fa-pen-to-square';
            
            return `
                <div class="notif-item notif-unread" data-id="${n.id}" data-history="${n.history_id || ''}" 
                     onclick="markNotifRead(${n.id}, ${userId}, '${n.history_id || ''}', this)">
                    <div class="notif-item-icon">
                        <i class="fa-solid ${icon}"></i>
                    </div>
                    <div class="notif-item-body">
                        <p class="notif-item-text">${n.content}</p>
                        ${n.old_name && n.new_name ? `
                            <div class="notif-item-change">
                                <span class="notif-old">${n.old_name}</span>
                                <i class="fa-solid fa-arrow-right"></i>
                                <span class="notif-new">${n.new_name}</span>
                            </div>` : ''}
                        <span class="notif-item-time"><i class="fa-regular fa-clock"></i> ${timeStr}</span>
                    </div>
                </div>`;
        }).join('');
    } catch (e) {
        console.error('Notification fetch error:', e);
    }
}

window.markNotifRead = async (notifId, userId, historyId, el) => {
    try {
        // 1. Mark as read on server
        await fetch(`/api/notifications/${notifId}/read`, { method: 'PUT' });
        
        // 2. Remove from dropdown with animation
        if (el) {
            el.style.transition = 'opacity 0.3s, transform 0.3s';
            el.style.opacity = '0';
            el.style.transform = 'translateX(20px)';
            setTimeout(() => {
                el.remove();
                // Check if dropdown is now empty
                const body = document.getElementById('notif-dropdown-body');
                if (body && body.querySelectorAll('.notif-item').length === 0) {
                    body.innerHTML = '<div class="notif-empty"><i class="fa-solid fa-bell-slash"></i><p>Không có thông báo mới</p></div>';
                }
            }, 300);
        }
        
        // 3. Update badge count
        const badge = document.getElementById('notif-badge');
        if (badge) {
            let count = parseInt(badge.textContent) || 0;
            count = Math.max(0, count - 1);
            if (count > 0) {
                badge.textContent = count > 9 ? '9+' : count;
            } else {
                badge.style.display = 'none';
            }
        }
        
        // 4. Close dropdown
        const dropdown = document.getElementById('notif-dropdown');
        if (dropdown) dropdown.classList.add('hidden');
        
        // 5. Navigate to profile > history
        window.location.hash = 'profile';
        // Wait for page to load then open comment modal if history_id exists
        if (historyId) {
            setTimeout(() => {
                const card = document.querySelector(`[onclick*="openHistoryCommentModal(${historyId}"]`);
                if (card) {
                    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    card.style.boxShadow = '0 0 0 2px var(--primary), 0 0 20px rgba(34, 197, 94, 0.3)';
                    setTimeout(() => { card.style.boxShadow = ''; }, 3000);
                }
            }, 500);
        }
    } catch (e) { console.error(e); }
};

// ============================================
// COMMENT / FEEDBACK SYSTEM
// ============================================
async function loadComments(historyId) {
    const listEl = document.getElementById('comment-list');
    if (!listEl) return;

    try {
        const res = await fetch(`/api/comments/${historyId}`);
        const data = await res.json();
        if (data.success) {
            renderComments(data.comments);
        }
    } catch (e) {
        console.error('Load comments error:', e);
    }
}

function renderComments(comments) {
    const listEl = document.getElementById('comment-list');
    if (!listEl) return;

    if (!comments || comments.length === 0) {
        listEl.innerHTML = '';
        return;
    }

    // Group: root comments and their replies
    const roots = comments.filter(c => !c.parent_id);
    const replies = comments.filter(c => c.parent_id);

    listEl.innerHTML = roots.map(c => {
        const childReplies = replies.filter(r => r.parent_id === c.id);
        const initial = (c.user_name || 'U').charAt(0).toUpperCase();
        const repliesHTML = childReplies.map(r => {
            const rInitial = r.is_admin ? 'A' : (r.user_name || 'U').charAt(0).toUpperCase();
            return `
                <div class="comment-reply-item">
                    <div class="comment-avatar comment-avatar-admin">${rInitial}</div>
                    <div class="comment-body">
                        <div class="comment-meta">
                            <span class="comment-author ${r.is_admin ? 'comment-admin-badge' : ''}">${r.is_admin ? '🛡️ Admin' : r.user_name}</span>
                            <span class="comment-time"><i class="fa-regular fa-clock"></i> ${r.time}</span>
                        </div>
                        <p class="comment-text">${r.content}</p>
                    </div>
                </div>`;
        }).join('');

        return `
            <div class="comment-item">
                <div class="comment-avatar">${initial}</div>
                <div class="comment-body">
                    <div class="comment-meta">
                        <span class="comment-author">${c.user_name}</span>
                        <span class="comment-time"><i class="fa-regular fa-clock"></i> ${c.time}</span>
                    </div>
                    <p class="comment-text">${c.content}</p>
                    ${repliesHTML ? `<div class="comment-replies">${repliesHTML}</div>` : ''}
                </div>
            </div>`;
    }).join('');
}

// ============================================
// HISTORY COMMENT MODAL (Profile page)
// ============================================
let _hcCurrentHistoryId = null;

function openHistoryCommentModal(historyId, foodName, planAdvice) {
    _hcCurrentHistoryId = historyId;
    const overlay = document.getElementById('history-comment-overlay');
    const foodLabel = document.getElementById('hc-modal-food');
    const commentInput = document.getElementById('hc-comment-input');
    const charCount = document.getElementById('hc-char-count');
    const submitBtn = document.getElementById('hc-btn-submit');
    const listEl = document.getElementById('hc-comment-list');
    
    if (!overlay) return;
    
    foodLabel.textContent = `Món: ${foodName}`;
    commentInput.value = '';
    charCount.textContent = '0/1000';
    submitBtn.disabled = true;
    listEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted)"><i class="fa-solid fa-spinner fa-spin"></i> Đang tải...</div>';
    
    // Render plan advice in modal
    let planDetailEl = document.getElementById('hc-plan-detail');
    if (!planDetailEl) {
        planDetailEl = document.createElement('div');
        planDetailEl.id = 'hc-plan-detail';
        const formEl = document.getElementById('hc-comment-form');
        formEl.parentNode.insertBefore(planDetailEl, formEl);
    }
    
    if (planAdvice) {
        const statusMap = {
            'phu_hop': { text: '✅ Phù hợp với kế hoạch', cls: 'plan-status-good', color: '#22c55e' },
            'an_it': { text: '⚠️ Nên ăn vừa phải', cls: 'plan-status-warn', color: '#f59e0b' },
            'khong_nen': { text: '❌ Không phù hợp kế hoạch', cls: 'plan-status-bad', color: '#ef4444' }
        };
        const st = statusMap[planAdvice.plan_status] || statusMap['an_it'];
        const total = planAdvice.plan_total_calo || 1;
        const consumedPct = Math.min(100, (planAdvice.plan_consumed_calo / total) * 100);
        const foodPct = Math.min(100 - consumedPct, (planAdvice.food_calo / total) * 100);
        
        planDetailEl.innerHTML = `
            <div style="padding:14px;border-radius:var(--radius-sm);border:1px solid var(--glass-border);margin-bottom:14px;border-left:3px solid ${st.color};background:rgba(255,255,255,0.02)">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                    <i class="fa-solid fa-clipboard-check" style="color:${st.color}"></i>
                    <strong style="font-size:13px">Đánh giá kế hoạch</strong>
                    <span class="${st.cls}" style="font-size:12px;padding:2px 8px;border-radius:10px;font-weight:700">${st.text}</span>
                </div>
                <p style="font-size:13px;color:var(--text-secondary);margin-bottom:10px">${planAdvice.plan_message}</p>
                <div style="position:relative;height:10px;background:rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;margin-bottom:6px">
                    <div style="position:absolute;left:0;top:0;height:100%;width:${consumedPct}%;background:linear-gradient(90deg,#6366f1,#8b5cf6);border-radius:5px"></div>
                    <div style="position:absolute;top:0;height:100%;width:${foodPct}%;left:${consumedPct}%;background:linear-gradient(90deg,#f59e0b,#f97316);border-radius:5px;opacity:0.85"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted)">
                    <span>Đã ăn: <strong style="color:var(--text-main)">${planAdvice.plan_consumed_calo}</strong> kcal</span>
                    <span>Món này: <strong style="color:#f59e0b">${planAdvice.food_calo}</strong> kcal</span>
                    <span>Mục tiêu: <strong style="color:var(--text-main)">${planAdvice.plan_total_calo}</strong> kcal</span>
                </div>
            </div>`;
    } else {
        planDetailEl.innerHTML = '';
    }
    
    overlay.classList.remove('hidden');
    
    // Load comments
    loadHistoryComments(historyId);
}

async function loadHistoryComments(historyId) {
    const listEl = document.getElementById('hc-comment-list');
    if (!listEl) return;
    
    try {
        const res = await fetch(`/api/comments/${historyId}`);
        const data = await res.json();
        if (data.success) {
            renderHistoryComments(data.comments, listEl);
        }
    } catch (e) {
        listEl.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:20px">Lỗi tải bình luận</p>';
    }
}

function renderHistoryComments(comments, listEl) {
    if (!comments || comments.length === 0) {
        listEl.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:20px"><i class="fa-regular fa-comment"></i> Chưa có bình luận nào. Hãy gửi phản hồi đầu tiên!</p>';
        return;
    }

    const roots = comments.filter(c => !c.parent_id);
    const replies = comments.filter(c => c.parent_id);

    listEl.innerHTML = roots.map(c => {
        const childReplies = replies.filter(r => r.parent_id === c.id);
        const initial = (c.user_name || 'U').charAt(0).toUpperCase();
        const repliesHTML = childReplies.map(r => {
            const rInitial = r.is_admin ? 'A' : (r.user_name || 'U').charAt(0).toUpperCase();
            return `
                <div class="comment-reply-item">
                    <div class="comment-avatar comment-avatar-admin">${rInitial}</div>
                    <div class="comment-body">
                        <div class="comment-meta">
                            <span class="comment-author ${r.is_admin ? 'comment-admin-badge' : ''}">${r.is_admin ? '🛡️ Admin' : r.user_name}</span>
                            <span class="comment-time"><i class="fa-regular fa-clock"></i> ${r.time}</span>
                        </div>
                        <p class="comment-text">${r.content}</p>
                    </div>
                </div>`;
        }).join('');

        return `
            <div class="comment-item">
                <div class="comment-avatar">${initial}</div>
                <div class="comment-body">
                    <div class="comment-meta">
                        <span class="comment-author">${c.user_name}</span>
                        <span class="comment-time"><i class="fa-regular fa-clock"></i> ${c.time}</span>
                    </div>
                    <p class="comment-text">${c.content}</p>
                    ${repliesHTML ? `<div class="comment-replies">${repliesHTML}</div>` : ''}
                </div>
            </div>`;
    }).join('');
}

// History comment modal form handlers
(function() {
    const input = document.getElementById('hc-comment-input');
    const charCount = document.getElementById('hc-char-count');
    const submitBtn = document.getElementById('hc-btn-submit');
    
    if (input) {
        input.addEventListener('input', () => {
            const len = input.value.length;
            charCount.textContent = `${len}/1000`;
            submitBtn.disabled = len === 0;
        });
    }
    
    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const content = input.value.trim();
            if (!content || !_hcCurrentHistoryId) return;
            
            const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
            if (!loggedUser) { alert('Vui lòng đăng nhập'); return; }
            
            submitBtn.disabled = true;
            const origHTML = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang gửi...';
            
            try {
                const res = await fetch('/api/comments', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        history_id: _hcCurrentHistoryId,
                        user_id: loggedUser.id,
                        content: content
                    })
                });
                const data = await res.json();
                if (data.success) {
                    input.value = '';
                    charCount.textContent = '0/1000';
                    loadHistoryComments(_hcCurrentHistoryId);
                    // Refresh history to update badge count
                    loadFoodHistory(loggedUser.id);
                } else {
                    alert(data.message || 'Lỗi khi gửi bình luận');
                }
            } catch (e) {
                alert('Lỗi kết nối server');
            }
            submitBtn.innerHTML = origHTML;
            submitBtn.disabled = false;
        });
    }
})();

// ============================================
// PREMIUM ACCOUNT FUNCTIONS
// ============================================

// Cập nhật quota counter trên trang phân tích
function updateQuotaCounter(quota) {
    const counter = document.getElementById('quota-counter');
    const text = document.getElementById('quota-text');
    const upgradeBtn = document.getElementById('quota-upgrade-btn');
    if (!counter || !text) return;

    if (quota.is_premium) {
        counter.style.display = 'flex';
        counter.classList.add('premium');
        counter.classList.remove('low');
        text.innerHTML = '<i class="fa-solid fa-crown"></i> Premium — Không giới hạn';
        if (upgradeBtn) upgradeBtn.style.display = 'none';
    } else {
        counter.style.display = 'flex';
        counter.classList.remove('premium');
        text.textContent = `Còn ${quota.remaining}/${quota.limit_per_day} lượt hôm nay`;
        if (quota.remaining <= 3) {
            counter.classList.add('low');
        } else {
            counter.classList.remove('low');
        }
        if (upgradeBtn) {
            upgradeBtn.style.display = quota.remaining <= 5 ? 'inline-flex' : 'none';
        }
    }
}

// Hiển thị modal nâng cấp Premium
function showUpgradeModal() {
    document.getElementById('premium-upgrade-modal').style.display = 'flex';
}

// Bắt đầu thanh toán PayOS
async function initiateUpgrade() {
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    if (!loggedUser) {
        alert('Vui lòng đăng nhập trước');
        return;
    }

    // Đóng tất cả modal
    document.querySelectorAll('.premium-modal-overlay').forEach(m => m.style.display = 'none');

    // Show loading toast
    if (typeof window.appToast === 'function') {
        window.appToast('Đang tạo đơn thanh toán PayOS...', 'info', 5000);
    }

    try {
        const res = await fetch('/api/payment/payos/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: loggedUser.id })
        });
        const data = await res.json();
        
        if (data.success && data.checkoutUrl) {
            // Redirect to PayOS payment page
            window.location.href = data.checkoutUrl;
        } else {
            alert(data.message || 'Lỗi tạo đơn thanh toán');
        }
    } catch (err) {
        console.error('Payment error:', err);
        alert('Lỗi kết nối server. Vui lòng thử lại.');
    }
}

// Xử lý kết quả thanh toán từ URL params
function checkPaymentResult() {
    const params = new URLSearchParams(window.location.search);
    const payment = params.get('payment');
    const orderId = params.get('orderId');

    if (!payment) return;

    const modal = document.getElementById('payment-result-modal');
    const icon = document.getElementById('payment-result-icon');
    const title = document.getElementById('payment-result-title');
    const desc = document.getElementById('payment-result-desc');

    if (payment === 'success') {
        icon.innerHTML = '<i class="fa-solid fa-circle-check"></i>';
        icon.className = 'premium-modal-icon crown-icon';
        title.textContent = '🎉 Nâng Cấp Thành Công!';
        desc.textContent = 'Cảm ơn bạn. Tài khoản của bạn đã được nâng cấp lên Premium.';
        
        const details = document.getElementById('payment-success-details');
        if (details) details.style.display = 'block';

        // Cập nhật localStorage
        const user = JSON.parse(localStorage.getItem('smartfood_user'));
        if (user) {
            user.account_type = 'premium';
            localStorage.setItem('smartfood_user', JSON.stringify(user));
        }
        
        // Cập nhật UI
        updatePremiumUI();

        // Chạy hiệu ứng pháo hoa
        setTimeout(triggerConfetti, 100);

    } else {
        icon.innerHTML = '<i class="fa-solid fa-circle-xmark"></i>';
        icon.className = 'premium-modal-icon quota-icon';
        title.textContent = 'Thanh Toán Thất Bại';
        desc.textContent = 'Giao dịch không thành công. Vui lòng thử lại hoặc liên hệ hỗ trợ.';
        const details = document.getElementById('payment-success-details');
        if (details) details.style.display = 'none';
    }

    modal.style.display = 'flex';

    // Remove payment params from URL
    const url = new URL(window.location);
    url.searchParams.delete('payment');
    url.searchParams.delete('orderId');
    url.searchParams.delete('resultCode');
    window.history.replaceState({}, '', url);
}

function triggerConfetti() {
    const colors = ['#22c55e', '#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6'];
    
    for (let i = 0; i < 60; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.position = 'fixed';
        confetti.style.width = '10px';
        confetti.style.height = '10px';
        confetti.style.zIndex = '99999';
        
        // Random styles
        confetti.style.left = Math.random() * 100 + 'vw';
        confetti.style.top = '-10px';
        confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        
        // Random animation variables
        const duration = Math.random() * 3 + 2;
        const delay = Math.random() * 1;
        
        confetti.animate([
            { transform: `translate3d(0, 0, 0) rotate(0deg)`, opacity: 1 },
            { transform: `translate3d(${Math.random() * 200 - 100}px, 100vh, 0) rotate(${Math.random() * 720}deg)`, opacity: 0 }
        ], {
            duration: duration * 1000,
            delay: delay * 1000,
            easing: 'cubic-bezier(.37,0,.63,1)',
            fill: 'forwards'
        });
        
        document.body.appendChild(confetti);
        
        setTimeout(() => {
            confetti.remove();
        }, (duration + delay) * 1000);
    }
}

function closePaymentResult() {
    document.getElementById('payment-result-modal').style.display = 'none';
}

// Cập nhật UI dựa trên trạng thái Premium
function updatePremiumUI() {
    const user = JSON.parse(localStorage.getItem('smartfood_user'));
    
    if (!user) {
        const counter = document.getElementById('quota-counter');
        const text = document.getElementById('quota-text');
        const upgradeBtn = document.getElementById('quota-upgrade-btn');
        if (counter && text) {
            let guestCount = parseInt(localStorage.getItem('guest_analysis_count')) || 0;
            let remaining = Math.max(0, 5 - guestCount);
            counter.style.display = 'flex';
            counter.classList.remove('premium');
            text.textContent = `Dùng thử: còn ${remaining}/5 lượt`;
            if (upgradeBtn) {
                upgradeBtn.style.display = 'none';
            }
        }
        return;
    }

    const isPremium = user.account_type === 'premium';

    // Profile badge
    const badgeWrap = document.getElementById('profile-account-badge');
    if (badgeWrap) {
        if (isPremium) {
            badgeWrap.innerHTML = '<span class="badge-premium"><i class="fa-solid fa-crown"></i> Premium</span>';
        } else {
            badgeWrap.innerHTML = '<button class="badge-free-upgrade" onclick="showUpgradeModal()"><i class="fa-solid fa-arrow-up-right-dots"></i> Nâng cấp Premium</button>';
        }
    }

    // Quota counter
    if (isPremium) {
        const counter = document.getElementById('quota-counter');
        if (counter) {
            counter.style.display = 'flex';
            counter.classList.add('premium');
            const text = document.getElementById('quota-text');
            if (text) text.innerHTML = '<i class="fa-solid fa-crown"></i> Premium — Không giới hạn';
            const upgradeBtn = document.getElementById('quota-upgrade-btn');
            if (upgradeBtn) upgradeBtn.style.display = 'none';
        }
    } else {
        // Load quota from server
        fetch(`/api/user/${user.id}/quota`).then(r=>r.json()).then(data => {
            if (data.success) updateQuotaCounter(data.quota);
        }).catch(() => {});
    }

}

// Khởi tạo Premium features khi trang load
function initPremiumFeatures() {
    checkPaymentResult();
    
    const user = JSON.parse(localStorage.getItem('smartfood_user'));
    updatePremiumUI();

    // Kiểm tra URL param upgrade=true
    const params = new URLSearchParams(window.location.search);
    if (params.get('upgrade') === 'true') {
        showUpgradeModal();
        const url = new URL(window.location);
        url.searchParams.delete('upgrade');
        window.history.replaceState({}, '', url);
    }
}

// Gọi khi DOM ready
document.addEventListener('DOMContentLoaded', initPremiumFeatures);
