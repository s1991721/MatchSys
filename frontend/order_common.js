(function () {
    const i18n = window.I18N;
    const t = (key) => (i18n ? i18n.t(key) : key);
    const format = (key, vars, fallback) => (i18n ? i18n.format(key, vars, fallback) : (fallback || key));
    const formatDateValue = window.datePart;

    const statusClass = {
        "草稿": "c-tag-neutral",
        "已创建": "c-tag-neutral",
        "承认中": "c-tag-warn",
        "已承认": "c-tag-success",
        "已送付": "c-tag-info",
        "已受注": "c-tag-success",
        "已取消": "c-tag-danger",
        "拒绝": "c-tag-danger"
    };
    const statusLabelMap = {
        "草稿": "common.status.draft",
        "已创建": "order.status.created",
        "承认中": "order.status.approving",
        "已承认": "order.status.approved",
        "已送付": "order.status.sent",
        "已受注": "order.status.accepted",
        "已取消": "order.status.canceled",
        "拒绝": "order.status.rejected"
    };

    const readOwnerSelect = (selectEl) => {
        if (!selectEl) return { id: null, name: "" };
        const selected = selectEl.options[selectEl.selectedIndex];
        const idValue = selected ? Number(selected.value) : null;
        return {
            id: Number.isFinite(idValue) && idValue ? idValue : null,
            name: selected ? selected.textContent.trim() : "",
        };
    };

    const setFieldValue = (field, value = "") => {
        if (!field) return;
        field.value = value === null || value === undefined ? "" : String(value);
    };

    const setFieldValues = (entries) => {
        entries.forEach(([field, value]) => setFieldValue(field, value));
    };

    const clearFields = (fields) => {
        fields.forEach((field) => setFieldValue(field, ""));
    };

    const createOption = (value, label = value) => {
        const opt = document.createElement("option");
        opt.value = String(value ?? "");
        opt.textContent = String(label ?? value ?? "");
        return opt;
    };

    const debounce = (fn, delay = 250) => {
        let timer = null;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    };

    const parseMoneyValue = (value) => {
        const raw = String(value || "").replace(/[^\d.-]/g, "");
        const number = Number(raw);
        return Number.isFinite(number) ? number : 0;
    };

    const formatBlankValue = (value) => {
        if (value === null || value === undefined || value === "") return "-";
        return String(value);
    };

    const formatYenValue = (value) => {
        const number = Number(value || 0);
        return `¥ ${number.toLocaleString("ja-JP", { maximumFractionDigits: 0 })}`;
    };

    const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[char]));

    const getDateParts = (date = new Date()) => {
        const yyyy = date.getFullYear();
        const mm = String(date.getMonth() + 1).padStart(2, "0");
        const dd = String(date.getDate()).padStart(2, "0");
        const hh = String(date.getHours()).padStart(2, "0");
        const mi = String(date.getMinutes()).padStart(2, "0");
        const ss = String(date.getSeconds()).padStart(2, "0");
        return { yyyy, mm, dd, hh, mi, ss };
    };

    const todayText = () => {
        const { yyyy, mm, dd } = getDateParts();
        return `${yyyy}-${mm}-${dd}`;
    };

    const buildIssueOrderNo = () => {
        const { yyyy, mm, dd, hh, mi, ss } = getDateParts();
        return `P_${yyyy}${mm}${dd}${hh}${mi}${ss}`;
    };

    const buildPeriodText = (start, end) => {
        if (start && end) return `${start} ～ ${end}`;
        return start || end || "";
    };

    const readBlobAsBase64 = (blob) => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = String(reader.result || "");
            resolve(result.includes(",") ? result.split(",").pop() : result);
        };
        reader.onerror = () => reject(reader.error || new Error("文件读取失败"));
        reader.readAsDataURL(blob);
    });

    const createActionIcon = (name) => {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("width", "14");
        svg.setAttribute("height", "14");
        svg.setAttribute("fill", "none");
        svg.setAttribute("stroke", "currentColor");
        svg.setAttribute("stroke-width", "2");
        svg.setAttribute("stroke-linecap", "round");
        svg.setAttribute("stroke-linejoin", "round");
        svg.setAttribute("aria-hidden", "true");
        const paths = {
            eye: [
                ["path", { d: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" }],
                ["circle", { cx: "12", cy: "12", r: "3" }],
            ],
            edit: [
                ["path", { d: "M12 20h9" }],
                ["path", { d: "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" }],
            ],
        };
        (paths[name] || []).forEach(([tag, attrs]) => {
            const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
            node.setAttribute("fill", "none");
            Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
            svg.appendChild(node);
        });
        return svg;
    };

    const renderActions = (container, actions) => {
        container.innerHTML = "";
        actions.forEach((item) => {
            const btn = document.createElement("button");
            btn.className = item.className;
            btn.type = "button";
            if (item.icon) {
                btn.appendChild(createActionIcon(item.icon));
                const label = document.createElement("span");
                label.textContent = t(item.labelKey || item.key);
                btn.appendChild(label);
                btn.setAttribute("aria-label", t(item.key));
            } else {
                btn.textContent = t(item.key);
            }
            if (item.action) btn.dataset.action = item.action;
            container.appendChild(btn);
        });
    };

    const fillStatusOptions = (select, view) => {
        if (!select) return;
        const options = (view === "accept" ? select.dataset.acceptOptions : select.dataset.issueOptions) || "";
        const values = options.split(",").map((v) => v.trim()).filter(Boolean);
        const defaultOption = select.dataset.defaultOption || "";
        select.innerHTML = "";
        if (defaultOption) {
            const opt = document.createElement("option");
            opt.value = defaultOption;
            if (defaultOption === "全部") {
                opt.textContent = t("common.all");
                opt.dataset.i18n = "common.all";
            } else if (defaultOption === "请选择状态") {
                opt.textContent = t("common.field.status_select");
                opt.dataset.i18n = "common.field.status_select";
            } else {
                opt.textContent = defaultOption;
            }
            select.appendChild(opt);
        }
        values.forEach((value) => {
            const opt = document.createElement("option");
            opt.value = value;
            const labelKey = statusLabelMap[value];
            opt.textContent = t(labelKey || value);
            if (labelKey) opt.dataset.i18n = labelKey;
            select.appendChild(opt);
        });
    };

    const fillIssueStatusOptions = (select, values, defaultOption = "") => {
        if (!select) return;
        select.innerHTML = "";
        if (defaultOption) {
            const opt = document.createElement("option");
            opt.value = defaultOption;
            opt.textContent = defaultOption === "请选择状态" ? t("common.field.status_select") : defaultOption;
            if (defaultOption === "请选择状态") opt.dataset.i18n = "common.field.status_select";
            select.appendChild(opt);
        }
        values.forEach((value) => {
            const opt = document.createElement("option");
            opt.value = value;
            const labelKey = statusLabelMap[value];
            opt.textContent = t(labelKey || value);
            if (labelKey) opt.dataset.i18n = labelKey;
            select.appendChild(opt);
        });
    };

    const renderProjectCustomerCell = (item) => {
        const projectName = item.project_name || "-";
        const customerName = item.customer_name || "-";
        const title = `${item.project_name || ""} / ${item.customer_name || ""}`;
        return `
          <td>
            <div class="c-truncate" title="${escapeHtml(title)}">${escapeHtml(projectName)}</div>
            <div class="c-truncate c-table-cell-sub" title="${escapeHtml(customerName)}">${escapeHtml(customerName)}</div>
          </td>
        `;
    };

    const showMissingField = (label, fieldEl) => {
        alert(format("common.error.missing_field", { field: label }, `缺少字段：${label}`));
        if (fieldEl && typeof fieldEl.focus === "function") fieldEl.focus();
    };

    function init() {
        if (i18n) {
            i18n.init();
            i18n.apply();
        }

        const switches = Array.from(document.querySelectorAll(".c-switcher-group .c-toggle"));
        const swapNodes = Array.from(document.querySelectorAll("[data-issue][data-accept]"));
        const swapPlaceholders = Array.from(document.querySelectorAll("[data-issue-placeholder][data-accept-placeholder]"));
        const acceptOnlyFields = Array.from(document.querySelectorAll("[data-accept-only]"));
        const statusFilter = document.getElementById("statusFilter");
        const createBtn = document.getElementById("createBtn");
        const createDialogIssue = document.getElementById("createDialogIssue");
        const createDialogAccept = document.getElementById("createDialogAccept");
        const detailDialog = document.getElementById("detailDialog");
        const sendDialog = document.getElementById("sendDialog");
        const sendTemplateDialog = document.getElementById("send-template-dialog");
        const detailTitle = document.getElementById("detailTitle");
        const detailSubtitle = document.getElementById("detailSubtitle");
        const detailSave = document.getElementById("detailSave");
        const tableBody = document.getElementById("order-body");
        const tableInfo = document.getElementById("table-info");
        const searchBtn = document.getElementById("searchBtn");
        const resetBtn = document.getElementById("resetBtn");
        const pagination = document.getElementById("order-pagination");
        const paginationPages = document.getElementById("order-pagination-pages");
        const pageSummary = document.getElementById("page-summary");

        const filters = {
            orderNo: document.getElementById("filter-order-no"),
            project: document.getElementById("filter-project"),
            customer: document.getElementById("filter-customer"),
            customerId: document.getElementById("filter-customer-id"),
            customerList: document.getElementById("filter-customer-list"),
            technician: document.getElementById("filter-technician"),
            status: statusFilter,
            onlySelf: document.getElementById("filter-only-self"),
            start: document.getElementById("filter-start"),
            end: document.getElementById("filter-end"),
        };

        const detailFields = {
            orderNo: document.querySelector('[data-field="orderNo"]'),
            project: document.querySelector('[data-field="project"]'),
            customerId: document.querySelector('[data-field="customerId"]'),
            purchaseId: document.querySelector('[data-field="purchaseId"]'),
            client: document.querySelector('[data-field="client"]'),
            engineer: document.querySelector('[data-field="engineer"]'),
            technicianId: document.querySelector('[data-field="technicianId"]'),
            status: document.querySelector('[data-field="status"]'),
            price: document.querySelector('[data-field="price"]'),
            start: document.querySelector('[data-field="start"]'),
            end: document.querySelector('[data-field="end"]'),
            createdAt: document.querySelector('[data-field="createdAt"]'),
            creator: document.querySelector('[data-field="creator"]'),
            owner: document.querySelector('[data-field="owner"]'),
            remark: document.querySelector('[data-field="remark"]'),
            updatedAt: document.querySelector('[data-field="updatedAt"]'),
            updater: document.querySelector('[data-field="updater"]'),
        };

        if (window.initDialogCloseBehavior) {
            window.initDialogCloseBehavior({
                dialogs: [createDialogIssue, createDialogAccept, detailDialog, sendDialog, sendTemplateDialog]
            });
        }
        if (tableInfo) tableInfo.textContent = format("order.table.info", { count: 0, page: 1 });
        if (pageSummary) pageSummary.textContent = format("common.summary.page", { count: 0, page: 1, total: 1 });

        let currentView = "issue";
        let currentPage = 1;
        const pageSize = 10;
        let totalPages = 1;
        let lastTotalCount = 0;
        let lastTotalPages = 1;
        let currentItems = [];
        let currentDetailId = null;
        let detailMode = "view";
        const viewStorageKey = "order_current_view";
        const filterCustomerMap = new Map();
        let ownerSelectOptionsCache = null;
        let ownerSelectOptionsRequest = null;

        const applyViewLabels = (view) => {
            switches.forEach((btn) => {
                const active = btn.dataset.view === view;
                btn.classList.toggle("is-active", active);
                btn.setAttribute("aria-selected", active ? "true" : "false");
            });
            swapNodes.forEach((node) => {
                node.textContent = view === "accept" ? node.dataset.accept : node.dataset.issue;
            });
            swapPlaceholders.forEach((node) => {
                node.setAttribute("placeholder", view === "accept" ? node.dataset.acceptPlaceholder : node.dataset.issuePlaceholder);
            });
            acceptOnlyFields.forEach((node) => {
                node.style.display = view === "accept" ? "" : "none";
            });
            if (createBtn) {
                const label = view === "accept" ? createBtn.dataset.accept : createBtn.dataset.issue;
                createBtn.textContent = `＋ ${label}`;
            }
            fillStatusOptions(statusFilter, view);
        };

        const setDialogMode = (mode) => {
            const isView = mode === "view";
            detailMode = mode;
            if (detailTitle) detailTitle.textContent = isView ? t("order.dialog.detail.view") : t("order.dialog.detail.edit");
            if (detailSubtitle) {
                detailSubtitle.textContent = isView
                    ? t("order.dialog.detail.subtitle_view")
                    : t("order.dialog.detail.subtitle_edit");
            }
            if (detailSave) detailSave.style.display = isView ? "none" : "";
            Object.values(detailFields).forEach((field) => {
                if (!field) return;
                if (field.tagName === "SELECT") {
                    field.disabled = isView;
                } else if (field.type === "date") {
                    field.disabled = isView;
                } else {
                    field.readOnly = isView;
                }
            });
            if (detailFields.createdAt) detailFields.createdAt.readOnly = true;
            if (detailFields.updatedAt) detailFields.updatedAt.readOnly = true;
            if (detailFields.creator) detailFields.creator.readOnly = true;
            if (detailFields.updater) detailFields.updater.readOnly = true;
        };

        const getModule = (view = currentView) => view === "accept" ? sales : purchase;

        const orderFieldLabelMap = {
            order_no: () => t("order.field.order_no"),
            project_name: () => t("order.field.project"),
            customer_id: () => t(currentView === "accept" ? "order.field.customer_accept" : "order.field.customer"),
            customer_name: () => t(currentView === "accept" ? "order.field.customer_accept" : "order.field.customer"),
            technician_id: () => t("common.field.technician_id"),
            technician_name: () => t("common.field.technician"),
            status: () => t("common.field.status"),
            price: () => t("order.field.price"),
            period_start: () => t("order.field.period"),
            period_end: () => t("order.field.period"),
            person_in_charge: () => t("common.field.owner"),
            person_in_charge_id: () => t("common.field.owner"),
            purchase_id: () => t("order.field.purchase_id"),
        };

        const getOrderFieldLabel = (field) => {
            const resolver = orderFieldLabelMap[field];
            return resolver ? resolver() : field;
        };

        const formatOrderApiError = (message, fallback) => {
            const raw = String(message || "").trim();
            if (!raw) return fallback;
            const missingMatch = raw.match(/^(?:Missing field|缺少字段)[:：]\s*(.+)$/);
            if (missingMatch) {
                return format("common.error.missing_field", { field: getOrderFieldLabel(missingMatch[1].trim()) });
            }
            const invalidNumberMatch = raw.match(/^Invalid number:\s*(.+)$/);
            if (invalidNumberMatch) return `${getOrderFieldLabel(invalidNumberMatch[1].trim())}格式不正确`;
            const invalidDateMatch = raw.match(/^Invalid date:\s*(.+)$/);
            if (invalidDateMatch) {
                const field = invalidDateMatch[1].trim();
                if (field === "period_start") return "契约开始日期格式不正确";
                if (field === "period_end") return "契约结束日期格式不正确";
                return `${getOrderFieldLabel(field)}格式不正确`;
            }
            if (raw === "Unauthorized") return "登录已过期，请重新登录";
            return raw;
        };

        const getRequestErrorMessage = (error, fallback) => {
            const raw = error && error.payload && error.payload.message ? error.payload.message : (error && error.message);
            return formatOrderApiError(raw, fallback);
        };

        const ctx = {
            t,
            format,
            statusClass,
            statusLabelMap,
            detailFields,
            createOption,
            clearFields,
            setFieldValue,
            setFieldValues,
            readOwnerSelect,
            fillIssueStatusOptions,
            parseMoneyValue,
            formatBlankValue,
            formatYenValue,
            escapeHtml,
            todayText,
            buildIssueOrderNo,
            buildPeriodText,
            readBlobAsBase64,
            renderProjectCustomerCell,
            showMissingField,
            getRequestErrorMessage,
            loadOwnerSelectOptions: null,
            fetchOrders: null,
            submitCreate: null,
        };

        const purchase = window.OrderPurchase.init(ctx);
        const sales = window.OrderSales.init(ctx);

        const fetchOwnerSelectOptions = () => {
            if (ownerSelectOptionsCache) return Promise.resolve(ownerSelectOptionsCache);
            if (ownerSelectOptionsRequest) return ownerSelectOptionsRequest;
            const params = window.createParams([["role_id", "2"]]);
            ownerSelectOptionsRequest = window.requestJson(window.buildUrl("/api/user-logins/by-role", params), { method: "GET" })
                .then((payload) => {
                    const result = payload.data || {};
                    const items = Array.isArray(result.items) ? result.items : [];
                    ownerSelectOptionsCache = items;
                    return items;
                })
                .catch((error) => {
                    ownerSelectOptionsRequest = null;
                    throw error;
                });
            return ownerSelectOptionsRequest;
        };

        const renderOwnerSelectOptions = (selectEl, items, currentValue) => {
            selectEl.innerHTML = "";
            items.forEach((item) => {
                if (!item || !item.employee_name) return;
                selectEl.appendChild(createOption(item.employee_id || "", item.employee_name));
            });
            if (currentValue && !items.some((item) => String(item.employee_id || "") === String(currentValue))) {
                selectEl.appendChild(createOption(currentValue));
            }
            if (currentValue) selectEl.value = String(currentValue);
        };

        const loadOwnerSelectOptions = (selectEl, currentValue) => {
            if (!selectEl) return Promise.resolve([]);
            return fetchOwnerSelectOptions()
                .then((items) => {
                    renderOwnerSelectOptions(selectEl, items, currentValue);
                    if (selectEl === purchase.form.owner) purchase.updatePreview();
                    return items;
                })
                .catch(() => {
                    selectEl.innerHTML = "";
                    if (currentValue) {
                        selectEl.appendChild(createOption(currentValue));
                        selectEl.value = String(currentValue);
                    }
                    if (selectEl === purchase.form.owner) purchase.updatePreview();
                    return [];
                });
        };
        ctx.loadOwnerSelectOptions = loadOwnerSelectOptions;

        const renderRows = (items, totalCount, page, totalPageCount) => {
            const count = Number.isFinite(totalCount) ? totalCount : items.length;
            totalPages = Number.isFinite(totalPageCount) ? totalPageCount : 1;
            lastTotalCount = count;
            lastTotalPages = totalPages;
            currentPage = Number.isFinite(page) ? page : 1;
            window.renderPagination(pagination, paginationPages, currentPage, totalPages);
            if (pageSummary) {
                pageSummary.textContent = format("common.summary.page", { count, page: currentPage, total: totalPages });
            }
            if (!items.length) {
                const colSpan = 12;
                tableBody.innerHTML = `<tr><td colspan="${colSpan}" class="empty c-empty">${t("order.table.no_data")}</td></tr>`;
                tableInfo.textContent = format("order.table.info", { count, page: currentPage });
                return;
            }
            tableBody.innerHTML = items.map((item) => {
                const status = item.status || "已创建";
                const statusLabel = t(statusLabelMap[status] || status);
                const periodStart = item.period_start || "-";
                const periodEnd = item.period_end || "-";
                return getModule().renderRow(item, status, statusLabel, periodStart, periodEnd);
            }).join("");
            tableInfo.textContent = format("order.table.info", { count, page: currentPage });
            Array.from(document.querySelectorAll("[data-row-actions]")).forEach((container) => {
                renderActions(container, getModule().actions);
            });
        };

        const fetchOrders = () => {
            const params = window.createParams([
                ["order_no", filters.orderNo.value.trim()],
                ["project_name", filters.project.value.trim()],
                ["customer_id", filters.customerId.value.trim()],
                ["technician_name", filters.technician.value.trim()],
                ["status", filters.status.value && filters.status.value !== "全部" ? filters.status.value : ""],
                ["only_self", filters.onlySelf && filters.onlySelf.checked ? "1" : ""],
                ["created_start", filters.start.value],
                ["created_end", filters.end.value],
                ["page", String(currentPage)],
                ["page_size", String(pageSize)],
            ]);
            const baseUrl = currentView === "accept" ? "/api/sales-orders" : "/api/purchase-orders";
            window.requestJson(window.buildUrl(baseUrl, params), { method: "GET" })
                .then((payload) => {
                    if (!payload.success) {
                        currentItems = [];
                        renderRows([], 0, 1, 1);
                        return;
                    }
                    const result = payload.data || {};
                    const meta = payload.meta || {};
                    currentItems = Array.isArray(result.items) ? result.items : [];
                    const totalCount = Number.isFinite(meta.total) ? meta.total : (Number.isFinite(result.total) ? result.total : currentItems.length);
                    const page = Number.isFinite(meta.page) ? meta.page : (Number.isFinite(result.page) ? result.page : 1);
                    const totalPageCount = Number.isFinite(meta.total_pages) ? meta.total_pages : (Number.isFinite(result.total_pages) ? result.total_pages : 1);
                    renderRows(currentItems, totalCount, page, totalPageCount);
                })
                .catch(() => {
                    currentItems = [];
                    renderRows([], 0, 1, 1);
                });
        };
        ctx.fetchOrders = fetchOrders;

        const setView = (view) => {
            currentView = view;
            currentPage = 1;
            try {
                sessionStorage.setItem(viewStorageKey, view);
            } catch (error) {
                console.warn(error);
            }
            applyViewLabels(view);
            fetchOrders();
        };

        const openDetailDialog = (mode, item) => {
            if (!detailDialog || !item) return;
            fillStatusOptions(detailFields.status, currentView);
            setFieldValues([
                [detailFields.orderNo, item.order_no],
                [detailFields.project, item.project_name],
                [detailFields.customerId, item.customer_id],
                [detailFields.purchaseId, item.purchase_id],
                [detailFields.client, item.customer_name],
                [detailFields.engineer, item.technician_name],
                [detailFields.technicianId, item.technician_id],
                [detailFields.price, item.price],
                [detailFields.start, item.period_start],
                [detailFields.end, item.period_end],
                [detailFields.createdAt, formatDateValue(item.created_at)],
                [detailFields.creator, item.created_by],
                [detailFields.remark, item.remark],
                [detailFields.updatedAt, formatDateValue(item.updated_at)],
                [detailFields.updater, item.updated_by],
            ]);
            if (detailFields.status && item.status) detailFields.status.value = item.status;
            if (detailFields.owner) loadOwnerSelectOptions(detailFields.owner, item.person_in_charge_id || item.person_in_charge || "");
            currentDetailId = item.id;
            setDialogMode(mode);
            detailDialog.showModal();
        };

        const submitCreate = async (view) => {
            const mod = getModule(view);
            if (!mod.validateForm()) return;
            const payload = mod.buildPayload(false);
            const submitButton = mod.submitButton;
            const originalText = submitButton ? submitButton.textContent : "";
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = view === "issue" ? "PDF生成中..." : originalText;
            }
            try {
                const requestOptions = mod.buildFormData
                    ? {
                        method: "POST",
                        headers: {},
                        body: view === "issue" ? mod.buildFormData(payload, await mod.exportPdfBlob()) : mod.buildFormData(payload),
                    }
                    : { method: "POST", body: JSON.stringify(payload) };
                if (submitButton && view === "issue") submitButton.textContent = "保存中...";
                const responsePayload = await window.requestJson(mod.baseUrl, requestOptions);
                if (!responsePayload.success) {
                    alert(formatOrderApiError(responsePayload.message, t("order.action.create_failed")));
                    return;
                }
                mod.closeCreateDialog();
                fetchOrders();
            } catch (error) {
                alert(getRequestErrorMessage(error, t("order.action.create_failed_retry")));
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = originalText || t("common.create");
                }
            }
        };
        ctx.submitCreate = submitCreate;

        const submitUpdate = () => {
            if (!currentDetailId) return;
            const mod = getModule();
            const payload = mod.buildPayload(true);
            window.requestJson(`${mod.baseUrl}/${currentDetailId}`, {
                method: "PUT",
                body: JSON.stringify(payload),
            })
                .then((responsePayload) => {
                    if (!responsePayload.success) {
                        alert(formatOrderApiError(responsePayload.message, t("common.save_failed")));
                        return;
                    }
                    if (detailDialog) detailDialog.close();
                    fetchOrders();
                })
                .catch((error) => {
                    alert(getRequestErrorMessage(error, t("common.save_failed_retry")));
                });
        };

        const renderCustomerOptions = (listEl, map, items) => {
            map.clear();
            listEl.innerHTML = "";
            items.forEach((item) => {
                if (!item || !item.company_name) return;
                map.set(item.company_name, item.id);
                listEl.appendChild(createOption(item.company_name));
            });
        };

        const fetchCustomerOptions = (inputEl, listEl, map, options = {}) => {
            const keyword = inputEl.value.trim();
            if (!keyword && options.useDefault !== true) {
                listEl.innerHTML = "";
                map.clear();
                return;
            }
            const params = window.createParams([["company_name", keyword], ["page", "1"], ["page_size", "5"]]);
            window.requestJson(window.buildUrl("/api/customers", params), { method: "GET" })
                .then((payload) => {
                    const result = payload.data || {};
                    renderCustomerOptions(listEl, map, Array.isArray(result.items) ? result.items : []);
                })
                .catch(() => {
                    listEl.innerHTML = "";
                    map.clear();
                });
        };

        const bindCustomerLookup = (inputEl, idEl, listEl, map, options = {}) => {
            if (!inputEl || !idEl || !listEl) return;
            const debouncedFetch = debounce(() => fetchCustomerOptions(inputEl, listEl, map));
            inputEl.addEventListener("input", () => {
                idEl.value = "";
                if (!inputEl.value.trim()) {
                    fetchCustomerOptions(inputEl, listEl, map);
                    return;
                }
                debouncedFetch();
            });
            if (options.enableDefault) {
                inputEl.addEventListener("focus", () => fetchCustomerOptions(inputEl, listEl, map, { useDefault: true }));
            }
            inputEl.addEventListener("change", () => {
                const id = map.get(inputEl.value.trim());
                idEl.value = id ? String(id) : "";
            });
        };

        const renderTechnicianOptions = (listEl, map, items) => {
            map.clear();
            listEl.innerHTML = "";
            items.forEach((item) => {
                if (!item || !item.name) return;
                map.set(item.name, item.employee_id);
                listEl.appendChild(createOption(item.name));
            });
        };

        const fetchTechnicianOptions = (inputEl, listEl, map, options = {}) => {
            const keyword = inputEl.value.trim();
            if (!keyword && options.useDefault !== true) {
                listEl.innerHTML = "";
                map.clear();
                return;
            }
            const params = window.createParams([["keyword", keyword], ["page_size", keyword ? "10" : "5"]]);
            window.requestJson(window.buildUrl("/api/technicians", params), { method: "GET" })
                .then((payload) => {
                    const result = payload.data || {};
                    renderTechnicianOptions(listEl, map, Array.isArray(result.items) ? result.items : []);
                })
                .catch(() => {
                    listEl.innerHTML = "";
                    map.clear();
                });
        };

        const bindTechnicianLookup = (inputEl, idEl, listEl, map, options = {}) => {
            if (!inputEl || !idEl || !listEl) return;
            const debouncedFetch = debounce(() => fetchTechnicianOptions(inputEl, listEl, map));
            inputEl.addEventListener("input", () => {
                idEl.value = "";
                if (!inputEl.value.trim()) {
                    fetchTechnicianOptions(inputEl, listEl, map);
                    return;
                }
                debouncedFetch();
            });
            if (options.enableDefault) {
                inputEl.addEventListener("focus", () => fetchTechnicianOptions(inputEl, listEl, map, { useDefault: true }));
            }
            inputEl.addEventListener("change", () => {
                const id = map.get(inputEl.value.trim());
                idEl.value = id ? String(id) : "";
            });
        };

        switches.forEach((btn) => btn.addEventListener("click", () => setView(btn.dataset.view)));
        if (createBtn) {
            createBtn.addEventListener("click", async () => {
                if (currentView === "accept") {
                    await sales.openCreateDialog();
                } else {
                    await purchase.openCreateDialog();
                }
            });
        }
        if (purchase.submitButton) purchase.submitButton.addEventListener("click", purchase.submitDialog);
        if (sales.submitButton) sales.submitButton.addEventListener("click", sales.submitDialog);
        if (searchBtn) {
            searchBtn.addEventListener("click", () => {
                currentPage = 1;
                fetchOrders();
            });
        }
        if (resetBtn) {
            resetBtn.addEventListener("click", () => {
                Object.values(filters).forEach((field) => {
                    if (!field) return;
                    if (field.type === "checkbox") field.checked = false;
                    else if (field.tagName === "SELECT") field.value = "全部";
                    else field.value = "";
                });
                filterCustomerMap.clear();
                currentPage = 1;
                fetchOrders();
            });
        }
        window.bindPagination(pagination, (value) => {
            if (value === "prev") currentPage = Math.max(1, currentPage - 1);
            else if (value === "next") currentPage = Math.min(totalPages, currentPage + 1);
            else {
                const targetPage = Number(value);
                if (!Number.isNaN(targetPage)) currentPage = targetPage;
            }
            fetchOrders();
        });
        if (tableBody) {
            tableBody.addEventListener("click", (event) => {
                const btn = event.target.closest("button[data-action]");
                if (!btn) return;
                const row = btn.closest("tr");
                if (!row) return;
                const item = currentItems.find((entry) => String(entry.id) === String(row.dataset.id));
                if (!item) return;
                if (currentView === "issue" && btn.dataset.action === "edit") {
                    purchase.openEditDialog(item);
                    return;
                }
                if (currentView === "issue" && btn.dataset.action === "send") {
                    purchase.openSendDialog(item);
                    return;
                }
                if (currentView === "accept" && btn.dataset.action === "edit") {
                    sales.openEditDialog(item);
                    return;
                }
                if (currentView === "accept" && btn.dataset.action === "view_request") {
                    const customerName = item.customer_name ? `?customer_name=${encodeURIComponent(item.customer_name)}` : "";
                    window.navigateAppRoute(`pay_request.html${customerName}`);
                    return;
                }
                if (currentView === "accept" && btn.dataset.action === "create_request") {
                    const price = parseMoneyValue(item.price);
                    const detailName = item.technician_name || item.project_name || "";
                    const prefill = {
                        source: "sales_order",
                        customer_id: item.customer_id || "",
                        customer_name: item.customer_name || "",
                        order_no: item.order_no || "",
                        subject: item.project_name || "",
                        details: [{
                            item: detailName,
                            qty: 1,
                            price,
                            tax: price ? Math.round(price * 0.1) : 0,
                            unit: "人月",
                        }],
                    };
                    try {
                        sessionStorage.setItem("pay_request_prefill", JSON.stringify(prefill));
                    } catch (error) {
                        console.warn(error);
                    }
                    window.navigateAppRoute("pay_request.html?prefill=1");
                    return;
                }
                openDetailDialog(btn.dataset.action, item);
            });
        }
        if (detailSave) {
            detailSave.addEventListener("click", () => {
                if (detailMode === "edit") submitUpdate();
            });
        }

        bindCustomerLookup(purchase.form.customerName, purchase.form.customerId, purchase.form.customerList, purchase.customerMap, { enableDefault: true });
        bindCustomerLookup(sales.form.customerName, sales.form.customerId, sales.form.customerList, sales.customerMap, { enableDefault: true });
        bindCustomerLookup(filters.customer, filters.customerId, filters.customerList, filterCustomerMap, { enableDefault: true });
        const refreshI18n = () => {
            if (i18n) i18n.apply();
            applyViewLabels(currentView);
            if (detailFields.status) fillStatusOptions(detailFields.status, currentView);
            purchase.updatePreview();
            renderRows(currentItems, lastTotalCount, currentPage, lastTotalPages);
        };

        window.addEventListener("storage", (event) => {
            if (!event || event.key !== "app_lang") return;
            refreshI18n();
        });
        window.addEventListener("i18n:change", refreshI18n);
        window.addEventListener("beforeunload", () => {
            purchase.cleanup();
            sales.cleanup();
        });

        let initialView = "issue";
        try {
            const storedView = sessionStorage.getItem(viewStorageKey);
            if (storedView === "issue" || storedView === "accept") initialView = storedView;
        } catch (error) {
            console.warn(error);
        }
        setView(initialView);
    }

    window.OrderCommon = { init };
    window.addEventListener("DOMContentLoaded", init);
})();
