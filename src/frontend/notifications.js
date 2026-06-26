// ============================================
// CENTRALIZED NOTIFICATIONS & BROADCAST SYNC
// ============================================
(function initCentralizedNotifications() {
    'use strict';
    
    // Khởi tạo BroadcastChannel để đồng bộ trạng thái thông báo giữa các tab
    const bc = new BroadcastChannel('smartfood_notifications');
    let notifPollTimer = null;
    
    // Nghe thông báo từ các tab khác
    bc.onmessage = (event) => {
        if (event.data.type === 'REFRESH_NOTIFICATIONS') {
            const loggedUser = JSON.parse(localStorage.getItem('smartfood_user'));
            if (loggedUser && loggedUser.id) {
                fetchSharedNotifications(loggedUser.id, false); // Fetch without broadcasting back
            }
        }
    };

    function getLoggedUser() {
        try {
            return JSON.parse(localStorage.getItem('smartfood_user'));
        } catch(e) { return null; }
    }

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
            dropdown?.classList.add('hidden');
        }
    });

    // Mark all read
    readAllBtn?.addEventListener('click', async () => {
        const user = getLoggedUser();
        if (!user) return;
        try {
            await fetch(`/api/notifications/${user.id}/read-all`, { method: 'PUT' });
            fetchSharedNotifications(user.id, true);
        } catch (e) { console.error(e); }
    });

    async function fetchSharedNotifications(userId, shouldBroadcast = false) {
        try {
            const res = await fetch(`/api/notifications/${userId}`);
            const data = await res.json();
            if (!data.success) return;

            const badge = document.getElementById('notif-badge');
            const body = document.getElementById('notif-dropdown-body');
            
            if (!badge || !body) return;

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
            } else {
                body.innerHTML = unread.map(n => {
                    const timeStr = n.time ? new Date(n.time).toLocaleString('vi-VN') : '';
                    
                    // Detect icon and type based on content
                    let icon = 'fa-pen-to-square';
                    
                    // Common types logic merged from script.js and admin.js
                    if (n.content.includes('👤') || n.content.includes('đăng ký')) {
                        icon = 'fa-user-plus';
                    } else if (n.content.includes('bình luận') || n.content.includes('phản hồi') || n.content.includes('💬')) {
                        icon = 'fa-comments';
                    } else if (n.content.includes('❌') || n.content.includes('Sai') || n.content.includes('không phù hợp')) {
                        icon = 'fa-circle-xmark';
                    } else if (n.content.includes('⚠️') || n.content.includes('Trung bình')) {
                        icon = 'fa-triangle-exclamation';
                    } else if (n.content.includes('chỉnh sửa') || n.content.includes('sửa') || n.content.includes('cập nhật')) {
                        icon = 'fa-pen-to-square';
                    } else if (n.content.includes('🎉') || n.content.includes('chúc mừng') || n.content.includes('Premium')) {
                        icon = 'fa-crown';
                    }

                    return `
                        <div class="notif-item notif-unread" data-id="${n.id}" data-history="${n.history_id || ''}" 
                             onclick="markSharedNotifRead(${n.id}, '${n.history_id || ''}', this)">
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
            }
            
            // Show bell wrap if hidden
            bellWrap.style.display = '';

            // If triggered by local action, broadcast to other tabs
            if (shouldBroadcast) {
                bc.postMessage({ type: 'REFRESH_NOTIFICATIONS' });
            }
        } catch (e) {
            console.error('Notification fetch error:', e);
        }
    }

    window.markSharedNotifRead = async (notifId, historyId, el) => {
        const user = getLoggedUser();
        if (!user) return;
        
        try {
            // 1. Mark as read on server
            await fetch(`/api/notifications/${notifId}/read`, { method: 'PUT' });
            
            // 2. Remove from dropdown with animation locally
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
            
            // 3. Update badge count locally
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
            
            // 5. Broadcast so other tabs immediately hide this notification
            bc.postMessage({ type: 'REFRESH_NOTIFICATIONS' });
            
            // 6. Navigation logic based on current page and history context
            const currentPath = window.location.pathname;
            
            if (currentPath.includes('admin')) {
                // Admin page navigation routing
                // Simple heuristic based on historyId existing or not
                const targetTab = historyId ? 'admin-history' : 'admin-comments';
                const tabBtn = document.querySelector(`.admin-tab-btn[data-tab="${targetTab}"]`);
                if (tabBtn) tabBtn.click();
            } else {
                // User page navigation routing
                if (currentPath !== '/') {
                    window.location.href = '/#profile';
                } else {
                    window.location.hash = 'profile';
                }
                
                // Wait for page to load then highlight the history card
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
            }
        } catch (e) { console.error(e); }
    };

    // Khởi động
    const initialUser = getLoggedUser();
    if (initialUser && initialUser.id) {
        fetchSharedNotifications(initialUser.id, false);
        if (notifPollTimer) clearInterval(notifPollTimer);
        notifPollTimer = setInterval(() => fetchSharedNotifications(initialUser.id, false), 30000);
    }
})();
