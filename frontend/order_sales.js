(function () {
    window.OrderSales = {
        init(ctx) {
            const createDialog = document.getElementById("createDialogAccept");
            const dialogTitle = document.getElementById("createTitleAccept");
            const submitButton = document.getElementById("accept-create-submit");
            const pdfUploadEmpty = document.getElementById("acceptPdfUploadEmpty");
            const pdfPreviewWrap = document.getElementById("acceptPdfPreviewWrap");
            const pdfPreviewFrame = document.getElementById("acceptPdfPreviewFrame");
            const pdfFileName = document.getElementById("acceptPdfFileName");
            const pdfReplace = document.getElementById("acceptPdfReplace");
            const form = {
                orderNo: document.getElementById("accept-order-no"),
                projectName: document.getElementById("accept-project-name"),
                customerName: document.getElementById("accept-customer-name"),
                customerId: document.getElementById("accept-customer-id"),
                customerList: document.getElementById("accept-customer-list"),
                technicianList: document.getElementById("accept-technician-list"),
                status: document.getElementById("accept-status"),
                start: document.getElementById("accept-start"),
                end: document.getElementById("accept-end"),
                owner: document.getElementById("accept-owner"),
                pdfFile: document.getElementById("accept-pdf-file"),
                remark: document.getElementById("accept-remark"),
                lineItems: document.getElementById("accept-line-items"),
                lineAdd: document.getElementById("accept-line-add"),
            };
            const customerMap = new Map();
            const technicianMap = new Map();
            let pdfObjectUrl = "";
            let dialogMode = "create";
            let currentEditId = null;

            const readItemField = (row, field) => row.querySelector(`[data-accept-item-field="${field}"]`)?.value?.trim() || "";
            const getItemInput = (row, field) => row.querySelector(`[data-accept-item-field="${field}"]`);
            const setItemField = (row, field, value) => ctx.setFieldValue(getItemInput(row, field), value);
            const updateBpTag = (row) => {
                if (!row) return;
                const technicianName = readItemField(row, "technician");
                const technicianId = readItemField(row, "technicianId");
                const isBp = Boolean(technicianName && !technicianId);
                const tag = row.querySelector("[data-accept-bp-tag]");
                const purchaseField = row.querySelector("[data-accept-purchase-field]");
                if (tag) tag.hidden = !isBp;
                if (purchaseField) {
                    purchaseField.hidden = !isBp;
                    if (!isBp) setItemField(row, "purchaseId", "");
                }
            };
            const isTechnicianOptionSelection = (event) => {
                return event.inputType === "insertReplacementText" || (!event.inputType && event.data == null);
            };

            const collectItems = () => {
                const rows = Array.from(form.lineItems ? form.lineItems.querySelectorAll(".order-accept-item-row") : []);
                return rows.map((row) => ({
                    row,
                    technicianName: readItemField(row, "technician"),
                    technicianId: Number(readItemField(row, "technicianId")) || 0,
                    priceInput: readItemField(row, "price"),
                    price: readItemField(row, "price"),
                    purchaseId: readItemField(row, "purchaseId"),
                }));
            };

            const createItemRow = () => {
                const row = document.createElement("div");
                row.className = "order-issue-item-row order-accept-item-row";
                row.innerHTML = `
                    <label class="c-inline-field">
                        <span>${ctx.t("common.field.technician")}</span>
                        <div class="order-accept-technician-wrap">
                            <input type="text" placeholder="${ctx.t("common.field.name")}" list="accept-technician-list" autocomplete="off" data-accept-item-field="technician"/>
                            <span class="order-accept-bp-tag" data-accept-bp-tag hidden>BP</span>
                        </div>
                        <input type="hidden" data-accept-item-field="technicianId"/>
                    </label>
                    <label class="c-inline-field">
                        <span>${ctx.t("order.field.price")}</span>
                        <input type="text" placeholder="¥ 0" data-accept-item-field="price"/>
                    </label>
                    <label class="c-inline-field" data-accept-purchase-field hidden>
                        <span>${ctx.t("order.field.purchase_id")}</span>
                        <input type="number" placeholder="${ctx.t("order.placeholder.purchase_id")}" data-accept-item-field="purchaseId"/>
                    </label>
                    <button class="c-btn c-btn-ghost c-btn-sm order-issue-item-remove" type="button" data-action="remove-accept-line" aria-label="删除">×</button>
                `;
                return row;
            };

            const setLineItems = (lineItems) => {
                if (!form.lineItems) return;
                form.lineItems.innerHTML = "";
                const items = Array.isArray(lineItems) && lineItems.length ? lineItems : [{}];
                items.forEach((item) => {
                    const row = createItemRow();
                    setItemField(row, "technician", item.technician_name ?? "");
                    setItemField(row, "technicianId", item.technician_id ?? "");
                    setItemField(row, "price", item.price ?? "");
                    setItemField(row, "purchaseId", item.purchase_id ?? "");
                    updateBpTag(row);
                    form.lineItems.appendChild(row);
                });
            };

            const renderTechnicianOptions = (items) => {
                technicianMap.clear();
                if (!form.technicianList) return;
                form.technicianList.innerHTML = "";
                items.forEach((item) => {
                    if (!item || !item.name) return;
                    technicianMap.set(item.name, item.employee_id);
                    form.technicianList.appendChild(ctx.createOption(item.name));
                });
                if (form.lineItems) {
                    form.lineItems.querySelectorAll(".order-accept-item-row").forEach(updateBpTag);
                }
            };

            const fetchTechnicianOptions = (keyword, useDefault = false) => {
                const value = String(keyword || "").trim();
                if (!value && useDefault !== true) {
                    renderTechnicianOptions([]);
                    return;
                }
                const params = window.createParams([["keyword", value], ["page_size", value ? "10" : "5"]]);
                window.requestJson(window.buildUrl("/api/technicians", params), { method: "GET" })
                    .then((payload) => {
                        const result = payload.data || {};
                        renderTechnicianOptions(Array.isArray(result.items) ? result.items : []);
                    })
                    .catch(() => renderTechnicianOptions([]));
            };

            const debounce = (fn, delay = 250) => {
                let timer = null;
                return (...args) => {
                    clearTimeout(timer);
                    timer = setTimeout(() => fn(...args), delay);
                };
            };
            const debouncedFetchTechnicians = debounce(fetchTechnicianOptions);

            const resetForm = () => {
                dialogMode = "create";
                currentEditId = null;
                if (dialogTitle) dialogTitle.textContent = ctx.t("order.action.create_accept");
                if (submitButton) submitButton.textContent = ctx.t("common.create");
                ctx.clearFields([
                    form.orderNo,
                    form.projectName,
                    form.customerName,
                    form.customerId,
                    form.start,
                    form.end,
                    form.remark,
                ]);
                if (form.status) form.status.value = "已受注";
                if (form.pdfFile) form.pdfFile.value = "";
                resetPdfPreview();
                setLineItems([{}]);
            };

            const resetPdfPreview = () => {
                if (pdfObjectUrl) {
                    URL.revokeObjectURL(pdfObjectUrl);
                    pdfObjectUrl = "";
                }
                if (pdfPreviewFrame) pdfPreviewFrame.src = "about:blank";
                if (pdfFileName) pdfFileName.textContent = "受注书PDF";
                if (pdfUploadEmpty) pdfUploadEmpty.hidden = false;
                if (pdfPreviewWrap) pdfPreviewWrap.hidden = true;
            };

            const updatePdfPreview = () => {
                const file = form.pdfFile && form.pdfFile.files ? form.pdfFile.files[0] : null;
                if (!file) {
                    resetPdfPreview();
                    return;
                }
                const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name || "");
                if (!isPdf) {
                    alert("请上传 PDF 文件");
                    form.pdfFile.value = "";
                    resetPdfPreview();
                    return;
                }
                if (pdfObjectUrl) URL.revokeObjectURL(pdfObjectUrl);
                pdfObjectUrl = URL.createObjectURL(file);
                if (pdfPreviewFrame) pdfPreviewFrame.src = pdfObjectUrl;
                if (pdfFileName) pdfFileName.textContent = file.name || "受注书PDF";
                if (pdfUploadEmpty) pdfUploadEmpty.hidden = true;
                if (pdfPreviewWrap) pdfPreviewWrap.hidden = false;
            };

            const showStoredPdfPreview = (item) => {
                resetPdfPreview();
                if (!item || !item.id || !item.pdf_file) return;
                if (pdfPreviewFrame) pdfPreviewFrame.src = `/api/sales-orders/${encodeURIComponent(item.id)}/pdf`;
                if (pdfFileName) pdfFileName.textContent = "受注书PDF";
                if (pdfUploadEmpty) pdfUploadEmpty.hidden = true;
                if (pdfPreviewWrap) pdfPreviewWrap.hidden = false;
            };

            const buildPayload = (fromDetail) => {
                const owner = ctx.readOwnerSelect(fromDetail ? ctx.detailFields.owner : form.owner);
                const lineItems = fromDetail ? [] : collectItems().map((item) => ({
                    technician_id: item.technicianId || null,
                    technician_name: item.technicianName,
                    price: item.price,
                    purchase_id: item.purchaseId ? Number(item.purchaseId) : null,
                }));
                const payload = {
                    order_no: fromDetail ? ctx.detailFields.orderNo.value.trim() : form.orderNo.value.trim(),
                    project_name: fromDetail ? ctx.detailFields.project.value.trim() : form.projectName.value.trim(),
                    customer_id: Number(fromDetail ? ctx.detailFields.customerId.value : form.customerId.value) || 0,
                    customer_name: fromDetail ? ctx.detailFields.client.value.trim() : form.customerName.value.trim(),
                    status: fromDetail ? ctx.detailFields.status.value : form.status.value,
                    period_start: fromDetail ? ctx.detailFields.start.value : form.start.value,
                    period_end: fromDetail ? ctx.detailFields.end.value : form.end.value,
                    person_in_charge_id: owner.id,
                    person_in_charge: owner.name,
                    remark: fromDetail ? ctx.detailFields.remark.value.trim() : form.remark.value.trim(),
                };
                if (fromDetail) {
                    const purchaseIdRaw = ctx.detailFields.purchaseId.value.trim();
                    payload.purchase_id = purchaseIdRaw ? Number(purchaseIdRaw) : null;
                    payload.technician_id = Number(ctx.detailFields.technicianId.value) || 0;
                    payload.technician_name = ctx.detailFields.engineer.value.trim();
                    payload.price = ctx.detailFields.price.value.trim();
                } else {
                    payload.line_items = lineItems;
                }
                return payload;
            };

            const buildFormData = (payload) => {
                const formData = new FormData();
                Object.entries(payload).forEach(([key, value]) => {
                    if (Array.isArray(value) || (value && typeof value === "object")) {
                        formData.append(key, JSON.stringify(value));
                    } else if (value !== null && value !== undefined) {
                        formData.append(key, String(value));
                    }
                });
                const file = form.pdfFile && form.pdfFile.files ? form.pdfFile.files[0] : null;
                if (file) formData.append("pdf_file", file, file.name || "sales_order.pdf");
                return formData;
            };

            const validateForm = () => {
                const orderNo = form.orderNo.value.trim();
                if (!orderNo) return ctx.showMissingField(ctx.t("order.field.order_no"), form.orderNo), false;
                const project = form.projectName.value.trim();
                if (!project) return ctx.showMissingField(ctx.t("order.field.project"), form.projectName), false;
                const customer = form.customerName.value.trim();
                if (!customer) return ctx.showMissingField(ctx.t("order.field.customer_accept"), form.customerName), false;
                const status = form.status.value;
                if (!status || status === "请选择状态") return ctx.showMissingField(ctx.t("common.field.status"), form.status), false;
                const items = collectItems();
                if (!items.length) return ctx.showMissingField("契约明细", form.lineAdd), false;
                for (const item of items) {
                    if (!item.technicianName) return ctx.showMissingField(ctx.t("common.field.technician"), getItemInput(item.row, "technician")), false;
                    if (!item.priceInput) return ctx.showMissingField(ctx.t("order.field.price"), getItemInput(item.row, "price")), false;
                    if (!item.technicianId && !item.purchaseId) return ctx.showMissingField(ctx.t("order.field.purchase_id"), getItemInput(item.row, "purchaseId")), false;
                }
                const start = form.start.value;
                const end = form.end.value;
                if (!start || !end) return ctx.showMissingField(ctx.t("order.field.period"), form.start), false;
                const owner = ctx.readOwnerSelect(form.owner);
                if (!owner.id) return ctx.showMissingField(ctx.t("common.field.owner"), form.owner), false;
                const pdfFile = form.pdfFile && form.pdfFile.files ? form.pdfFile.files[0] : null;
                if (dialogMode === "create" && !pdfFile) return ctx.showMissingField("受注书PDF", form.pdfFile), false;
                return true;
            };

            const buildEditPayload = () => {
                const owner = ctx.readOwnerSelect(form.owner);
                const lineItem = collectItems()[0] || {};
                return {
                    order_no: form.orderNo.value.trim(),
                    project_name: form.projectName.value.trim(),
                    customer_id: Number(form.customerId.value) || 0,
                    customer_name: form.customerName.value.trim(),
                    status: form.status.value,
                    period_start: form.start.value,
                    period_end: form.end.value,
                    person_in_charge_id: owner.id,
                    person_in_charge: owner.name,
                    remark: form.remark.value.trim(),
                    purchase_id: lineItem.purchaseId ? Number(lineItem.purchaseId) : null,
                    technician_id: lineItem.technicianId || null,
                    technician_name: lineItem.technicianName,
                    price: lineItem.price,
                };
            };

            const submitEdit = () => {
                if (!currentEditId || !validateForm()) return;
                const originalText = submitButton ? submitButton.textContent : "";
                if (submitButton) submitButton.disabled = true;
                window.requestJson(`/api/sales-orders/${currentEditId}`, {
                    method: "PUT",
                    body: JSON.stringify(buildEditPayload()),
                })
                    .then((responsePayload) => {
                        if (!responsePayload.success) {
                            alert(ctx.getRequestErrorMessage({ payload: responsePayload }, ctx.t("common.save_failed")));
                            return;
                        }
                        if (createDialog) createDialog.close();
                        ctx.fetchOrders();
                    })
                    .catch((error) => {
                        alert(ctx.getRequestErrorMessage(error, ctx.t("common.save_failed_retry")));
                    })
                    .finally(() => {
                        if (submitButton) {
                            submitButton.disabled = false;
                            submitButton.textContent = originalText || ctx.t("common.save");
                        }
                    });
            };

            const renderRow = (item, status, statusLabel, periodStart, periodEnd) => {
                return `
                    <tr data-id="${ctx.escapeHtml(item.id)}">
                      <td>${ctx.escapeHtml(item.order_no || "-")}</td>
                      ${ctx.renderProjectCustomerCell(item)}
                      <td>${ctx.escapeHtml(item.technician_name || "-")}</td>
                      <td>${ctx.escapeHtml(ctx.formatBlankValue(item.price))}</td>
                      <td>
                        <div>${ctx.escapeHtml(periodStart)}</div>
                        <div>${ctx.escapeHtml(periodEnd)}</div>
                      </td>
                      <td>${ctx.escapeHtml(item.created_at || "-")}</td>
                      <td>${ctx.escapeHtml(item.created_by || "-")}</td>
                      <td>${ctx.escapeHtml(item.person_in_charge || "-")}</td>
                      <td>${ctx.escapeHtml(item.updated_at || "-")}</td>
                      <td>${ctx.escapeHtml(item.updated_by || "-")}</td>
                      <td><span class="c-tag ${ctx.statusClass[status] || "c-tag-neutral"}">${ctx.escapeHtml(statusLabel)}</span></td>
                      <td><div class="row-actions c-row-actions c-row-actions-nowrap" data-row-actions></div></td>
                    </tr>
                `;
            };

            const openCreateDialog = async () => {
                if (!createDialog) return;
                resetForm();
                await ctx.loadOwnerSelectOptions(form.owner);
                updatePdfPreview();
                createDialog.showModal();
            };

            const openEditDialog = async (item) => {
                if (!createDialog || !item) return;
                resetForm();
                dialogMode = "edit";
                currentEditId = item.id;
                if (dialogTitle) dialogTitle.textContent = ctx.t("order.action.edit_accept");
                if (submitButton) submitButton.textContent = ctx.t("common.save");
                ctx.setFieldValues([
                    [form.orderNo, item.order_no],
                    [form.projectName, item.project_name],
                    [form.customerName, item.customer_name],
                    [form.customerId, item.customer_id],
                    [form.start, item.period_start],
                    [form.end, item.period_end],
                    [form.remark, item.remark],
                ]);
                if (form.status) form.status.value = item.status || "已受注";
                setLineItems([{
                    technician_name: item.technician_name,
                    technician_id: item.technician_id,
                    price: item.price,
                    purchase_id: item.purchase_id,
                }]);
                await ctx.loadOwnerSelectOptions(form.owner, item.person_in_charge_id || item.person_in_charge || "");
                showStoredPdfPreview(item);
                createDialog.showModal();
            };

            if (form.pdfFile) {
                form.pdfFile.addEventListener("change", updatePdfPreview);
            }
            if (pdfReplace && form.pdfFile) {
                pdfReplace.addEventListener("click", () => form.pdfFile.click());
            }
            if (form.lineAdd && form.lineItems) {
                form.lineAdd.addEventListener("click", () => {
                    form.lineItems.appendChild(createItemRow());
                });
            }
            if (form.lineItems) {
                form.lineItems.addEventListener("input", (event) => {
                    const input = event.target.closest('[data-accept-item-field="technician"]');
                    if (!input) return;
                    const row = input.closest(".order-accept-item-row");
                    if (row) setItemField(row, "technicianId", "");
                    const selectedId = technicianMap.get(input.value.trim());
                    if (row && selectedId && isTechnicianOptionSelection(event)) {
                        setItemField(row, "technicianId", selectedId);
                    }
                    updateBpTag(row);
                    if (!input.value.trim()) {
                        fetchTechnicianOptions("");
                        return;
                    }
                    debouncedFetchTechnicians(input.value);
                });
                form.lineItems.addEventListener("focusin", (event) => {
                    const input = event.target.closest('[data-accept-item-field="technician"]');
                    if (input) fetchTechnicianOptions(input.value, true);
                });
                form.lineItems.addEventListener("change", (event) => {
                    const input = event.target.closest('[data-accept-item-field="technician"]');
                    if (!input) return;
                    const row = input.closest(".order-accept-item-row");
                    updateBpTag(row);
                });
                form.lineItems.addEventListener("click", (event) => {
                    const btn = event.target.closest('[data-action="remove-accept-line"]');
                    if (!btn) return;
                    const row = btn.closest(".order-accept-item-row");
                    if (!row || row === form.lineItems.querySelector(".order-accept-item-row")) return;
                    row.remove();
                });
            }

            return {
                baseUrl: "/api/sales-orders",
                actions: [
                    { key: "common.edit", action: "edit", className: "c-btn c-btn-secondary c-btn-sm" },
                    { key: "order.action.view_request", labelKey: "order.action.request", action: "view_request", icon: "eye", className: "c-btn c-btn-lite c-btn-sm" },
                    { key: "order.action.create_request", labelKey: "order.action.request", icon: "edit", className: "c-btn c-btn-success-lite c-btn-sm" },
                ],
                form,
                customerMap,
                technicianMap,
                submitButton,
                openCreateDialog,
                openEditDialog,
                closeCreateDialog() {
                    if (createDialog) createDialog.close();
                },
                submitDialog() {
                    if (dialogMode === "edit") {
                        submitEdit();
                    } else {
                        ctx.submitCreate("accept");
                    }
                },
                validateForm,
                buildPayload,
                buildFormData,
                renderRow,
                cleanup() {
                    resetPdfPreview();
                },
            };
        }
    };
})();
