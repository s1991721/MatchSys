(function () {
    const FinanceUI = window.FinanceUI || {};
    window.FinanceUI = FinanceUI;

    FinanceUI.notifyFinanceParentRoute = function () {
        const route = (window.location.pathname || "").replace(/^\/+/, "");
        if (!route.startsWith("finance/") || route === "finance/my_salary.html") return;
        window.__routeNotified = true;
        try {
            if (!window.top || window.top === window) return;
            const topHash = ((window.top.location && window.top.location.hash) || "")
                .replace(/^#/, "")
                .split("?")[0]
                .split("#")[0];
            if (topHash === route) {
                window.top.location.hash = "finance.html";
            }
        } catch (e) {}
    };

    FinanceUI.applyI18n = function (root = document) {
        if (window.MatchSys && typeof window.MatchSys.applyI18n === "function") {
            window.MatchSys.applyI18n(root);
            return;
        }
        if (window.I18N && typeof window.I18N.init === "function") {
            window.I18N.init();
        }
        if (window.I18N && typeof window.I18N.apply === "function") {
            window.I18N.apply(root);
        }
    };

    FinanceUI.currentLang = function () {
        return window.I18N && typeof window.I18N.getLang === "function" ? window.I18N.getLang() : "zh-CN";
    };

    FinanceUI.t = function (key, fallback) {
        if (!key || !window.I18N || typeof window.I18N.t !== "function") return fallback;
        const value = window.I18N.t(key);
        return value && value !== key ? value : fallback;
    };

    FinanceUI.escapeHtml = function (value) {
        if (typeof window.escapeHtml === "function") return window.escapeHtml(value);
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    };

    FinanceUI.buildFrameSrc = function (route, params = {}) {
        const search = new URLSearchParams();
        Object.entries(params).forEach(([name, value]) => {
            if (value !== undefined && value !== null && value !== "") {
                search.set(name, value);
            }
        });
        const query = search.toString();
        return query ? `${route.src}?${query}` : route.src;
    };

    FinanceUI.syncFrameLang = function (frame) {
        if (!frame || !frame.contentWindow) return;
        try {
            frame.contentWindow.postMessage({ type: "i18n:change", lang: FinanceUI.currentLang() }, "*");
        } catch (e) {}
    };

    FinanceUI.initFrameLangSync = function (frame) {
        if (!frame) return;
        const sync = () => FinanceUI.syncFrameLang(frame);
        frame.addEventListener("load", sync);
        window.addEventListener("i18n:change", sync);
        sync();
    };

    FinanceUI.initSubtabFrame = function (options = {}) {
        FinanceUI.applyI18n();
        const routes = options.routes || {};
        const buttons = Array.from(document.querySelectorAll(options.buttonSelector || "[data-finance-subtab]"));
        const frame = document.querySelector(options.frameSelector || "#financeSubFrame");
        const initialKey = options.initialKey || buttons.find((button) => button.classList.contains("is-active"))?.dataset.financeSubtab;
        const getTitle = (route) => FinanceUI.t(route.titleKey, route.fallbackTitle || route.title || "");
        const setSubtab = (key, params = {}) => {
            const route = routes[key];
            if (!route || !frame) return;
            buttons.forEach((button) => {
                const active = button.dataset.financeSubtab === key;
                button.classList.toggle("is-active", active);
                button.setAttribute("aria-selected", String(active));
            });
            const targetSrc = typeof options.buildFrameSrc === "function"
                ? options.buildFrameSrc(key, route, params)
                : FinanceUI.buildFrameSrc(route, params);
            if (frame.getAttribute("src") !== targetSrc) {
                frame.setAttribute("src", targetSrc);
            }
            frame.setAttribute("title", getTitle(route));
            if (typeof options.onSubtabChange === "function") {
                options.onSubtabChange(key, route, frame);
            }
        };

        buttons.forEach((button) => {
            button.addEventListener("click", () => setSubtab(button.dataset.financeSubtab));
        });
        FinanceUI.initFrameLangSync(frame);
        window.addEventListener("i18n:change", () => {
            FinanceUI.applyI18n();
            const activeKey = buttons.find((button) => button.classList.contains("is-active"))?.dataset.financeSubtab;
            const route = routes[activeKey];
            if (frame && route) frame.setAttribute("title", getTitle(route));
            if (options.titleKey) document.title = FinanceUI.t(options.titleKey, options.fallbackTitle || document.title);
        });
        if (initialKey) setSubtab(initialKey, options.initialParams || {});
        return { setSubtab, frame, buttons };
    };

    FinanceUI.onReady = function (callback) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback);
        } else {
            callback();
        }
    };

    FinanceUI.notifyFinanceParentRoute();
}());
