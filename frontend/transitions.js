// ===================================================================
// Page Transitions & Graceful Logout
// Shared across index.html, nutrition.html, admin.html
// ===================================================================

(function () {
    'use strict';

    const LOGOUT_DELAY_MS = 650;
    const NAV_FLAG = 'app:nav';

    // ---------- Toast ----------
    function ensureToastHost() {
        let host = document.getElementById('app-toast-host');
        if (!host) {
            host = document.createElement('div');
            host.id = 'app-toast-host';
            host.className = 'app-toast-host';
            document.body.appendChild(host);
        }
        return host;
    }

    function showToast(message, type = 'success', durationMs = 2200) {
        const host = ensureToastHost();
        const toast = document.createElement('div');
        toast.className = `app-toast app-toast-${type}`;
        const icon = type === 'success' ? 'fa-circle-check'
                   : type === 'error'   ? 'fa-circle-xmark'
                   : type === 'warning' ? 'fa-triangle-exclamation'
                                        : 'fa-circle-info';
        toast.innerHTML = `<i class="fa-solid ${icon}"></i><span>${message}</span>`;
        host.appendChild(toast);

        requestAnimationFrame(() => toast.classList.add('show'));

        setTimeout(() => {
            toast.classList.remove('show');
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 320);
        }, durationMs);

        return toast;
    }

    // ---------- Page veil (cross-page coloured overlay) ----------
    function ensureVeil() {
        let veil = document.getElementById('app-page-veil');
        if (!veil) {
            veil = document.createElement('div');
            veil.id = 'app-page-veil';
            veil.className = 'app-page-veil';
            veil.setAttribute('aria-hidden', 'true');
            // Put veil at the very top of body so it's painted with the first frame.
            if (document.body.firstChild) {
                document.body.insertBefore(veil, document.body.firstChild);
            } else {
                document.body.appendChild(veil);
            }
        }
        return veil;
    }

    function setNavFlag() {
        try { sessionStorage.setItem(NAV_FLAG, '1'); } catch (e) { /* ignore */ }
    }

    function clearNavFlag() {
        try { sessionStorage.removeItem(NAV_FLAG); } catch (e) { /* ignore */ }
    }

    // Fade veil IN before leaving the page.
    function leaveVeilIn() {
        const veil = ensureVeil();
        // Ensure the next opacity change is instantaneous — if the user clicks
        // again while a fade-out is in progress, we must snap to opaque, not
        // continue animating through the 0→1 transition.
        veil.classList.remove('veil-fading-out');
        document.documentElement.classList.add('app-leaving');
    }

    // Fade veil OUT after we arrive on the new page.
    function enterVeilOut() {
        const html = document.documentElement;
        if (!html.classList.contains('app-navigating') && !html.classList.contains('app-leaving')) {
            return;
        }
        const veil = ensureVeil();
        // Two RAFs: first paint the opaque veil, THEN enable the fade-out
        // transition and remove the trigger class. Without this, the veil
        // either snaps to 0 (no animation) or never paints at opacity 1.
        requestAnimationFrame(() => {
            veil.classList.add('veil-fading-out');
            requestAnimationFrame(() => {
                html.classList.remove('app-navigating');
                html.classList.remove('app-leaving');
            });
        });
        // Clean up the helper class after the transition completes so a
        // subsequent leaveVeilIn() snaps back to opaque without animating.
        setTimeout(() => veil.classList.remove('veil-fading-out'), 600);
    }

    // ---------- Graceful logout ----------
    function gracefulLogout(options = {}) {
        const { redirectTo = '/', message = 'Đăng xuất thành công. Hẹn gặp lại!' } = options;

        try { localStorage.removeItem('smartfood_user'); } catch (e) { /* ignore */ }

        showToast(message, 'success', LOGOUT_DELAY_MS + 400);

        setTimeout(() => {
            setNavFlag();
            leaveVeilIn();
        }, 120);
        setTimeout(() => {
            window.location.href = redirectTo;
        }, LOGOUT_DELAY_MS);
    }

    // ---------- Smooth in-app navigation ----------
    function smoothNavigate(url) {
        if (!url || url === '#' || url.startsWith('javascript:')) return;

        // Same-page hash navigation: don't fade, just let the browser handle it
        const isHashOnly = url.startsWith('#') ||
            (url.includes('#') && url.split('#')[0] === window.location.pathname);
        if (isHashOnly) {
            window.location.href = url;
            return;
        }

        // Set flag synchronously so the next page's inline head script can see it.
        setNavFlag();
        leaveVeilIn();
        // Wait for the browser to actually paint the opaque veil before
        // unloading. Without this, paint-hold may capture a frame where the
        // veil hasn't been rendered yet → visible white/content flash.
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                window.location.href = url;
            });
        });
    }

    // ---------- Auto-bind nav links for page-to-page transitions ----------
    const PAGE_PATHS = ['/', '/nutrition', '/admin'];

    function isPageToPageLink(anchor) {
        const href = anchor.getAttribute('href');
        if (!href) return false;
        if (anchor.target && anchor.target !== '_self') return false;
        if (anchor.hasAttribute('download')) return false;
        if (href.startsWith('http://') || href.startsWith('https://')) {
            try {
                const u = new URL(href);
                if (u.origin !== window.location.origin) return false;
            } catch (e) { return false; }
        }
        const path = href.split('?')[0].split('#')[0];
        if (!path) return false;
        const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
        const targetPath = path.replace(/\/$/, '') || '/';
        if (targetPath === currentPath) return false;
        return PAGE_PATHS.includes(targetPath);
    }

    // ---------- Prefetch on hover/focus for snappier perceived nav ----------
    const prefetched = new Set();
    function prefetch(url) {
        if (!url || prefetched.has(url)) return;
        prefetched.add(url);
        try {
            const link = document.createElement('link');
            link.rel = 'prefetch';
            link.href = url;
            link.as = 'document';
            document.head.appendChild(link);
        } catch (e) { /* ignore */ }
    }

    function handleLinkHover(e) {
        const anchor = e.target.closest && e.target.closest('a');
        if (!anchor || !isPageToPageLink(anchor)) return;
        prefetch(anchor.getAttribute('href'));
    }

    function handleLinkClick(e) {
        const anchor = e.target.closest('a');
        if (!anchor) return;
        if (e.defaultPrevented) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        if (e.button !== 0) return;
        if (!isPageToPageLink(anchor)) return;

        e.preventDefault();
        smoothNavigate(anchor.getAttribute('href'));
    }

    // ---------- Background food icons (decorative) ----------
    const FOOD_ICONS = [
        { cls: 'fa-pizza-slice',  top: '8%',  left: '4%',  size: 42, rot: -15, dur: 18, delay: 0,   color: '#f59e0b' },
        { cls: 'fa-bowl-rice',    top: '16%', left: '92%', size: 50, rot: 12,  dur: 24, delay: -2,  color: '#22c55e' },
        { cls: 'fa-fish',         top: '30%', left: '3%',  size: 38, rot: -8,  dur: 20, delay: -4,  color: '#06b6d4' },
        { cls: 'fa-burger',       top: '42%', left: '95%', size: 46, rot: 18,  dur: 22, delay: -1,  color: '#ef4444' },
        { cls: 'fa-ice-cream',    top: '56%', left: '6%',  size: 36, rot: -20, dur: 19, delay: -5,  color: '#ec4899' },
        { cls: 'fa-apple-whole',  top: '70%', left: '94%', size: 38, rot: 10,  dur: 21, delay: -3,  color: '#ef4444' },
        { cls: 'fa-cookie',       top: '82%', left: '8%',  size: 42, rot: -12, dur: 23, delay: -6,  color: '#d97706' },
        { cls: 'fa-cake-candles', top: '10%', left: '46%', size: 32, rot: 5,   dur: 25, delay: -2.5,color: '#ec4899' },
        { cls: 'fa-mug-hot',      top: '88%', left: '52%', size: 36, rot: -5,  dur: 18, delay: -4.5,color: '#92400e' },
        { cls: 'fa-carrot',       top: '24%', left: '70%', size: 36, rot: 25,  dur: 22, delay: -1.5,color: '#f97316' },
        { cls: 'fa-egg',          top: '54%', left: '50%', size: 28, rot: -10, dur: 17, delay: -3.5,color: '#fbbf24' },
        { cls: 'fa-lemon',        top: '38%', left: '48%', size: 32, rot: 15,  dur: 20, delay: -5.5,color: '#facc15' },
        { cls: 'fa-pepper-hot',   top: '66%', left: '40%', size: 32, rot: -25, dur: 19, delay: -0.5,color: '#dc2626' },
        { cls: 'fa-cheese',       top: '6%',  left: '74%', size: 38, rot: 8,   dur: 24, delay: -2,  color: '#fbbf24' },
        { cls: 'fa-bread-slice',  top: '92%', left: '78%', size: 40, rot: -18, dur: 21, delay: -4,  color: '#d97706' }
    ];

    function injectBackgroundFoodIcons() {
        if (document.querySelector('.bg-food-icons')) return;
        if (document.body.dataset.noFoodIcons === 'true') return;

        const container = document.createElement('div');
        container.className = 'bg-food-icons';
        container.setAttribute('aria-hidden', 'true');

        const frag = document.createDocumentFragment();
        FOOD_ICONS.forEach((cfg, i) => {
            const span = document.createElement('span');
            span.className = `bg-food-icon bg-food-icon-${i + 1}`;
            span.style.top = cfg.top;
            span.style.left = cfg.left;
            span.style.fontSize = `${cfg.size}px`;
            span.style.color = cfg.color;
            span.style.setProperty('--icon-rot', `${cfg.rot}deg`);
            span.style.setProperty('--icon-dur', `${cfg.dur}s`);
            span.style.setProperty('--icon-delay', `${cfg.delay}s`);
            span.innerHTML = `<i class="fa-solid ${cfg.cls}"></i>`;
            frag.appendChild(span);
        });
        container.appendChild(frag);

        if (document.body.firstChild) {
            document.body.insertBefore(container, document.body.firstChild);
        } else {
            document.body.appendChild(container);
        }
    }

    // ---------- Restore body when coming back via bfcache ----------
    function handlePageShow(e) {
        if (e.persisted) {
            document.documentElement.classList.remove('app-leaving');
            document.documentElement.classList.remove('app-navigating');
            clearNavFlag();
        }
    }

    // ---------- Floating Upgrade Button ----------
    function injectFloatingUpgradeButton() {
        try {
            const userJson = localStorage.getItem('smartfood_user');
            if (!userJson) return;
            const user = JSON.parse(userJson);
            if (user && user.account_type === 'premium') return;
            
            if (document.getElementById('floating-upgrade-btn')) return;

            const btn = document.createElement('a');
            btn.id = 'floating-upgrade-btn';
            btn.className = 'floating-upgrade-btn';
            
            // If on index, trigger modal. Else, navigate to /?upgrade=true
            if (window.location.pathname === '/' || window.location.pathname === '') {
                btn.href = '#';
                btn.onclick = function(e) {
                    e.preventDefault();
                    if (typeof window.showUpgradeModal === 'function') {
                        window.showUpgradeModal();
                    } else {
                        window.location.href = '/?upgrade=true';
                    }
                };
            } else {
                btn.href = '/?upgrade=true';
            }
            
            btn.innerHTML = `
                <div class="fub-glow"></div>
                <div class="fub-content">
                    <i class="fa-solid fa-crown"></i>
                    <span>Nâng Cấp Premium</span>
                </div>
            `;
            
            document.body.appendChild(btn);
        } catch (e) { /* ignore */ }
    }

    // ---------- Boot ----------
    function boot() {
        ensureVeil();

        // If the previous page set the nav flag, we arrived via smoothNavigate
        // — the inline head script will have added html.app-navigating already,
        // so the veil is currently opaque. Fade it out now.
        clearNavFlag();
        enterVeilOut();

        document.addEventListener('click', handleLinkClick, true);
        // Prefetch on hover/focus for snappier transitions.
        document.addEventListener('mouseover', handleLinkHover, { passive: true });
        document.addEventListener('focusin', handleLinkHover, { passive: true });
        window.addEventListener('pageshow', handlePageShow);
        injectBackgroundFoodIcons();
        injectFloatingUpgradeButton();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

    // Expose API
    window.gracefulLogout = gracefulLogout;
    window.smoothNavigate = smoothNavigate;
    window.appToast = showToast;
})();
