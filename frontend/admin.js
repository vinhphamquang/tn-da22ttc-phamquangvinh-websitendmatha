// ---- ADMIN LOGIC ----
document.addEventListener('DOMContentLoaded', () => {
    console.log("Admin page loaded!");
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));

    // Redirect if not admin
    if (!loggedUser || loggedUser.role !== 'admin') {
        window.location.href = '/';
        return;
    }

    // --- Navbar Setup ---
    // Show user name
    const displayUsername = document.getElementById('display-username');
    if (displayUsername) displayUsername.textContent = loggedUser.name;

    // Show nutrition link (visible for logged-in users)
    const nutritionLink = document.getElementById('nav-nutrition-link');
    if (nutritionLink) nutritionLink.style.display = '';



    // Mobile nav toggle
    const navToggle = document.getElementById('nav-toggle');
    const navLinks = document.getElementById('nav-links');
    if (navToggle && navLinks) {
        navToggle.addEventListener('click', () => {
            navLinks.classList.toggle('show');
        });
    }

    // Logout logic
    const btnLogout = document.getElementById('btn-admin-logout');
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

    // Init animations
    const reveals = document.querySelectorAll('.reveal');
    setTimeout(() => {
        reveals.forEach(el => el.classList.add('visible'));
    }, 100);

    // ============================================
    // BULK SELECT STATE
    // ============================================
    let selectedFoodIds = new Set();

    function updateBulkUI() {
        const bar = document.getElementById('bulk-action-bar');
        const countEl = document.getElementById('bulk-count');
        const listEl = document.getElementById('bulk-selected-list');
        const count = selectedFoodIds.size;

        if (count > 0) {
            bar.classList.remove('hidden');
            countEl.textContent = `${count} món đã chọn`;

            // Build tags showing selected food names
            let tagsHtml = '';
            document.querySelectorAll('#tb-foods tr').forEach(row => {
                const id = parseInt(row.dataset.foodId);
                if (selectedFoodIds.has(id)) {
                    const name = row.querySelectorAll('td')[1]?.textContent || '';
                    tagsHtml += `<span class="bulk-tag" data-id="${id}">
                        <strong>#${id}</strong> ${name}
                        <i class="fa-solid fa-xmark bulk-tag-remove" onclick="window._removeBulkItem(${id})"></i>
                    </span>`;
                }
            });
            listEl.innerHTML = tagsHtml;
        } else {
            bar.classList.add('hidden');
            listEl.innerHTML = '';
        }

        // Sync select-all checkbox in bulk bar
        const allCheckboxes = document.querySelectorAll('.food-row-checkbox');
        const bulkSelectAll = document.getElementById('bulk-select-all');
        const allChecked = allCheckboxes.length > 0 && selectedFoodIds.size === allCheckboxes.length;
        if (bulkSelectAll) bulkSelectAll.checked = allChecked;

        // Highlight rows
        document.querySelectorAll('#tb-foods tr').forEach(row => {
            const id = parseInt(row.dataset.foodId);
            if (selectedFoodIds.has(id)) {
                row.classList.add('row-selected');
            } else {
                row.classList.remove('row-selected');
            }
        });
    }

    // Remove single item from bulk selection
    window._removeBulkItem = function (id) {
        selectedFoodIds.delete(id);
        const cb = document.querySelector(`.food-row-checkbox[data-food-id="${id}"]`);
        if (cb) cb.checked = false;
        updateBulkUI();
    };

    function toggleFoodSelect(id, checked) {
        if (checked) selectedFoodIds.add(id);
        else selectedFoodIds.delete(id);
        updateBulkUI();
    }

    function toggleSelectAll(checked) {
        const allCheckboxes = document.querySelectorAll('.food-row-checkbox');
        allCheckboxes.forEach(cb => {
            cb.checked = checked;
            const id = parseInt(cb.dataset.foodId);
            if (checked) selectedFoodIds.add(id);
            else selectedFoodIds.delete(id);
        });
        updateBulkUI();
    }

    // Select-all from bulk bar
    document.getElementById('bulk-select-all')?.addEventListener('change', (e) => {
        toggleSelectAll(e.target.checked);
    });
    // Cancel bulk selection
    document.getElementById('btn-bulk-cancel')?.addEventListener('click', () => {
        toggleSelectAll(false);
    });

    // Bulk Soft Delete
    document.getElementById('btn-bulk-soft-delete')?.addEventListener('click', async () => {
        const ids = Array.from(selectedFoodIds);
        if (ids.length === 0) return;
        if (!confirm(`Bạn có chắc muốn KHÓA (soft delete) ${ids.length} món ăn đã chọn?`)) return;

        let success = 0, fail = 0;
        for (const id of ids) {
            try {
                const res = await fetch(`/api/admin/foods/${id}`, { method: 'DELETE' });
                const r = await res.json();
                if (r.success) success++;
                else fail++;
            } catch { fail++; }
        }
        alert(`Đã khóa ${success} món.${fail > 0 ? ` Lỗi: ${fail} món.` : ''}`);
        selectedFoodIds.clear();
        updateBulkUI();
        fetchAdminFoods();
    });

    // Bulk Hard Delete
    document.getElementById('btn-bulk-hard-delete')?.addEventListener('click', async () => {
        const ids = Array.from(selectedFoodIds);
        if (ids.length === 0) return;
        if (!confirm(`⚠️ BẠN CÓ CHẮC MUỐN XÓA VĨNH VIỄN ${ids.length} MÓN ĂN?\n\nHành động này KHÔNG THỂ HOÀN TÁC!`)) return;
        if (!confirm(`Xác nhận lần cuối: XÓA VĨNH VIỄN ${ids.length} món ăn đã chọn?`)) return;

        let success = 0, fail = 0;
        for (const id of ids) {
            try {
                const res = await fetch(`/api/admin/foods/${id}/hard-delete`, { method: 'DELETE' });
                const r = await res.json();
                if (r.success) success++;
                else fail++;
            } catch { fail++; }
        }
        alert(`✅ Đã xóa vĩnh viễn ${success} món.${fail > 0 ? ` Lỗi: ${fail} món.` : ''}`);
        selectedFoodIds.clear();
        updateBulkUI();
        fetchAdminFoods();
    });

    // Tabs logic
    const tabs = document.querySelectorAll('.admin-tab');
    const contents = document.querySelectorAll('.admin-tab-content');
    const TAB_LEAVE_MS = 180;
    let _tabSwapTimer = null;

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.dataset.tab;
            const targetEl = document.getElementById(targetId);
            const currentEl = document.querySelector('.admin-tab-content:not(.hidden)');
            if (!targetEl || currentEl === targetEl) {
                // Still sync active state on the buttons in case they're out of sync
                tabs.forEach(t => t.classList.toggle('active', t === tab));
                return;
            }

            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            if (_tabSwapTimer) { clearTimeout(_tabSwapTimer); _tabSwapTimer = null; }

            const commit = () => {
                contents.forEach(c => {
                    c.classList.add('hidden');
                    c.classList.remove('tab-leaving');
                });
                targetEl.classList.remove('hidden');

                if (targetId === 'admin-stats') fetchAdminStats();
                if (targetId === 'admin-foods') fetchAdminFoods();
                if (targetId === 'admin-users') fetchAdminUsers();
                if (targetId === 'admin-history') fetchAdminHistory();
                if (targetId === 'admin-comments') fetchAdminComments();
                if (targetId === 'admin-payments') fetchAdminPayments();
            };

            if (currentEl) {
                currentEl.classList.add('tab-leaving');
                _tabSwapTimer = setTimeout(() => {
                    _tabSwapTimer = null;
                    commit();
                }, TAB_LEAVE_MS);
            } else {
                commit();
            }
        });
    });

    // Removed Food Modal Logic



    // Global Edit/Delete Handlers

    window.deleteAdminFood = async (id) => {
        if (!confirm('Bạn có chắc chắn muốn CHUYỂN VÀO THÙNG RÁC món ăn này? (Sẽ không còn hiện trên web cho User)')) return;
        try {
            const res = await fetch(`/api/admin/foods/${id}`, { method: 'DELETE' });
            const r = await res.json();
            if (r.success) fetchAdminFoods();
            else alert(r.message);
        } catch (e) { console.error(e); }
    };

    window.restoreAdminFood = async (id) => {
        if (!confirm('Bạn muốn HOÀN TÁC (khôi phục) món ăn này để hiển thị lại trên web?')) return;
        try {
            const res = await fetch(`/api/admin/foods/${id}/restore`, { method: 'PUT' });
            const r = await res.json();
            if (r.success) fetchAdminFoods();
            else alert(r.message);
        } catch (e) { console.error(e); }
    };

    window.hardDeleteAdminFood = async (id) => {
        if (!confirm('⚠️ BẠN CÓ CHẮC MUỐN XÓA VĨNH VIỄN MÓN ĂN NÀY?\n\nHành động này KHÔNG THỂ HOÀN TÁC!\nTất cả dữ liệu dinh dưỡng, công thức, nguyên liệu liên quan sẽ bị xóa hoàn toàn.')) return;
        if (!confirm('Xác nhận lần cuối: XÓA VĨNH VIỄN món ăn ID #' + id + '?')) return;
        try {
            const res = await fetch(`/api/admin/foods/${id}/hard-delete`, { method: 'DELETE' });
            const r = await res.json();
            if (r.success) {
                alert('✅ ' + r.message);
                fetchAdminFoods();
            }
            else alert(r.message);
        } catch (e) { console.error(e); }
    };

    window.deleteAdminUser = async (id) => {
        if (!confirm('Bạn có chắc chắn muốn XÓA VĨNH VIỄN người dùng này?')) return;
        try {
            const res = await fetch(`/api/admin/users/${id}`, { method: 'DELETE' });
            const r = await res.json();
            if (r.success) fetchAdminUsers();
            else alert(r.message);
        } catch (e) { console.error(e); }
    };

    window.calculateExpiry = (upgradeDateStr) => {
        if (!upgradeDateStr) return '--';
        try {
            // upgradeDateStr is 'YYYY-MM-DD HH:mm:ss'
            const d = new Date(upgradeDateStr.replace(' ', 'T'));
            d.setDate(d.getDate() + 30); // 30 days expiry
            return d.toLocaleDateString('vi-VN');
        } catch (e) {
            return '--';
        }
    };

    // Default fetch on load
    fetchAdminStats();

    // Fetch Functions
    async function fetchAdminStats() {
        try {
            const res = await fetch('/api/admin/stats');
            const data = await res.json();
            if (data.success) {
                document.getElementById('st-users').textContent = data.stats.total_users;
                document.getElementById('st-foods').textContent = data.stats.total_foods;
                document.getElementById('st-recs').textContent = data.stats.total_recognitions;

                // Premium stats
                const stPremium = document.getElementById('st-premium');
                if (stPremium) stPremium.textContent = data.stats.premium_users || 0;

                // Fetch revenue for overview
                fetchPaymentStatsOverview();

                // Render Comment Stats
                renderCommentStats(data.stats);

                // Render Top Foods
                renderTopFoods(data.stats.top_foods);
            }
        } catch (e) { console.error(e); }
    }

    function renderCommentStats(stats) {
        const comments = stats.comments || { total: 0, replied: 0, pending: 0 };

        // Update values
        const csTotal = document.getElementById('cs-total');
        const csPending = document.getElementById('cs-pending');
        const csReplied = document.getElementById('cs-replied');

        if (csTotal) csTotal.textContent = comments.total;
        if (csPending) csPending.textContent = comments.pending;
        if (csReplied) csReplied.textContent = comments.replied;

        // Recent Comments
        const recentList = document.getElementById('recent-comments-list');
        const recentComments = stats.recent_comments || [];
        if (recentList) {
            if (recentComments.length > 0) {
                recentList.innerHTML = recentComments.map(item => {
                    const statusCls = item.reply_count > 0 ? 'comment-status-replied' : 'comment-status-pending';
                    const statusText = item.reply_count > 0 ? 'Đã phản hồi' : 'Chưa phản hồi';
                    const statusIcon = item.reply_count > 0 ? 'fa-check-double' : 'fa-clock';
                    return `
                        <div class="recent-comment-item">
                            <div class="recent-comment-info">
                                <span class="recent-comment-user"><i class="fa-solid fa-user"></i> ${item.user_name}</span>
                                <span class="recent-comment-food">${item.food_name}</span>
                                <p class="recent-comment-text">${item.content.length > 60 ? item.content.substring(0, 60) + '...' : item.content}</p>
                                <span class="recent-comment-time"><i class="fa-regular fa-clock"></i> ${item.time}</span>
                            </div>
                            <span class="comment-status-badge ${statusCls}"><i class="fa-solid ${statusIcon}"></i> ${statusText}</span>
                        </div>
                    `;
                }).join('');
            } else {
                recentList.innerHTML = '<p class="rating-empty"><i class="fa-solid fa-comments"></i> Chưa có bình luận nào</p>';
            }
        }
    }

    function renderTopFoods(topFoods) {
        const listEl = document.getElementById('top-foods-list');
        if (!listEl) return;
        
        if (!topFoods || topFoods.length === 0) {
            listEl.innerHTML = '<p class="rating-empty">Chưa có dữ liệu nhận diện món ăn</p>';
            return;
        }
        
        listEl.innerHTML = topFoods.map((item, index) => {
            let badgeClass = 'badge-info';
            if (index === 0) badgeClass = 'badge-success';
            if (index === 1) badgeClass = 'badge-warning';
            
            return `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(255,255,255,0.5); border-radius: 8px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-weight: bold; color: var(--text-muted); width: 20px;">#${index + 1}</span>
                        <span style="font-weight: 600;">${item.name}</span>
                    </div>
                    <span class="badge ${badgeClass}"><i class="fa-solid fa-camera"></i> ${item.count} lượt</span>
                </div>
            `;
        }).join('');
    }

    async function fetchAdminFoods() {
        const tb = document.getElementById('tb-foods');
        tb.innerHTML = '<tr><td colspan="5" style="text-align:center"><i class="fa-solid fa-spinner fa-spin"></i></td></tr>';
        selectedFoodIds.clear();
        updateBulkUI();
        try {
            const res = await fetch('/api/admin/foods');
            const data = await res.json();
            if (data.success) {
                tb.innerHTML = '';
                data.foods.forEach(f => {
                    const status = f.is_deleted ? '<span class="badge badge-danger">Đã khóa</span>' : '<span class="badge badge-success">Hiển thị</span>';
                    const tr = document.createElement('tr');
                    tr.dataset.foodId = f.id;
                    tr.innerHTML = `
                            <td>#${f.id}</td>
                            <td>${f.name}</td>
                            <td>${f.category}</td>
                            <td>${status}</td>
                            <td>
                                <div class="action-btns">
                                    ${!f.is_deleted ? `<button class="btn-icon delete" title="Khóa (Soft Delete)" onclick="deleteAdminFood(${f.id})"><i class="fa-solid fa-ban"></i></button>` : `<button class="btn-icon" title="Hoàn tác" style="color: var(--c-carb);" onclick="restoreAdminFood(${f.id})"><i class="fa-solid fa-rotate-left"></i></button>`}
                                    <button class="btn-icon delete" title="Xóa vĩnh viễn" onclick="hardDeleteAdminFood(${f.id})" style="color: #ef4444;"><i class="fa-solid fa-trash"></i></button>
                                    <label class="bulk-select-label" title="Chọn để xóa nhiều">
                                        <input type="checkbox" class="food-row-checkbox" data-food-id="${f.id}">
                                        <span class="bulk-select-box"><i class="fa-solid fa-check"></i></span>
                                    </label>
                                </div>
                            </td>
                    `;
                    tb.appendChild(tr);
                });
                // Attach checkbox listeners
                document.querySelectorAll('.food-row-checkbox').forEach(cb => {
                    cb.addEventListener('change', (e) => {
                        toggleFoodSelect(parseInt(e.target.dataset.foodId), e.target.checked);
                    });
                });
            }
        } catch (e) { console.error(e); tb.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">Lỗi tải dữ liệu</td></tr>'; }
    }

    let allUsersData = [];

    async function fetchAdminUsers() {
        const tb = document.getElementById('tb-users');
        tb.innerHTML = '<tr><td colspan="8" style="text-align:center"><i class="fa-solid fa-spinner fa-spin"></i></td></tr>';
        try {
            const res = await fetch('/api/admin/users');
            const data = await res.json();
            if (data.success) {
                allUsersData = data.users;
                renderUsersTable();
            }
        } catch (e) { console.error(e); tb.innerHTML = '<tr><td colspan="8" style="text-align:center; color:red;">Lỗi tải dữ liệu</td></tr>'; }
    }

    function getOnlineStatus(lastActive) {
        if (!lastActive) return { cls: 'status-offline', text: 'Chưa hoạt động', dot: '⚪' };
        const now = new Date();
        const last = new Date(lastActive);
        const diffMin = (now - last) / 60000;
        if (diffMin < 5) return { cls: 'status-online', text: 'Đang online', dot: '🟢' };
        if (diffMin < 30) return { cls: 'status-away', text: 'Vừa hoạt động', dot: '🟡' };
        if (diffMin < 1440) return { cls: 'status-offline', text: formatTimeAgo(last), dot: '⚪' };
        return { cls: 'status-offline', text: last.toLocaleDateString('vi-VN'), dot: '⚪' };
    }

    function formatTimeAgo(date) {
        const now = new Date();
        const diffMin = Math.floor((now - date) / 60000);
        if (diffMin < 60) return `${diffMin} phút trước`;
        const diffHours = Math.floor(diffMin / 60);
        if (diffHours < 24) return `${diffHours} giờ trước`;
        return date.toLocaleDateString('vi-VN');
    }

    function getFilteredSortedUsers() {
        const searchVal = (document.getElementById('user-search-input')?.value || '').trim().toLowerCase();
        const roleFilter = document.getElementById('user-role-filter')?.value || 'all';
        const sortVal = document.getElementById('user-sort-select')?.value || 'newest';

        let filtered = [...allUsersData];

        // Filter by search
        if (searchVal) {
            filtered = filtered.filter(u =>
                (u.name || '').toLowerCase().includes(searchVal) ||
                (u.email || '').toLowerCase().includes(searchVal)
            );
        }

        // Filter by role
        if (roleFilter === 'admin') filtered = filtered.filter(u => u.role === 'admin');
        else if (roleFilter === 'user') filtered = filtered.filter(u => u.role === 'user' && u.auth_provider !== 'google');
        else if (roleFilter === 'google') filtered = filtered.filter(u => u.auth_provider === 'google');

        // Sort
        switch (sortVal) {
            case 'newest':
                filtered.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
                break;
            case 'oldest':
                filtered.sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
                break;
            case 'name_az':
                filtered.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'vi'));
                break;
            case 'most_active':
                filtered.sort((a, b) => (b.analysis_count || 0) - (a.analysis_count || 0));
                break;
        }

        return filtered;
    }

    function renderUsersTable() {
        const tb = document.getElementById('tb-users');
        const filtered = getFilteredSortedUsers();

        // Update total badge
        const badge = document.getElementById('user-total-badge');
        if (badge) badge.textContent = `${filtered.length} / ${allUsersData.length} người dùng`;

        if (filtered.length === 0) {
            tb.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 40px; color: var(--text-muted);">Không tìm thấy người dùng</td></tr>';
            return;
        }

        tb.innerHTML = '';
        filtered.forEach(u => {
            const status = getOnlineStatus(u.last_active);
            const roleBadge = u.role === 'admin'
                ? '<span class="badge badge-warning"><i class="fa-solid fa-star"></i> Admin</span>'
                : u.auth_provider === 'google'
                    ? '<span class="badge badge-info"><i class="fa-brands fa-google"></i> Google</span>'
                    : '<span class="badge badge-info">User</span>';

            const accountBadge = u.account_type === 'premium'
                ? '<span class="badge" style="background:linear-gradient(135deg,#f59e0b,#d97706);color:white;font-size:10px;padding:2px 8px;margin-left:4px;"><i class="fa-solid fa-crown"></i> Premium</span>'
                : '';

            const initial = (u.name || 'U').charAt(0).toUpperCase();
            const avatarColors = ['#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4', '#FF5722', '#607D8B'];
            const colorIdx = (u.id || 0) % avatarColors.length;

            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            tr.onclick = () => viewUserDetail(u.id);
            tr.innerHTML = `
                <td style="width: 50px;">
                    <div class="user-avatar-sm" style="background: ${avatarColors[colorIdx]};">${initial}</div>
                </td>
                <td style="font-weight: 600">${u.name}</td>
                <td><span style="font-size: 13px; color: var(--text-secondary)">${u.email}</span></td>
                <td>${roleBadge}${accountBadge}</td>
                <td>
                    <span class="user-status-badge ${status.cls}">
                        <span class="status-dot"></span> ${status.text}
                    </span>
                </td>
                <td>
                    <span class="analysis-count-badge">${u.analysis_count || 0} <i class="fa-solid fa-camera-retro"></i></span>
                </td>
                <td><span style="font-size: 13px; color: var(--text-muted)">${u.created_at}</span></td>
                <td>
                    <div class="action-btns" onclick="event.stopPropagation()">
                        <button class="btn-icon" title="Xem chi tiết" onclick="viewUserDetail(${u.id})"><i class="fa-solid fa-eye"></i></button>
                        ${u.role !== 'admin' ? `<button class="btn-icon delete" title="Xóa" onclick="deleteAdminUser(${u.id})"><i class="fa-solid fa-trash"></i></button>` : ''}
                    </div>
                </td>
            `;
            tb.appendChild(tr);
        });
    }

    // Search, Filter, Sort event listeners
    const userSearchInput = document.getElementById('user-search-input');
    if (userSearchInput) {
        let searchTimeout;
        userSearchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(renderUsersTable, 300);
        });
    }
    document.getElementById('user-role-filter')?.addEventListener('change', renderUsersTable);
    document.getElementById('user-sort-select')?.addEventListener('change', renderUsersTable);

    // View User Detail Modal
    window.viewUserDetail = async (userId) => {
        const overlay = document.getElementById('user-detail-overlay');
        const content = document.getElementById('user-detail-content');
        overlay.classList.remove('hidden');
        content.innerHTML = '<div class="history-loading"><i class="fa-solid fa-spinner fa-spin"></i><span>Đang tải chi tiết...</span></div>';

        try {
            const res = await fetch(`/api/admin/users/${userId}/detail`);
            const data = await res.json();
            if (!data.success) {
                content.innerHTML = '<div class="history-empty"><i class="fa-solid fa-circle-exclamation"></i><p>Không tìm thấy người dùng</p></div>';
                return;
            }

            const d = data.detail;
            const status = getOnlineStatus(d.last_active);
            const initial = (d.name || 'U').charAt(0).toUpperCase();
            const avatarColors = ['#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4', '#FF5722', '#607D8B'];
            const colorIdx = (d.id || 0) % avatarColors.length;

            const authBadge = d.auth_provider === 'google'
                ? '<span class="badge badge-info" style="font-size: 11px;"><i class="fa-brands fa-google"></i> Google</span>'
                : '<span class="badge badge-success" style="font-size: 11px;"><i class="fa-solid fa-envelope"></i> Email</span>';

            // Health section
            let healthHTML = '';
            if (d.health) {
                const h = d.health;
                const bmiColor = h.bmi < 18.5 ? '#3b82f6' : h.bmi < 25 ? '#22c55e' : h.bmi < 30 ? '#f59e0b' : '#ef4444';
                healthHTML = `
                    <div class="ud-section">
                        <div class="ud-section-title"><i class="fa-solid fa-heart-pulse"></i> Hồ Sơ Sức Khỏe</div>
                        <div class="ud-health-grid">
                            <div class="ud-health-item">
                                <span class="ud-health-label">Cân nặng</span>
                                <span class="ud-health-val">${h.weight} kg</span>
                            </div>
                            <div class="ud-health-item">
                                <span class="ud-health-label">Chiều cao</span>
                                <span class="ud-health-val">${h.height} cm</span>
                            </div>
                            <div class="ud-health-item">
                                <span class="ud-health-label">Tuổi</span>
                                <span class="ud-health-val">${h.age || '--'}</span>
                            </div>
                            <div class="ud-health-item">
                                <span class="ud-health-label">Giới tính</span>
                                <span class="ud-health-val">${h.gender || '--'}</span>
                            </div>
                            <div class="ud-health-item ud-health-highlight" style="border-color: ${bmiColor}">
                                <span class="ud-health-label">BMI</span>
                                <span class="ud-health-val" style="color: ${bmiColor}">${h.bmi || '--'}</span>
                                <span class="ud-health-sub">${h.bmi_status}</span>
                            </div>
                            <div class="ud-health-item ud-health-highlight">
                                <span class="ud-health-label">BMR</span>
                                <span class="ud-health-val">${h.bmr || '--'}</span>
                                <span class="ud-health-sub">kcal/ngày</span>
                            </div>
                            <div class="ud-health-item">
                                <span class="ud-health-label">TDEE</span>
                                <span class="ud-health-val">${h.tdee || '--'}</span>
                                <span class="ud-health-sub">kcal/ngày</span>
                            </div>
                            <div class="ud-health-item">
                                <span class="ud-health-label">Mục tiêu</span>
                                <span class="ud-health-val">${h.goal || '--'}</span>
                                <span class="ud-health-sub">${h.target_cal ? h.target_cal + ' kcal' : ''}</span>
                            </div>
                        </div>
                    </div>`;
            } else {
                healthHTML = `
                    <div class="ud-section">
                        <div class="ud-section-title"><i class="fa-solid fa-heart-pulse"></i> Hồ Sơ Sức Khỏe</div>
                        <p style="color: var(--text-muted); font-size: 14px; padding: 16px;">Chưa cập nhật hồ sơ sức khỏe</p>
                    </div>`;
            }

            // Recent history section
            let historyHTML = '';
            if (d.recent_history && d.recent_history.length > 0) {
                const rows = d.recent_history.map(h => {
                    const ratingMap = {
                        'chinh_xac': '✅',
                        'trung_binh': '⚠️',
                        'sai': '❌'
                    };
                    return `<tr>
                        <td style="font-weight: 500; color: var(--primary-light)">${h.food_name}</td>
                        <td>${h.calories ? Math.round(h.calories) + ' kcal' : '--'}</td>
                        <td>${ratingMap[h.rating] || '—'}</td>
                        <td style="font-size: 12px; color: var(--text-muted)">${h.time}</td>
                    </tr>`;
                }).join('');
                historyHTML = `
                    <div class="ud-section">
                        <div class="ud-section-title"><i class="fa-solid fa-clock-rotate-left"></i> Lịch Sử Hoạt Động Gần Đây</div>
                        <div class="table-responsive">
                            <table class="admin-table ud-history-table">
                                <thead><tr><th>Món ăn</th><th>Calo</th><th>Đánh giá</th><th>Thời gian</th></tr></thead>
                                <tbody>${rows}</tbody>
                            </table>
                        </div>
                    </div>`;
            } else {
                historyHTML = `
                    <div class="ud-section">
                        <div class="ud-section-title"><i class="fa-solid fa-clock-rotate-left"></i> Lịch Sử Hoạt Động</div>
                        <p style="color: var(--text-muted); font-size: 14px; padding: 16px;">Chưa có hoạt động nào</p>
                    </div>`;
            }

            content.innerHTML = `
                <div class="ud-header">
                    <div class="ud-avatar-lg" style="background: ${avatarColors[colorIdx]};">${initial}</div>
                    <div class="ud-header-info" style="flex: 1;">
                        <h2 class="ud-name">${d.name}</h2>
                        <div class="ud-meta">
                            <span>${d.email}</span>
                            ${authBadge}
                            <span class="user-status-badge ${status.cls}"><span class="status-dot"></span> ${status.text}</span>
                        </div>
                    </div>
                    ${d.account_type === 'premium' && d.upgrade_date ? `
                    <div class="ud-actions">
                        <div class="premium-expiry-badge" style="background: rgba(245, 158, 11, 0.1); color: #f59e0b; padding: 6px 12px; border-radius: 8px; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px; border: 1px solid rgba(245, 158, 11, 0.2);">
                            <i class="fa-solid fa-crown"></i>
                            Hạn Premium: ${calculateExpiry(d.upgrade_date)}
                        </div>
                    </div>
                    ` : ''}
                </div>

                <div class="ud-stats-row">
                    <div class="ud-stat-card">
                        <i class="fa-solid fa-camera-retro" style="color: #f59e0b;"></i>
                        <span class="ud-stat-val">${d.stats.total_analyses}</span>
                        <span class="ud-stat-label">Phân tích</span>
                    </div>
                    <div class="ud-stat-card">
                        <i class="fa-solid fa-fire" style="color: #ef4444;"></i>
                        <span class="ud-stat-val">${d.stats.avg_calories}</span>
                        <span class="ud-stat-label">Calo TB</span>
                    </div>
                    <div class="ud-stat-card">
                        <i class="fa-solid fa-calendar-check" style="color: #22c55e;"></i>
                        <span class="ud-stat-val">${d.created_at ? new Date(d.created_at).toLocaleDateString('vi-VN') : '--'}</span>
                        <span class="ud-stat-label">Ngày đăng ký</span>
                    </div>
                    <div class="ud-stat-card">
                        <i class="fa-solid fa-clock" style="color: #3b82f6;"></i>
                        <span class="ud-stat-val">${d.stats.last_analysis || 'Chưa có'}</span>
                        <span class="ud-stat-label">Phân tích cuối</span>
                    </div>
                </div>

                ${healthHTML}
                ${historyHTML}
            `;
        } catch (e) {
            console.error('User detail error:', e);
            content.innerHTML = '<div class="history-empty"><i class="fa-solid fa-triangle-exclamation"></i><p>Lỗi khi tải chi tiết</p></div>';
        }
    };

    // ============================================
    // HISTORY: GRID + TABLE + DETAIL MODAL
    // ============================================
    let allHistoryData = [];
    let historyView = 'grid'; // 'grid' or 'table'

    // View toggle
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            historyView = btn.dataset.view;
            const gridEl = document.getElementById('history-grid-view');
            const tableEl = document.getElementById('history-table-view');
            if (historyView === 'grid') {
                gridEl.style.display = '';
                tableEl.style.display = 'none';
            } else {
                gridEl.style.display = 'none';
                tableEl.style.display = '';
            }
        });
    });

    // Search filter
    const historySearchInput = document.getElementById('history-search-input');
    if (historySearchInput) {
        let searchTimeout;
        historySearchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                renderHistoryViews(allHistoryData, historySearchInput.value.trim().toLowerCase());
            }, 300);
        });
    }

    function renderHistoryViews(data, filter = '') {
        let filtered = data;
        if (filter) {
            filtered = data.filter(h =>
                (h.food_name || '').toLowerCase().includes(filter) ||
                (h.user_name || '').toLowerCase().includes(filter) ||
                (h.user_email || '').toLowerCase().includes(filter)
            );
        }
        renderHistoryGrid(filtered);
        renderHistoryTable(filtered);
    }

    function getImageSrc(imageData) {
        if (!imageData) return '';
        if (imageData.startsWith('data:')) return imageData;
        if (imageData.startsWith('/9j/') || imageData.startsWith('iVBOR')) {
            return 'data:image/jpeg;base64,' + imageData;
        }
        return imageData;
    }

    function getCommentBadge(commentCount) {
        if (!commentCount || commentCount === 0) return '<span class="rating-badge rating-none"><i class="fa-solid fa-minus"></i> --</span>';
        return `<span class="rating-badge rating-green"><i class="fa-solid fa-comments"></i> ${commentCount}</span>`;
    }

    function renderHistoryGrid(data) {
        const grid = document.getElementById('history-grid-view');
        if (!data || data.length === 0) {
            grid.innerHTML = `
                <div class="history-empty">
                    <i class="fa-solid fa-folder-open"></i>
                    <p>Không có dữ liệu lịch sử</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = data.map(h => {
            const imgSrc = getImageSrc(h.image);
            const dateObj = h.time ? new Date(h.time) : null;
            const dateStr = dateObj ? dateObj.toLocaleDateString('vi-VN') : '';

            return `
            <div class="history-card" onclick="viewHistoryDetail(${h.id})">
                <div class="history-card-img">
                    ${imgSrc
                    ? `<img src="${imgSrc}" alt="${h.food_name}" loading="lazy">`
                    : `<div class="history-card-no-img"><i class="fa-solid fa-image"></i></div>`
                }
                </div>
                <div class="history-card-body">
                    <h4 class="history-card-food">${h.food_name || 'Không xác định'}</h4>
                    <div class="history-card-meta">
                        <span class="history-card-user">
                            <i class="fa-solid fa-user"></i> ${h.user_name || 'Ẩn danh'}
                        </span>
                        ${h.calories ? `<span class="history-card-cal"><i class="fa-solid fa-fire-flame-curved"></i> ${Math.round(h.calories)} kcal</span>` : ''}
                    </div>
                    <div class="history-card-rating">${getCommentBadge(h.comment_count)}</div>
                    <div class="history-card-time">
                        <i class="fa-regular fa-clock"></i> ${dateStr}
                    </div>
                </div>
                <div class="history-card-hover-hint">
                    <i class="fa-solid fa-eye"></i> Xem chi tiết
                </div>
            </div>`;
        }).join('');
    }

    function renderHistoryTable(data) {
        const tb = document.getElementById('tb-history');
        if (!data || data.length === 0) {
            tb.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 40px; color: var(--text-muted);">Không có dữ liệu</td></tr>';
            return;
        }

        tb.innerHTML = data.map(h => {
            const imgSrc = getImageSrc(h.image);
            const dateObj = h.time ? new Date(h.time) : null;
            const dateStr = dateObj ? dateObj.toLocaleString('vi-VN') : '';

            return `
            <tr style="cursor: pointer" onclick="viewHistoryDetail(${h.id})">
                <td>#${h.id}</td>
                <td>
                    ${imgSrc
                    ? `<img src="${imgSrc}" alt="" class="history-table-thumb" onclick="event.stopPropagation(); viewHistoryDetail(${h.id})">`
                    : `<span class="history-table-no-img"><i class="fa-solid fa-image-slash"></i></span>`
                }
                </td>
                <td style="font-weight: 500">${h.user_name || 'Ẩn danh'}</td>
                <td style="font-weight: 600; color: var(--text-main);">${h.food_name || 'Không xác định'}</td>
                <td>${h.calories ? `<span class="badge badge-warning" style="font-size: 11px;">${Math.round(h.calories)} kcal</span>` : '-'}</td>
                <td>${getCommentBadge(h.comment_count)}</td>
                <td style="font-size: 13px; color: var(--text-muted);">${dateStr}</td>
                <td>
                    <div class="action-btns" onclick="event.stopPropagation()">
                        <button class="btn-icon" title="Xem chi tiết" onclick="viewHistoryDetail(${h.id})">
                            <i class="fa-solid fa-eye"></i>
                        </button>
                    </div>
                </td>
            </tr>`;
        }).join('');
    }

    async function fetchAdminHistory() {
        const grid = document.getElementById('history-grid-view');
        const tb = document.getElementById('tb-history');
        grid.innerHTML = '<div class="history-loading"><i class="fa-solid fa-spinner fa-spin"></i><span>Đang tải dữ liệu...</span></div>';
        tb.innerHTML = '<tr><td colspan="9" style="text-align:center"><i class="fa-solid fa-spinner fa-spin"></i></td></tr>';
        try {
            const res = await fetch('/api/admin/history');
            const data = await res.json();
            if (data.success) {
                allHistoryData = data.history;
                const filter = (historySearchInput && historySearchInput.value.trim().toLowerCase()) || '';
                renderHistoryViews(allHistoryData, filter);
            }
        } catch (e) {
            console.error(e);
            grid.innerHTML = '<div class="history-empty"><i class="fa-solid fa-triangle-exclamation"></i><p>Lỗi tải dữ liệu</p></div>';
        }
    }

    // Detail modal
    window.viewHistoryDetail = async (historyId) => {
        const overlay = document.getElementById('history-detail-overlay');
        const content = document.getElementById('history-detail-content');
        overlay.classList.remove('hidden');
        content.innerHTML = '<div class="history-loading"><i class="fa-solid fa-spinner fa-spin"></i><span>Đang tải chi tiết...</span></div>';

        try {
            const res = await fetch(`/api/admin/history/${historyId}`);
            const data = await res.json();
            if (!data.success) {
                content.innerHTML = '<div class="history-empty"><i class="fa-solid fa-circle-exclamation"></i><p>Không tìm thấy bản ghi</p></div>';
                return;
            }

            const d = data.detail;
            const imgSrc = getImageSrc(d.image);
            const dateObj = d.time ? new Date(d.time) : null;
            const dateStr = dateObj ? dateObj.toLocaleString('vi-VN') : 'N/A';
            const fi = d.food_info; // may be null
            const accuracyPct = d.accuracy ? Math.round(d.accuracy * 100) : null;
            const escapeHtml = (s) => String(s == null ? '' : s)
                .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            const commentsHtml = (d.comments && d.comments.length)
                ? d.comments.map(c => `
                    <div class="hd-comment ${c.is_admin ? 'hd-comment-admin' : ''} ${c.parent_id ? 'hd-comment-reply' : ''}">
                        <div class="hd-comment-head">
                            <span class="hd-comment-user">
                                <i class="fa-solid ${c.is_admin ? 'fa-user-shield' : 'fa-user'}"></i>
                                ${escapeHtml(c.user_name)}${c.is_admin ? ' <span class="hd-admin-tag">Admin</span>' : ''}
                            </span>
                            <span class="hd-comment-time">${escapeHtml(c.time)}</span>
                        </div>
                        <div class="hd-comment-body">${escapeHtml(c.content)}</div>
                    </div>`).join('')
                : '<p style="color: var(--text-muted); font-size: 14px; margin: 0;">Chưa có bình luận nào.</p>';

            content.innerHTML = `
                <div class="hd-header">
                    <div class="hd-badge"><i class="fa-solid fa-receipt"></i> Chi Tiết Nhận Diện #${d.id}</div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span class="hd-time"><i class="fa-regular fa-clock"></i> ${dateStr}</span>
                    </div>
                </div>

                <div class="hd-layout">
                    <!-- Image Section -->
                    <div class="hd-image-section">
                        ${imgSrc
                    ? `<div class="hd-image-wrap"><img src="${imgSrc}" alt="${d.food_name}" class="hd-image"></div>`
                    : `<div class="hd-image-placeholder"><i class="fa-solid fa-camera"></i><span>Không có hình ảnh</span></div>`
                }
                    </div>

                    <!-- Info Section -->
                    <div class="hd-info-section">
                        <!-- Food Name -->
                        <h2 class="hd-food-name">
                            <i class="fa-solid fa-utensils"></i>
                            ${d.food_name || 'Không xác định'}
                        </h2>

                        ${accuracyPct !== null ? `
                        <!-- Accuracy Badge -->
                        <div class="hd-user-rating">
                            <span class="hd-info-label">Độ chính xác AI:</span>
                            <span class="rating-badge ${accuracyPct >= 80 ? 'rating-green' : accuracyPct >= 50 ? 'rating-yellow' : 'rating-none'}">
                                <i class="fa-solid fa-bullseye"></i> ${accuracyPct}%
                            </span>
                        </div>` : ''}

                        <!-- User Info -->
                        <div class="hd-info-card">
                            <div class="hd-info-card-title"><i class="fa-solid fa-user-circle"></i> Người dùng</div>
                            <div class="hd-info-row">
                                <span class="hd-info-label">Tên:</span>
                                <span class="hd-info-value">${d.user_name}</span>
                            </div>
                            ${d.user_email ? `
                            <div class="hd-info-row">
                                <span class="hd-info-label">Email:</span>
                                <span class="hd-info-value">${d.user_email}</span>
                            </div>` : ''}
                            ${d.user_id ? `
                            <div class="hd-info-row">
                                <span class="hd-info-label">User ID:</span>
                                <span class="hd-info-value">#${d.user_id}</span>
                            </div>` : ''}
                        </div>



                        <!-- Detailed Nutrition from DB -->
                        ${fi ? `
                        <div class="hd-info-card hd-nutrition-card">
                            <div class="hd-info-card-title"><i class="fa-solid fa-chart-pie"></i> Thông tin dinh dưỡng (CSDL)</div>
                            ${fi.category ? `<div class="hd-info-row"><span class="hd-info-label">Phân loại:</span><span class="hd-info-value">${fi.category}</span></div>` : ''}
                            ${fi.description ? `<div class="hd-info-row"><span class="hd-info-label">Mô tả:</span><span class="hd-info-value hd-desc">${fi.description}</span></div>` : ''}
                            <div class="hd-nutrition-grid">
                                <div class="hd-nutr-item hd-nutr-cal">
                                    <i class="fa-solid fa-fire"></i>
                                    <span class="hd-nutr-val">${fi.calories || 0}</span>
                                    <span class="hd-nutr-label">Calo</span>
                                </div>
                                <div class="hd-nutr-item hd-nutr-pro">
                                    <i class="fa-solid fa-dumbbell"></i>
                                    <span class="hd-nutr-val">${fi.protein || 0}g</span>
                                    <span class="hd-nutr-label">Protein</span>
                                </div>
                                <div class="hd-nutr-item hd-nutr-fat">
                                    <i class="fa-solid fa-droplet"></i>
                                    <span class="hd-nutr-val">${fi.fat || 0}g</span>
                                    <span class="hd-nutr-label">Chất béo</span>
                                </div>
                                <div class="hd-nutr-item hd-nutr-carb">
                                    <i class="fa-solid fa-wheat-awn"></i>
                                    <span class="hd-nutr-val">${fi.carbs || 0}g</span>
                                    <span class="hd-nutr-label">Carbs</span>
                                </div>
                            </div>
                        </div>` : `
                        <div class="hd-info-card">
                            <div class="hd-info-card-title"><i class="fa-solid fa-circle-info"></i> Thông tin CSDL</div>
                            <p style="color: var(--text-muted); font-size: 14px;">Món ăn này chưa có trong cơ sở dữ liệu hệ thống.</p>
                        </div>`}

                        <!-- Comments -->
                        <div class="hd-info-card hd-comments-card">
                            <div class="hd-info-card-title">
                                <i class="fa-solid fa-comments"></i>
                                Bình luận (${(d.comments || []).length})
                            </div>
                            <div class="hd-comments-list">${commentsHtml}</div>
                        </div>
                    </div>
                </div>
            `;
        } catch (e) {
            console.error('History detail error:', e);
            content.innerHTML = '<div class="history-empty"><i class="fa-solid fa-triangle-exclamation"></i><p>Lỗi khi tải chi tiết</p></div>';
        }
    };
});

// ============================================
// ADMIN NOTIFICATIONS
// ============================================
(function initAdminNotifications() {
    const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
    if (!loggedUser || !loggedUser.id) return;

    const bellWrap = document.getElementById('notif-bell-wrap');
    const bellBtn = document.getElementById('notif-bell-btn');
    const dropdown = document.getElementById('notif-dropdown');
    const readAllBtn = document.getElementById('notif-read-all');

    if (!bellWrap) return;

    // Toggle dropdown
    bellBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('hidden');
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!bellWrap.contains(e.target)) {
            dropdown.classList.add('hidden');
        }
    });

    // Mark all read
    readAllBtn?.addEventListener('click', async () => {
        try {
            await fetch(`/api/notifications/${loggedUser.id}/read-all`, { method: 'PUT' });
            fetchAdminNotifications();
        } catch (e) { console.error(e); }
    });

    async function fetchAdminNotifications() {
        try {
            const res = await fetch(`/api/notifications/${loggedUser.id}`);
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

            // Only show unread
            const unread = data.notifications.filter(n => !n.is_read);

            if (unread.length === 0) {
                body.innerHTML = '<div class="notif-empty"><i class="fa-solid fa-bell-slash"></i><p>Không có thông báo mới</p></div>';
                return;
            }

            body.innerHTML = unread.map(n => {
                const timeStr = n.time ? new Date(n.time).toLocaleString('vi-VN') : '';

                // Detect notification type for icon & target tab
                let icon = 'fa-pen-to-square';
                let targetTab = 'admin-history';
                if (n.content.includes('👤') || n.content.includes('đăng ký')) {
                    icon = 'fa-user-plus';
                    targetTab = 'admin-users';
                } else if (n.content.includes('bình luận') || n.content.includes('phản hồi') || n.content.includes('💬')) {
                    icon = 'fa-comments';
                    targetTab = 'admin-comments';
                } else if (n.content.includes('❌') || n.content.includes('Sai')) {
                    icon = 'fa-circle-xmark';
                } else if (n.content.includes('⚠️') || n.content.includes('Trung bình')) {
                    icon = 'fa-triangle-exclamation';
                }

                return `
                    <div class="notif-item notif-unread" data-id="${n.id}" 
                         onclick="markAdminNotifRead(${n.id}, '${targetTab}', this)">
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
            console.error('Admin notification fetch error:', e);
        }
    }

    // Mark single notification read → navigate → remove from dropdown
    window.markAdminNotifRead = async (notifId, targetTab, el) => {
        try {
            // 1. Mark as read on server
            await fetch(`/api/notifications/${notifId}/read`, { method: 'PUT' });

            // 2. Animate removal
            if (el) {
                el.style.transition = 'opacity 0.3s, transform 0.3s';
                el.style.opacity = '0';
                el.style.transform = 'translateX(20px)';
                setTimeout(() => {
                    el.remove();
                    const body = document.getElementById('notif-dropdown-body');
                    if (body && body.querySelectorAll('.notif-item').length === 0) {
                        body.innerHTML = '<div class="notif-empty"><i class="fa-solid fa-bell-slash"></i><p>Không có thông báo mới</p></div>';
                    }
                }, 300);
            }

            // 3. Update badge
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

            // 5. Navigate to target tab
            if (targetTab) {
                const tabBtn = document.querySelector(`.admin-tab-btn[data-tab="${targetTab}"]`);
                if (tabBtn) tabBtn.click();
            }
        } catch (e) { console.error(e); }
    };

    // Initial fetch + polling
    fetchAdminNotifications();
    setInterval(() => fetchAdminNotifications(), 30000);
})();

// ============================================
// ADMIN COMMENTS MANAGEMENT
// ============================================
async function fetchAdminComments() {
    const listEl = document.getElementById('admin-comments-list');
    if (!listEl) return;

    listEl.innerHTML = '<div class="history-loading"><i class="fa-solid fa-spinner fa-spin"></i><span>Đang tải...</span></div>';

    const filter = document.getElementById('comment-filter-status')?.value || 'all';

    try {
        const res = await fetch(`/api/admin/comments?status=${filter}`);
        const data = await res.json();
        if (data.success) {
            renderAdminComments(data.comments);
        }
    } catch (e) {
        console.error(e);
        listEl.innerHTML = '<div class="history-empty"><i class="fa-solid fa-triangle-exclamation"></i><p>Lỗi tải dữ liệu</p></div>';
    }
}

function renderAdminComments(comments) {
    const listEl = document.getElementById('admin-comments-list');
    if (!listEl) return;

    if (!comments || comments.length === 0) {
        listEl.innerHTML = '<div class="history-empty"><i class="fa-solid fa-comments"></i><p>Chưa có bình luận nào</p></div>';
        return;
    }

    listEl.innerHTML = comments.map(c => {
        const statusCls = c.status === 'replied' ? 'comment-status-replied' : 'comment-status-pending';
        const statusText = c.status === 'replied' ? 'Đã phản hồi' : 'Chưa phản hồi';
        const statusIcon = c.status === 'replied' ? 'fa-check-double' : 'fa-clock';

        const repliesHTML = (c.replies || []).map(r => `
            <div class="admin-reply-item">
                <div class="admin-reply-avatar">${r.is_admin ? '🛡️' : 'U'}</div>
                <div class="admin-reply-body">
                    <span class="admin-reply-author">${r.is_admin ? 'Admin' : r.user_name}</span>
                    <p class="admin-reply-text">${r.content}</p>
                    <span class="admin-reply-time"><i class="fa-regular fa-clock"></i> ${r.time}</span>
                </div>
            </div>
        `).join('');

        return `
            <div class="admin-comment-card" data-id="${c.id}">
                <div class="admin-comment-header">
                    <div class="admin-comment-user">
                        <div class="admin-comment-avatar">${(c.user_name || 'U').charAt(0).toUpperCase()}</div>
                        <div>
                            <span class="admin-comment-name">${c.user_name}</span>
                            <span class="admin-comment-email">${c.user_email || ''}</span>
                        </div>
                    </div>
                    <span class="comment-status-badge ${statusCls}"><i class="fa-solid ${statusIcon}"></i> ${statusText}</span>
                </div>
                <div class="admin-comment-food">
                    <i class="fa-solid fa-utensils"></i> ${c.food_name}
                </div>
                <div class="admin-comment-content">
                    <p>${c.content}</p>
                    <span class="admin-comment-time"><i class="fa-regular fa-clock"></i> ${c.time}</span>
                </div>
                ${repliesHTML ? `<div class="admin-comment-replies">${repliesHTML}</div>` : ''}
                <div class="admin-comment-actions">
                    <div class="admin-reply-form-wrap" id="reply-form-${c.id}" style="display: none;">
                        <textarea class="admin-reply-textarea" id="reply-input-${c.id}" placeholder="Nhập phản hồi cho người dùng..." rows="2"></textarea>
                        <div class="admin-reply-btns">
                            <button class="btn btn-ghost" style="padding: 6px 14px; font-size: 13px;" onclick="document.getElementById('reply-form-${c.id}').style.display='none'">Hủy</button>
                            <button class="btn btn-primary" style="padding: 6px 14px; font-size: 13px;" onclick="submitAdminReply(${c.id})">
                                <i class="fa-solid fa-paper-plane"></i> Gửi
                            </button>
                        </div>
                    </div>
                    <div class="admin-comment-btn-row">
                        <button class="btn btn-outline" style="padding: 6px 14px; font-size: 13px;" onclick="toggleReplyForm(${c.id})">
                            <i class="fa-solid fa-reply"></i> Phản hồi
                        </button>
                        <button class="btn-icon btn-icon-danger" title="Xóa bình luận" onclick="deleteAdminComment(${c.id})">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

window.toggleReplyForm = (commentId) => {
    const form = document.getElementById(`reply-form-${commentId}`);
    if (form) {
        form.style.display = form.style.display === 'none' ? '' : 'none';
        if (form.style.display !== 'none') {
            form.querySelector('textarea')?.focus();
        }
    }
};

window.submitAdminReply = async (commentId) => {
    const input = document.getElementById(`reply-input-${commentId}`);
    const content = input?.value.trim();
    if (!content) { alert('Vui lòng nhập nội dung phản hồi'); return; }

    const adminUser = JSON.parse(localStorage.getItem('smartfood_user'));
    if (!adminUser) { alert('Vui lòng đăng nhập'); return; }

    try {
        const res = await fetch(`/api/admin/comments/${commentId}/reply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_id: adminUser.id, content })
        });
        const data = await res.json();
        if (data.success) {
            fetchAdminComments();
        } else {
            alert(data.message || 'Lỗi khi gửi phản hồi');
        }
    } catch (e) {
        console.error(e);
        alert('Lỗi kết nối server');
    }
};

window.deleteAdminComment = async (commentId) => {
    if (!confirm('Bạn có chắc muốn xóa bình luận này và tất cả phản hồi liên quan?')) return;
    try {
        const res = await fetch(`/api/admin/comments/${commentId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            fetchAdminComments();
        } else {
            alert(data.message || 'Lỗi khi xóa');
        }
    } catch (e) {
        console.error(e);
    }
};

// Filter change listener
document.getElementById('comment-filter-status')?.addEventListener('change', () => {
    fetchAdminComments();
});

// ============================================
// PAYMENTS TAB
// ============================================

function formatVND(amount) {
    return new Intl.NumberFormat('vi-VN').format(amount) + 'đ';
}

async function fetchPaymentStatsOverview() {
    try {
        const res = await fetch('/api/admin/payment-stats');
        const data = await res.json();
        if (data.success) {
            const stRevenue = document.getElementById('st-revenue');
            if (stRevenue) stRevenue.textContent = formatVND(data.stats.total_revenue || 0);
        }
    } catch (e) { console.warn('Payment stats overview error:', e); }
}

async function fetchAdminPayments() {
    const tb = document.getElementById('tb-payments');
    if (!tb) return;
    tb.innerHTML = '<tr><td colspan="7" style="text-align:center"><i class="fa-solid fa-spinner fa-spin"></i></td></tr>';

    try {
        // Fetch stats and payments in parallel
        const [statsRes, paymentsRes] = await Promise.all([
            fetch('/api/admin/payment-stats'),
            fetch('/api/admin/payments')
        ]);
        const statsData = await statsRes.json();
        const paymentsData = await paymentsRes.json();

        // Update payment stats
        if (statsData.success) {
            const s = statsData.stats;
            const psRevenue = document.getElementById('ps-revenue');
            const psSuccess = document.getElementById('ps-success');
            const psPending = document.getElementById('ps-pending');
            const psFailed = document.getElementById('ps-failed');

            if (psRevenue) psRevenue.textContent = formatVND(s.total_revenue || 0);
            if (psSuccess) psSuccess.textContent = s.success_count || 0;
            if (psPending) psPending.textContent = s.pending_count || 0;
            if (psFailed) psFailed.textContent = s.failed_count || 0;
        }

        // Render payments table
        if (paymentsData.success && paymentsData.payments && paymentsData.payments.length > 0) {
            tb.innerHTML = '';
            paymentsData.payments.forEach(p => {
                const statusMap = {
                    'success': '<span class="badge badge-success"><i class="fa-solid fa-check"></i> Thành công</span>',
                    'pending': '<span class="badge badge-warning"><i class="fa-solid fa-clock"></i> Đang chờ</span>',
                    'failed': '<span class="badge badge-danger"><i class="fa-solid fa-xmark"></i> Thất bại</span>'
                };
                const statusBadge = statusMap[p.status] || `<span class="badge">${p.status}</span>`;

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><code style="font-size:12px;background:rgba(0,0,0,0.05);padding:2px 6px;border-radius:4px;">${p.order_id}</code></td>
                    <td style="font-weight:500">${p.user_name || 'N/A'}</td>
                    <td style="font-weight:600;color:var(--primary)">${formatVND(p.amount)}</td>
                    <td>
                        <span style="display:inline-flex;align-items:center;gap:4px;">
                            <i class="fa-solid fa-credit-card" style="margin-right: 5px;"></i>
                            ${p.method === 'payos' ? 'PayOS' : (p.method || 'PayOS')}
                        </span>
                    </td>
                    <td>${statusBadge}</td>
                    <td><span style="font-size:12px;color:var(--text-muted)">${p.momo_trans_id || '—'}</span></td>
                    <td><span style="font-size:12px;color:var(--text-muted)">${p.created_at || ''}</span></td>
                `;
                tb.appendChild(tr);
            });
        } else {
            tb.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-muted)"><i class="fa-solid fa-receipt" style="font-size:24px;display:block;margin-bottom:8px;"></i>Chưa có giao dịch nào</td></tr>';
        }
    } catch (e) {
        console.error('Payment fetch error:', e);
        tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:red;">Lỗi tải dữ liệu thanh toán</td></tr>';
    }
}
