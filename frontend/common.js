(function () {
    const MatchSys = window.MatchSys || {};
    window.MatchSys = MatchSys;

    const getI18n = () => window.I18N || null;
    const t = (key, fallback) => {
        const i18n = getI18n();
        return i18n && typeof i18n.t === "function" ? i18n.t(key) : fallback;
    };
    const format = (key, vars, fallback) => {
        const i18n = getI18n();
        return i18n && typeof i18n.format === "function" ? i18n.format(key, vars) : (fallback || key);
    };

    const resolveLabel = (key, fallback) => {
        const value = t(key, fallback);
        return value === key ? fallback : value;
    };
    const pad2 = (value) => String(value).padStart(2, "0");
    window.pad2 = pad2;

    const getCommonScriptUrl = () => {
        const current = document.currentScript && document.currentScript.src;
        if (current) return current;
        const scripts = Array.from(document.scripts || []);
        const commonScript = scripts.find((script) => {
            const src = script.getAttribute("src") || "";
            return /(^|\/)common\.js(?:[?#].*)?$/.test(src);
        });
        return commonScript ? commonScript.src : "";
    };

    const commonScriptUrl = getCommonScriptUrl();
    const appBaseUrl = (() => {
        try {
            return new URL(".", commonScriptUrl || window.location.href);
        } catch (e) {
            return new URL(".", window.location.href);
        }
    })();

    MatchSys.getAppBaseUrl = function () {
        return appBaseUrl.toString();
    };

    MatchSys.normalizeAppRoute = function (value) {
        const raw = String(value || "").trim().replace(/^#/, "");
        if (!raw) return "";
        let url;
        try {
            url = new URL(raw, appBaseUrl);
        } catch (e) {
            return raw.replace(/^#/, "").replace(/^\/+/, "");
        }
        if (url.origin !== window.location.origin) return raw;
        const basePath = appBaseUrl.pathname.endsWith("/") ? appBaseUrl.pathname : `${appBaseUrl.pathname}/`;
        let path = url.pathname || "";
        if (path.startsWith(basePath)) {
            path = path.slice(basePath.length);
        } else {
            path = path.replace(/^\/+/, "");
        }
        const baseSegment = basePath.replace(/^\/+|\/+$/g, "").split("/").filter(Boolean).pop();
        if (baseSegment && path.startsWith(`${baseSegment}/`)) {
            path = path.slice(baseSegment.length + 1);
        }
        return `${path}${url.search || ""}${url.hash || ""}`.replace(/^\/+/, "");
    };

    MatchSys.buildAppUrl = function (route) {
        return new URL(MatchSys.normalizeAppRoute(route), appBaseUrl).toString();
    };

    const AUTH_STORAGE_KEYS = [
        "app_employee_id",
        "app_employee_name",
        "app_employee_position_name",
        "app_role_id",
        "app_menu_list",
    ];
    const LOGIN_REQUIRED_CODE = 100401;
    const ACTIVATION_REQUIRED_CODE = 100410;

    const clearAuthState = () => {
        AUTH_STORAGE_KEYS.forEach((key) => {
            try {
                localStorage.removeItem(key);
            } catch (e) {}
        });
    };

    window.escapeHtml = function (value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    };

    const isFreshPayload = (payload, maxAgeMs = 30 * 60 * 1000) => {
        if (!payload || typeof payload !== "object") return false;
        const ts = Number(payload.updatedAt);
        if (!Number.isFinite(ts)) return false;
        return Math.abs(Date.now() - ts) <= maxAgeMs;
    };

    const readJSONFromWebStorage = (storage, key, maxAgeMs) => {
        try {
            const payload = JSON.parse(storage.getItem(key) || "null");
            if (isFreshPayload(payload, maxAgeMs)) {
                return payload;
            }
            storage.removeItem(key);
            return null;
        } catch {
            storage.removeItem(key);
            return null;
        }
    };

    const writeJSONToWebStorage = (storage, key, value) => {
        storage.setItem(key, JSON.stringify(value));
    };

    MatchSys.writeJSONToSessionStorage = function (key, value) {
        writeJSONToWebStorage(sessionStorage, key, value);
    };

    MatchSys.writeJSONToLocalStorage = function (key, value) {
        writeJSONToWebStorage(localStorage, key, value);
    };

    MatchSys.readJSONFromSessionStorage = function (key, maxAgeMs) {
        return readJSONFromWebStorage(sessionStorage, key, maxAgeMs);
    };

    MatchSys.readJSONFromLocalStorage = function (key, maxAgeMs) {
        return readJSONFromWebStorage(localStorage, key, maxAgeMs);
    };

    MatchSys.clearStoredKey = function (key) {
        sessionStorage.removeItem(key);
        localStorage.removeItem(key);
    };

    const ORIGINAL_MESSAGE_SEPARATOR = "---------- Original Message ----------";

    MatchSys.buildQuotedReplyBody = function (replyBody, originalMail) {
        const content = String(replyBody == null ? "" : replyBody)
            .replace(/\r\n?/g, "\n")
            .trimEnd();
        if (!originalMail || content.includes(ORIGINAL_MESSAGE_SEPARATOR)) {
            return content;
        }

        const from = String(originalMail.from || originalMail.address || "").trim();
        const date = String(originalMail.date || originalMail.time || "").trim();
        const subject = String(
            originalMail.subject || originalMail.title || originalMail.name || ""
        ).trim();
        const originalBody = String(originalMail.body || originalMail.detail || "")
            .replace(/\r\n?/g, "\n")
            .trimEnd();
        const quotedBody = originalBody
            ? originalBody.split("\n").map((line) => line ? `> ${line}` : ">").join("\n")
            : ">";

        return [
            content,
            "",
            "",
            ORIGINAL_MESSAGE_SEPARATOR,
            `From: ${from}`,
            `Date: ${date}`,
            `Subject: ${subject}`,
            "",
            quotedBody,
        ].join("\n");
    };

    window.getAppLocale = function () {
        const i18n = getI18n();
        return i18n && typeof i18n.getLang === "function" && i18n.getLang() === "ja" ? "ja-JP" : "zh-CN";
    };

    const redirectAuthFailure = (reason = "login") => {
        if (window.__authRedirecting) return;
        window.__authRedirecting = true;
        const target = reason === "activation" ? "login.html?activation=1" : "login.html";
        const nextUrl = MatchSys.buildAppUrl(target);
        clearAuthState();
        window.top.location.replace(nextUrl);
    };

    MatchSys.redirectAuthFailure = redirectAuthFailure;
    MatchSys.isAuthRedirecting = function () {
        return window.__authRedirecting === true;
    };

    MatchSys.navigateAppRoute = function (src) {
        const route = MatchSys.normalizeAppRoute(src);
        if (!route) return;
        if (window.top && window.top !== window) {
            window.top.postMessage({type: "route:change", src: route}, "*");
        } else {
            window.location.href = MatchSys.buildAppUrl(route);
        }
    };
    window.navigateAppRoute = MatchSys.navigateAppRoute;

    const LOCALIZED_FILE_SKIP_SELECTOR = [
        ".songxin-upload-bar",
        ".file-picker",
        "[data-file-i18n-skip='1']",
    ].join(", ");

    const ensureFileInputId = (input, index) => {
        if (input.id) return input.id;
        let generated = `file-input-${index}`;
        let suffix = 1;
        while (document.getElementById(generated)) {
            generated = `file-input-${index}-${suffix}`;
            suffix += 1;
        }
        input.id = generated;
        return generated;
    };

    const getLocalizedNoFileText = () => resolveLabel("common.file.none", "未选择文件");

    const formatSelectedFileText = (input) => {
        const files = input && input.files ? Array.from(input.files) : [];
        if (!files.length) return getLocalizedNoFileText();
        const first = files[0] && files[0].name ? files[0].name : "";
        if (files.length === 1) return first || getLocalizedNoFileText();
        const rest = files.length - 1;
        return `${first} +${rest}`;
    };

    const updateLocalizedFileText = (input) => {
        if (!input) return;
        const textEl = input.__localizedFileTextEl;
        if (!textEl) return;
        textEl.textContent = formatSelectedFileText(input);
    };

    const enhanceFileInput = (input, index) => {
        if (!input || input.dataset.fileI18nEnhanced === "1") return;
        if (input.closest(LOCALIZED_FILE_SKIP_SELECTOR)) return;
        const inputId = ensureFileInputId(input, index);
        const wrapper = document.createElement("div");
        wrapper.className = "c-file-picker";
        wrapper.setAttribute("data-file-i18n-wrapper", "1");

        const trigger = document.createElement("label");
        trigger.className = "c-btn c-btn-secondary c-btn-sm";
        trigger.setAttribute("for", inputId);
        trigger.setAttribute("data-i18n", "common.file.choose");
        trigger.textContent = resolveLabel("common.file.choose", "选择文件");

        const name = document.createElement("span");
        name.className = "c-file-picker-name";
        name.textContent = getLocalizedNoFileText();

        wrapper.appendChild(trigger);
        wrapper.appendChild(name);

        input.classList.add("c-file-picker-native");
        input.dataset.fileI18nEnhanced = "1";
        input.__localizedFileTextEl = name;
        input.addEventListener("change", () => updateLocalizedFileText(input));
        input.insertAdjacentElement("afterend", wrapper);
        updateLocalizedFileText(input);
    };

    const initLocalizedFileInputs = () => {
        const fileInputs = document.querySelectorAll("input[type='file']");
        fileInputs.forEach((input, index) => enhanceFileInput(input, index));
        fileInputs.forEach((input) => updateLocalizedFileText(input));
        if (window.I18N && typeof window.I18N.apply === "function") {
            window.I18N.apply(document);
        }
    };

    const translateApiError = (payload, fallback) => {
        const responsePayload = payload && typeof payload === "object" ? payload : {};
        const fallbackMessage = fallback || responsePayload.message || t("common.load_failed", "Load failed");
        const errorCodeMessages = window.ErrorCodeMessages;
        if (errorCodeMessages && typeof errorCodeMessages.getMessage === "function") {
            const message = errorCodeMessages.getMessage(responsePayload);
            if (message) return message;
        }
        return fallbackMessage;
    };
    window.translateApiError = translateApiError;

    // 接口校验登录
    window.fetchWithAuth = async function (url, options = {}) {
        const mergedOptions = {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            credentials: "include",
            ...options,
        };
        const res = await fetch(url, mergedOptions);
        if (!res.ok) {
            const payload = await res.json().catch(() => ({}));
            const message = translateApiError(payload, `HTTP ${res.status}`);
            if (res.status === 401 && Number(payload?.code) === LOGIN_REQUIRED_CODE) {
                redirectAuthFailure("login");
                const error = new Error(message);
                error.payload = payload;
                error.code = payload?.code;
                throw error;
            }
            if (res.status === 403 && Number(payload?.code) === ACTIVATION_REQUIRED_CODE) {
                redirectAuthFailure("activation");
            }
            const error = new Error(message);
            error.payload = payload;
            error.code = payload?.code;
            throw error;
        }
        return res;
    };

    // 构建GET请求params
    window.createParams = function (entries = []) {
        const params = new URLSearchParams();
        entries.forEach(([key, value]) => {
            if (value) {
                params.set(key, value);
            }
        });
        return params;
    };

    // 构建GET请求URL
    window.buildUrl = function (base, params) {
        const query = params.toString();
        return query ? `${base}?${query}` : base;
    };

    // 接口返回处理
    window.normalizeApiResponse = function (raw) {
        if (raw && typeof raw === "object" && "success" in raw) {
            return raw;
        }
        return {
            success: false,
            code: "ERR_INVALID_RESPONSE",
            message: t("common.invalid_response", "Invalid response"),
            data: null,
            meta: {},
        };
    };

    window.requestJson = async function (url, options = {}, settings = {}) {
        const response = await window.fetchWithAuth(url, options);
        const raw = await response.json();
        const payload = window.normalizeApiResponse(raw);
        if (!payload.success) {
            const message = translateApiError(
                payload,
                settings.fallbackMessage || t("common.load_failed", "Load failed")
            );
            const error = new Error(message);
            error.payload = payload;
            error.code = payload.code;
            throw error;
        }
        return payload;
    };

    MatchSys.verifySession = async function () {
        if (MatchSys.isAuthRedirecting()) return false;
        const payload = await window.requestJson("/api/session/status", {
            method: "GET",
            cache: "no-store",
        });
        if (payload.data?.authenticated !== true) {
            throw new Error("Invalid session status response");
        }
        return true;
    };

    //获取当前月
    window.getCurrentMonth = function () {
        const today = new Date();
        return `${today.getFullYear()}-${pad2(today.getMonth() + 1)}`;
    };

    // 日期格式化
    window.formatDate = function (raw) {
        if (!raw) return "";
        const d = new Date(raw);
        if (Number.isNaN(d.getTime())) return raw;
        const y = d.getFullYear();
        const m = pad2(d.getMonth() + 1);
        const day = pad2(d.getDate());
        return `${y}-${m}-${day}`;
    };

    window.datePart = function (value) {
        if (!value) return "";
        const text = String(value);
        return text.length >= 10 ? text.slice(0, 10) : text;
    };

    window.formatLocaleDate = function (raw, fallback = "") {
        if (!raw) return fallback;
        const date = new Date(raw);
        if (Number.isNaN(date.getTime())) return String(raw);
        return date.toLocaleDateString(window.getAppLocale());
    };

    window.formatMonthDay = function (raw, fallback = "") {
        if (!raw) return fallback;
        const date = new Date(raw);
        if (Number.isNaN(date.getTime())) return String(raw);
        return `${date.getMonth() + 1}月${date.getDate()}日`;
    };

    window.formatMonthDayTime = function (raw, fallback = "") {
        if (!raw) return fallback;
        const date = new Date(raw);
        if (Number.isNaN(date.getTime())) return String(raw);
        return [
            `${date.getMonth() + 1}月${date.getDate()}日`,
            `${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`,
        ].join(" ");
    };

    // 根据生日计算年龄
    window.calcAge = function (birthday) {
        if (!birthday) return null;
        const date = new Date(birthday);
        if (Number.isNaN(date.getTime())) return null;
        const today = new Date();
        let age = today.getFullYear() - date.getFullYear();
        const m = today.getMonth() - date.getMonth();
        if (m < 0 || (m === 0 && today.getDate() < date.getDate())) {
            age -= 1;
        }
        return age;
    };

    // 分页页码构建
    const buildPageItems = (totalPages, activePage) => {
        if (totalPages <= 7) {
            return Array.from({length: totalPages}, (_, i) => i + 1);
        }
        const pages = [1];
        const start = Math.max(2, activePage - 1);
        const end = Math.min(totalPages - 1, activePage + 1);
        if (start > 2) pages.push("…");
        for (let i = start; i <= end; i += 1) pages.push(i);
        if (end < totalPages - 1) pages.push("…");
        pages.push(totalPages);
        return pages;
    };

    const createPaginationButton = (label, page, options = {}) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "c-btn c-btn-ghost c-btn-sm";
        btn.textContent = String(label);
        if (page) {
            btn.dataset.page = String(page);
        }
        if (options.disabled) {
            btn.disabled = true;
        }
        if (options.active) {
            btn.classList.add("is-active");
        }
        if (options.ellipsis) {
            btn.classList.add("is-ellipsis");
        }
        return btn;
    };

    // 渲染分页
    window.renderPagination = function (paginationEl, pagesEl, currentPage, totalPages) {
        if (!paginationEl) return;
        const safeTotalPages = Math.max(1, totalPages || 1);
        const safeCurrentPage = Math.min(Math.max(1, currentPage || 1), safeTotalPages);
        if (!pagesEl) {
            pagesEl = paginationEl.querySelector(".pagination-pages");
        }
        const summaryEl = paginationEl.querySelector(".pagination-summary");
        paginationEl.innerHTML = "";
        if (summaryEl) {
            paginationEl.appendChild(summaryEl);
        }

        paginationEl.appendChild(createPaginationButton(
            t("common.pagination.prev", "上一页"),
            "prev",
            {disabled: safeCurrentPage <= 1}
        ));

        if (!pagesEl) {
            pagesEl = document.createElement("div");
            pagesEl.className = "pagination-pages";
        }
        pagesEl.innerHTML = "";
        const pageItems = buildPageItems(safeTotalPages, safeCurrentPage);
        pagesEl.append(...pageItems.map((page) => {
            if (page === "…") {
                return createPaginationButton(page, "", {disabled: true, ellipsis: true});
            }
            return createPaginationButton(page, page, {active: page === safeCurrentPage});
        }));
        paginationEl.appendChild(pagesEl);

        paginationEl.appendChild(createPaginationButton(
            t("common.pagination.next", "下一页"),
            "next",
            {disabled: safeCurrentPage >= safeTotalPages}
        ));
    };

    // 分页点击绑定（通过钩子处理具体逻辑）
    window.bindPagination = function (paginationEl, onPageChange) {
        if (!paginationEl || typeof onPageChange !== "function") return;
        paginationEl.addEventListener("click", (event) => {
            const btn = event.target.closest("button[data-page]");
            if (!btn) return;
            onPageChange(btn.dataset.page || "");
        });
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initLocalizedFileInputs, { once: true });
    } else {
        initLocalizedFileInputs();
    }
    window.addEventListener("i18n:change", initLocalizedFileInputs);

    window.startTopbarBadgePolling = function (options = {}) {
        const intervalMs = Math.max(60 * 1000, Number(options.intervalMs || 5 * 60 * 1000));
        const onData = typeof options.onData === "function" ? options.onData : function () {};
        const autoStart = options.autoStart !== false;
        let pendingTick = null;

        if (window.__topbarBadgePollingTimer) {
            clearInterval(window.__topbarBadgePollingTimer);
            window.__topbarBadgePollingTimer = null;
        }

        const tick = () => {
            if (pendingTick) return pendingTick;
            pendingTick = (async () => {
                try {
                    const payload = await window.requestJson("/api/home/topbar-badges", {
                        method: "GET",
                        cache: "no-store",
                    });
                    if (!payload || payload.success === false) {
                        onData({ badges: {}, error: true });
                        return;
                    }
                    onData(payload.data || {});
                } catch (error) {
                    onData({ badges: {}, error: true });
                }
            })().finally(() => {
                pendingTick = null;
            });
            return pendingTick;
        };

        // 手动刷新复用轮询请求，不改变现有轮询周期。
        window.refreshTopbarBadges = tick;

        const start = () => {
            if (window.__topbarBadgePollingTimer) return;
            tick();
            window.__topbarBadgePollingTimer = setInterval(tick, intervalMs);
        };

        const stop = () => {
            if (!window.__topbarBadgePollingTimer) return;
            clearInterval(window.__topbarBadgePollingTimer);
            window.__topbarBadgePollingTimer = null;
        };

        if (autoStart) {
            start();
        }
        return { start, stop, tick };
    };

    // 统一 dialog 关闭逻辑：仅通过显式关闭按钮关闭，并阻止 Esc 默认关闭。
    window.initDialogCloseBehavior = function (options = {}) {
        const root = options.root || document;
        const closeSelector = options.closeSelector || "[data-dialog-close]";
        const dialogs = Array.isArray(options.dialogs)
            ? options.dialogs.filter(Boolean)
            : Array.from(root.querySelectorAll("dialog"));
        const onClose = typeof options.onClose === "function" ? options.onClose : null;

        dialogs.forEach((dialog) => {
            if (dialog.__dialogCancelBound) return;
            dialog.addEventListener("cancel", (event) => {
                event.preventDefault();
            });
            dialog.__dialogCancelBound = true;
        });

        if (root.__dialogCloseDelegated) return;
        root.addEventListener("click", (event) => {
            const closer = event.target.closest(closeSelector);
            if (!closer) return;
            const dialog = closer.closest("dialog");
            if (!dialog) return;
            event.preventDefault();
            if (onClose) {
                const shouldContinue = onClose(dialog, closer);
                if (shouldContinue === false) return;
            }
            if (typeof dialog.close === "function") {
                dialog.close();
            } else {
                dialog.removeAttribute("open");
            }
        });
        root.__dialogCloseDelegated = true;
    };

    const notifyParentRoute = () => {
        if (window.__routeNotified) return;
        if (!window.top || window.top === window) return;
        if (window.parent && window.parent !== window.top) return;
        const route = MatchSys.normalizeAppRoute(window.location.href);
        const routePath = route.split("?")[0].split("#")[0];
        if (!routePath || !routePath.endsWith(".html")) return;
        try {
            const topHash = (window.top.location && window.top.location.hash) || "";
            const normalizedTop = MatchSys.normalizeAppRoute(topHash).split("?")[0].split("#")[0];
            if (normalizedTop === routePath) {
                window.__routeNotified = true;
                return;
            }
            window.top.postMessage({ type: "route:change", src: route }, "*");
            window.__routeNotified = true;
        } catch (e) {}
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", notifyParentRoute);
    } else {
        notifyParentRoute();
    }
})();
