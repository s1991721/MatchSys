(function () {
    const i18n = window.I18N || null;
    const t = (key, fallback) => (i18n && typeof i18n.t === "function" ? i18n.t(key) : fallback);
    // 接口校验登录
    window.fetchWithAuth = async function (url, options = {}) {
        const mergedOptions = {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            credentials: "include",
            ...options,
        };
        const res = await fetch(url, mergedOptions);
        if (res.status === 401) {
            window.location.href = "/login.html";
            throw new Error("Unauthorized");
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
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

    //获取当前月
    window.getCurrentMonth = function () {
        const today = new Date();
        const month = String(today.getMonth() + 1).padStart(2, "0");
        return `${today.getFullYear()}-${month}`;
    };

    // 日期格式化
    window.formatDate = function (raw) {
        if (!raw) return "";
        const d = new Date(raw);
        if (Number.isNaN(d.getTime())) return raw;
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${day}`;
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

    // 根据契约类型返回字符串
    window.contractTypeToLabel = function (value) {
        const i18n = window.I18N;
        const t = (key, fallback) => (i18n && typeof i18n.t === "function" ? i18n.t(key) : fallback);
        const mapping = {
            1: t("people.contract.regular", "正社员"),
            2: t("people.contract.contract", "契约社员"),
            3: t("people.contract.freelance", "フリーランス")
        };
        return mapping[value] || t("people.contract.unknown", "未定");
    };

    // 分页页码构建
    window.buildPageItems = function (totalPages, activePage) {
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

        const prevBtn = document.createElement("button");
        prevBtn.type = "button";
        prevBtn.className = "c-btn c-btn-ghost c-btn-sm";
        prevBtn.dataset.page = "prev";
        prevBtn.textContent = t("pagination.prev", "上一页");
        prevBtn.disabled = safeCurrentPage <= 1;
        paginationEl.appendChild(prevBtn);

        if (!pagesEl) {
            pagesEl = document.createElement("div");
            pagesEl.className = "pagination-pages";
        }
        pagesEl.innerHTML = "";
        const pageItems = window.buildPageItems(safeTotalPages, safeCurrentPage);
        pagesEl.append(...pageItems.map((page) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "c-btn c-btn-ghost c-btn-sm";
            btn.textContent = String(page);
            if (page === "…") {
                btn.disabled = true;
                btn.classList.add("is-ellipsis");
                return btn;
            }
            btn.dataset.page = String(page);
            if (page === safeCurrentPage) {
                btn.classList.add("is-active");
            }
            return btn;
        }));
        paginationEl.appendChild(pagesEl);

        const nextBtn = document.createElement("button");
        nextBtn.type = "button";
        nextBtn.className = "c-btn c-btn-ghost c-btn-sm";
        nextBtn.dataset.page = "next";
        nextBtn.textContent = t("pagination.next", "下一页");
        nextBtn.disabled = safeCurrentPage >= safeTotalPages;
        paginationEl.appendChild(nextBtn);
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

    const notifyParentRoute = () => {
        if (window.__routeNotified) return;
        if (!window.top || window.top === window) return;
        const path = window.location.pathname || "";
        const parts = path.split("/").filter(Boolean);
        const filename = parts.length ? parts[parts.length - 1] : "";
        if (!filename || !filename.endsWith(".html")) return;
        try {
            const topHash = (window.top.location && window.top.location.hash) || "";
            const normalizedTop = topHash.replace(/^#/, "").split("?")[0].split("#")[0];
            if (normalizedTop === filename) {
                window.__routeNotified = true;
                return;
            }
            window.top.postMessage({ type: "route:change", src: filename }, "*");
            window.__routeNotified = true;
        } catch (e) {}
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", notifyParentRoute);
    } else {
        notifyParentRoute();
    }
})();
