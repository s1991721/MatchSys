(function () {
    const viewConfig = {
        receivables: {
            html: "finance/receivables.html",
            script: "finance/receivables.js",
            init: "receivables",
        },
        payables: {
            html: "finance/payables.html",
            script: "finance/payables.js",
            init: "payables",
        },
        reimbursements: {
            html: "finance/reimbursements.html",
            script: "finance/reimbursements.js",
            init: "reimbursements",
        },
        payroll: {
            html: "finance/payroll.html",
            script: "finance/payroll.js",
            init: "payroll",
        },
        payments: {
            html: "finance/payments.html",
            script: "finance/payments.js",
            init: "payments",
        },
        reports: {
            html: "finance/reports.html",
            script: "finance/reports.js",
            init: "reports",
        },
        settings: {
            html: "finance/settings.html",
            script: "finance/settings.js",
            init: "settings",
        },
    };

    const loadedScripts = new Set();

    const t = (key, fallback) => {
        const i18n = window.I18N;
        return i18n && typeof i18n.t === "function" ? i18n.t(key) : fallback;
    };

    const applyI18n = (root) => {
        if (window.I18N && typeof window.I18N.apply === "function") {
            window.I18N.apply(root);
        }
    };

    const loadScript = (src) => {
        if (!src || loadedScripts.has(src)) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = src;
            script.onload = () => {
                loadedScripts.add(src);
                resolve();
            };
            script.onerror = () => reject(new Error(`Failed to load ${src}`));
            document.body.appendChild(script);
        });
    };

    const renderState = (container, message, isError) => {
        container.innerHTML = `
            <section class="c-card c-card-pad finance-view">
                <div class="${isError ? "c-empty" : "c-muted"}">${window.escapeHtml ? window.escapeHtml(message) : message}</div>
            </section>
        `;
    };

    const initView = (view, panel) => {
        const registry = window.FinanceViews || {};
        const handler = registry[viewConfig[view].init];
        if (handler && typeof handler.init === "function") {
            handler.init(panel);
        }
    };

    const initSubtabs = (root) => {
        if (!root || root.dataset.subtabsInitialized === "true") return;

        const buttons = Array.from(root.querySelectorAll("[data-finance-subtab]"));
        const panels = Array.from(root.querySelectorAll("[data-finance-subpanel]"));
        if (!buttons.length || !panels.length) return;

        const activate = (subtab) => {
            buttons.forEach((button) => {
                const active = button.dataset.financeSubtab === subtab;
                button.classList.toggle("is-active", active);
                button.setAttribute("aria-selected", String(active));
            });
            panels.forEach((panel) => {
                panel.classList.toggle("hidden", panel.dataset.financeSubpanel !== subtab);
            });
        };

        buttons.forEach((button) => {
            button.addEventListener("click", () => activate(button.dataset.financeSubtab));
        });
        activate((buttons.find((button) => button.classList.contains("is-active")) || buttons[0]).dataset.financeSubtab);
        root.dataset.subtabsInitialized = "true";
    };

    document.addEventListener("DOMContentLoaded", () => {
        const buttons = Array.from(document.querySelectorAll("[data-finance-view]"));
        const container = document.getElementById("financeContent");
        const cachedPanels = new Map();
        let activeView = null;
        let requestId = 0;

        const setButtonState = (view) => {
            buttons.forEach((button) => {
                const active = button.dataset.financeView === view;
                button.classList.toggle("is-active", active);
                button.setAttribute("aria-selected", String(active));
            });
        };

        const showCachedPanel = (view) => {
            cachedPanels.forEach((panel, panelView) => {
                panel.classList.toggle("hidden", panelView !== view);
            });
        };

        const setView = async (view) => {
            const config = viewConfig[view];
            if (!config || !container || activeView === view) {
                return;
            }

            const currentRequestId = ++requestId;
            setButtonState(view);

            if (cachedPanels.has(view)) {
                showCachedPanel(view);
                activeView = view;
                return;
            }

            renderState(container, t("common.loading", "加载中..."), false);

            try {
                const response = await fetch(config.html, { credentials: "same-origin" });
                if (!response.ok) {
                    throw new Error(`${response.status} ${response.statusText}`);
                }

                const wrapper = document.createElement("div");
                wrapper.innerHTML = await response.text();
                const panel = wrapper.firstElementChild;
                if (!panel) {
                    throw new Error(t("common.invalid_response", "无效响应"));
                }
                if (currentRequestId !== requestId) {
                    return;
                }

                container.innerHTML = "";
                cachedPanels.forEach((cachedPanel) => container.appendChild(cachedPanel));
                container.appendChild(panel);
                cachedPanels.set(view, panel);
                showCachedPanel(view);
                activeView = view;

                applyI18n(panel);
                initSubtabs(panel);
                await loadScript(config.script);
                initView(view, panel);
            } catch (error) {
                if (currentRequestId !== requestId) {
                    return;
                }
                renderState(container, `${t("common.load_failed", "加载失败")}：${error.message}`, true);
            }
        };

        buttons.forEach((button) => {
            button.addEventListener("click", () => setView(button.dataset.financeView));
        });

        if (window.I18N && typeof window.I18N.init === "function") {
            window.I18N.init();
        }
        applyI18n(document);
        setView("receivables");
    });
}());
