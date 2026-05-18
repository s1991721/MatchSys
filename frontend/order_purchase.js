(function () {
    window.OrderPurchase = {
        init(ctx) {
            const createDialog = document.getElementById("createDialogIssue");
            const createTitle = document.getElementById("createTitleIssue");
            const submitButton = document.getElementById("issue-create-submit");
            const pdfPreviewPage = document.getElementById("issuePdfPreviewPage");
            const sendDialog = document.getElementById("sendDialog");
            const sendSubmit = document.getElementById("sendSubmit");
            const sendTemplateEdit = document.getElementById("send-template-edit");
            const sendTemplateDialog = document.getElementById("send-template-dialog");
            const sendTemplateContent = document.getElementById("send-template-content");
            const sendTemplateSave = document.getElementById("send-template-save");
            const sendPdfFrame = document.getElementById("sendPdfFrame");
            const sendNoPdfMessage = document.getElementById("sendNoPdfMessage");
            const form = {
                orderNo: document.getElementById("issue-order-no"),
                projectName: document.getElementById("issue-project-name"),
                customerName: document.getElementById("issue-customer-name"),
                customerId: document.getElementById("issue-customer-id"),
                customerList: document.getElementById("issue-customer-list"),
                status: document.getElementById("issue-status"),
                start: document.getElementById("issue-start"),
                end: document.getElementById("issue-end"),
                owner: document.getElementById("issue-owner"),
                workContent: document.getElementById("issue-work-content"),
                workPlace: document.getElementById("issue-work-place"),
                contractType: document.getElementById("issue-contract-type"),
                paymentTerms: document.getElementById("issue-payment-terms"),
                remark: document.getElementById("issue-remark"),
                lineItems: document.getElementById("issue-line-items"),
                lineAdd: document.getElementById("issue-line-add"),
            };
            const sendFields = {
                subject: document.getElementById("send-subject"),
                type: document.getElementById("send-type"),
                to: document.getElementById("send-to"),
                toCombobox: document.getElementById("send-to-combobox"),
                toToggle: document.getElementById("send-to-toggle"),
                toOptions: document.getElementById("send-to-options"),
                body: document.getElementById("send-body"),
                cc: document.getElementById("send-cc"),
                files: document.getElementById("send-files"),
                filesTrigger: document.getElementById("send-files-trigger"),
                filesStatus: document.getElementById("send-files-status"),
                attachmentList: document.getElementById("send-attachment-list"),
            };
            const preview = {
                orderNo: document.querySelector('[data-preview="issueOrderNo"]'),
                orderDate: document.querySelector('[data-preview="issueOrderDate"]'),
                customer: document.querySelector('[data-preview="issueCustomer"]'),
                companyName: document.querySelector('[data-preview="issueCompanyName"]'),
                companyPostalCode: document.querySelector('[data-preview="issueCompanyPostalCode"]'),
                companyAddress: document.querySelector('[data-preview="issueCompanyAddress"]'),
                companyTel: document.querySelector('[data-preview="issueCompanyTel"]'),
                companyFax: document.querySelector('[data-preview="issueCompanyFax"]'),
                companyMail: document.querySelector('[data-preview="issueCompanyMail"]'),
                companySeal: document.querySelector('[data-preview="issueCompanySeal"]'),
                ownerSeal: document.querySelector('[data-preview="issueOwnerSeal"]'),
                project: document.querySelector('[data-preview="issueProject"]'),
                workContent: document.querySelector('[data-preview="issueWorkContent"]'),
                period: document.querySelector('[data-preview="issuePeriod"]'),
                workPlace: document.querySelector('[data-preview="issueWorkPlace"]'),
                contractType: document.querySelector('[data-preview="issueContractType"]'),
                paymentTerms: document.querySelector('[data-preview="issuePaymentTerms"]'),
                owner: document.querySelector('[data-preview="issueOwner"]'),
                total: document.querySelector('[data-preview="issueTotal"]'),
                subtotal: document.querySelector('[data-preview="issueSubtotal"]'),
                tax: document.querySelector('[data-preview="issueTax"]'),
                summaryTotal: document.querySelector('[data-preview="issueSummaryTotal"]'),
                remark: document.querySelector('[data-preview="issueRemark"]'),
                detailBody: document.getElementById("issuePreviewDetailBody"),
            };

            let dialogMode = "create";
            let currentEditId = null;
            let currentEditStatus = "";
            let currentSendItem = null;
            let sendExtraFiles = [];
            let sendRecipientOptions = [];
            const sendTemplateName = "order";
            const sendTemplateCache = {};
            const customerMap = new Map();
            const ownerSealCache = new Map();
            let companySealObjectUrl = "";
            let companyInfoState = {
                company_name: "",
                postal_code: "",
                address: "",
                tel: "",
                fax: "",
                mail: "",
                sealUrl: "",
            };
            let ownerSealState = {
                employeeId: "",
                url: "",
                requestId: 0,
            };

            const setItemField = (row, field, value) => {
                ctx.setFieldValue(row.querySelector(`[data-issue-item-field="${field}"]`), value);
            };
            const readItemField = (row, field) => row.querySelector(`[data-issue-item-field="${field}"]`)?.value?.trim() || "";
            const getItemInput = (row, field) => row.querySelector(`[data-issue-item-field="${field}"]`);

            const collectItems = () => {
                const rows = Array.from(form.lineItems ? form.lineItems.querySelectorAll(".order-issue-item-row") : []);
                return rows.map((row) => {
                    const priceInput = readItemField(row, "price");
                    const taxInput = readItemField(row, "tax");
                    return {
                        row,
                        itemName: readItemField(row, "item"),
                        priceInput,
                        price: ctx.parseMoneyValue(priceInput),
                        taxInput,
                        tax: ctx.parseMoneyValue(taxInput),
                        unit: readItemField(row, "unit"),
                    };
                });
            };

            const summarizeItems = () => {
                const items = collectItems();
                const totalPrice = items.reduce((sum, item) => sum + item.price, 0);
                const totalTax = items.reduce((sum, item) => sum + item.tax, 0);
                const itemNames = Array.from(new Set(items.map((item) => item.itemName).filter(Boolean)));
                return {
                    items,
                    totalPrice,
                    totalTax,
                    totalAmount: totalPrice + totalTax,
                    itemName: itemNames.join("、"),
                    periodStart: form.start.value || "",
                    periodEnd: form.end.value || "",
                };
            };

            const createItemRow = () => {
                const row = document.createElement("div");
                row.className = "order-issue-item-row";
                row.innerHTML = `
                    <label class="c-inline-field">
                        <span>项目</span>
                        <input type="text" placeholder="项目" data-issue-item-field="item"/>
                    </label>
                    <label class="c-inline-field">
                        <span>单价</span>
                        <input type="text" placeholder="¥ 0" data-issue-item-field="price"/>
                    </label>
                    <label class="c-inline-field">
                        <span>税金</span>
                        <input type="text" placeholder="¥ 0" data-issue-item-field="tax"/>
                    </label>
                    <label class="c-inline-field">
                        <span>单位</span>
                        <input type="text" placeholder="式" data-issue-item-field="unit"/>
                    </label>
                    <button class="c-btn c-btn-ghost c-btn-sm order-issue-item-remove" type="button" data-action="remove-issue-line" aria-label="删除">×</button>
                `;
                return row;
            };

            const setLineItems = (lineItems) => {
                if (!form.lineItems) return;
                form.lineItems.innerHTML = "";
                const items = Array.isArray(lineItems) && lineItems.length ? lineItems : [{}];
                items.forEach((item) => {
                    const row = createItemRow();
                    setItemField(row, "item", item.item ?? item.itemName ?? "");
                    setItemField(row, "price", item.price ?? "");
                    setItemField(row, "tax", item.tax ?? "");
                    setItemField(row, "unit", item.unit ?? "");
                    form.lineItems.appendChild(row);
                });
            };

            const setDialogMode = (mode) => {
                dialogMode = mode;
                const isEdit = mode === "edit";
                if (createTitle) createTitle.textContent = isEdit ? ctx.t("order.action.edit_issue") : ctx.t("order.action.create_issue");
                if (submitButton) submitButton.textContent = isEdit ? ctx.t("common.save") : ctx.t("common.create");
            };

            const setFormEditability = (status) => {
                const isEdit = dialogMode === "edit";
                const isCreated = !isEdit || status === "已创建";
                const isApproving = isEdit && status === "承认中";
                const canSave = !isEdit || isCreated || isApproving;
                if (form.status) {
                    ctx.fillIssueStatusOptions(
                        form.status,
                        isApproving ? ["已承认", "已取消"] : ["已创建", "承认中", "已承认", "已取消"],
                        ""
                    );
                    form.status.value = isApproving ? "已承认" : (status || "已创建");
                    form.status.disabled = !isEdit || (isEdit && !isCreated && !isApproving);
                }
                [
                    form.orderNo,
                    form.projectName,
                    form.customerName,
                    form.start,
                    form.end,
                    form.owner,
                    form.workContent,
                    form.workPlace,
                    form.contractType,
                    form.paymentTerms,
                    form.remark,
                ].forEach((field) => {
                    if (field) field.disabled = !isCreated;
                });
                if (form.lineAdd) form.lineAdd.disabled = !isCreated;
                if (form.lineItems) {
                    form.lineItems.querySelectorAll("input, button").forEach((field) => {
                        field.disabled = !isCreated;
                    });
                }
                if (submitButton) submitButton.style.display = canSave ? "" : "none";
            };

            const resetForm = () => {
                ctx.clearFields([
                    form.projectName,
                    form.customerName,
                    form.customerId,
                    form.start,
                    form.end,
                    form.workContent,
                    form.workPlace,
                    form.contractType,
                    form.paymentTerms,
                    form.remark,
                ]);
                ctx.setFieldValue(form.orderNo, ctx.buildIssueOrderNo());
                setFormEditability("已创建");
                if (form.customerList) form.customerList.innerHTML = "";
                customerMap.clear();
                setLineItems([]);
                updatePreview();
            };

            const populateForm = (item) => {
                if (!item) return;
                ctx.setFieldValues([
                    [form.orderNo, item.order_no],
                    [form.projectName, item.project_name],
                    [form.customerName, item.customer_name],
                    [form.customerId, item.customer_id],
                    [form.start, item.period_start],
                    [form.end, item.period_end],
                    [form.workContent, item.work_content],
                    [form.workPlace, item.work_place],
                    [form.contractType, item.contract_type],
                    [form.paymentTerms, item.payment_terms],
                    [form.remark, item.remark],
                ]);
                const status = item.status || "已创建";
                setFormEditability(status);
                if (form.status) form.status.value = status === "承认中" ? "已承认" : status;
                setLineItems(item.line_items || []);
                setFormEditability(status);
                updatePreview();
            };

            const renderCompanyInfo = () => {
                if (preview.companyName) preview.companyName.textContent = companyInfoState.company_name || "";
                if (preview.companyPostalCode) preview.companyPostalCode.textContent = companyInfoState.postal_code || "";
                if (preview.companyAddress) preview.companyAddress.textContent = companyInfoState.address || "";
                if (preview.companyTel) preview.companyTel.textContent = companyInfoState.tel || "";
                if (preview.companyFax) preview.companyFax.textContent = companyInfoState.fax || "";
                if (preview.companyMail) preview.companyMail.textContent = companyInfoState.mail || "";
                if (preview.companySeal) {
                    preview.companySeal.innerHTML = "";
                    preview.companySeal.classList.toggle("is-filled", Boolean(companyInfoState.sealUrl));
                    if (companyInfoState.sealUrl) {
                        const img = document.createElement("img");
                        img.src = companyInfoState.sealUrl;
                        img.alt = "印";
                        preview.companySeal.appendChild(img);
                    }
                }
            };

            const renderOwnerSeal = (sealUrl, ownerName = "") => {
                if (!preview.ownerSeal) return;
                preview.ownerSeal.innerHTML = "";
                preview.ownerSeal.classList.toggle("is-filled", Boolean(sealUrl));
                if (!sealUrl) return;
                const img = document.createElement("img");
                img.src = sealUrl;
                img.alt = ownerName ? `${ownerName}印` : "担当印";
                preview.ownerSeal.appendChild(img);
            };

            const fetchOwnerSealUrl = async (employeeId) => {
                const key = String(employeeId || "");
                if (!key) return "";
                if (ownerSealCache.has(key)) return ownerSealCache.get(key);
                try {
                    const response = await fetch(`/api/employees/${encodeURIComponent(key)}/seal?v=${encodeURIComponent(Date.now())}`, {
                        credentials: "same-origin"
                    });
                    if (!response.ok) {
                        ownerSealCache.set(key, "");
                        return "";
                    }
                    const blob = await response.blob();
                    if (!blob || !blob.size) {
                        ownerSealCache.set(key, "");
                        return "";
                    }
                    const url = URL.createObjectURL(blob);
                    ownerSealCache.set(key, url);
                    return url;
                } catch (error) {
                    console.warn(error);
                    ownerSealCache.set(key, "");
                    return "";
                }
            };

            const updateOwnerSeal = async (owner) => {
                const employeeId = owner && owner.id ? String(owner.id) : "";
                const ownerName = owner && owner.name ? owner.name : "";
                if (!employeeId) {
                    ownerSealState = {
                        ...ownerSealState,
                        employeeId: "",
                        url: "",
                        requestId: ownerSealState.requestId + 1,
                    };
                    renderOwnerSeal("", ownerName);
                    return;
                }
                if (ownerSealState.employeeId === employeeId && ownerSealState.url !== undefined) {
                    renderOwnerSeal(ownerSealState.url, ownerName);
                    return;
                }
                const requestId = ownerSealState.requestId + 1;
                ownerSealState = { employeeId, url: "", requestId };
                renderOwnerSeal("", ownerName);
                const sealUrl = await fetchOwnerSealUrl(employeeId);
                if (ownerSealState.requestId !== requestId) return;
                ownerSealState = { employeeId, url: sealUrl, requestId };
                renderOwnerSeal(sealUrl, ownerName);
            };

            const clearCompanySealObjectUrl = () => {
                if (companySealObjectUrl) {
                    URL.revokeObjectURL(companySealObjectUrl);
                    companySealObjectUrl = "";
                }
            };

            const clearOwnerSealObjectUrls = () => {
                ownerSealCache.forEach((url) => {
                    if (url) URL.revokeObjectURL(url);
                });
                ownerSealCache.clear();
            };

            const fetchCompanySealUrl = async (filename) => {
                clearCompanySealObjectUrl();
                if (!filename) return "";
                try {
                    const response = await fetch(`/api/company-info/seal?v=${encodeURIComponent(`${filename}-${Date.now()}`)}`, {
                        credentials: "same-origin"
                    });
                    if (!response.ok) return "";
                    const blob = await response.blob();
                    if (!blob || !blob.size) return "";
                    companySealObjectUrl = URL.createObjectURL(blob);
                    return companySealObjectUrl;
                } catch (error) {
                    console.warn(error);
                    return "";
                }
            };

            const fetchCompanyInfo = async () => {
                try {
                    const payload = await window.requestJson("/api/company-info", { method: "GET" });
                    const settings = payload && payload.data && payload.data.settings ? payload.data.settings : {};
                    const sealUrl = await fetchCompanySealUrl(settings.seal_filename || "");
                    companyInfoState = {
                        ...companyInfoState,
                        company_name: String(settings.company_name || ""),
                        postal_code: String(settings.postal_code || ""),
                        address: String(settings.address || ""),
                        tel: String(settings.tel || ""),
                        fax: String(settings.fax || ""),
                        mail: String(settings.mail || ""),
                        sealUrl,
                    };
                } catch (error) {
                    console.warn(error);
                    clearCompanySealObjectUrl();
                    companyInfoState = { ...companyInfoState, sealUrl: "" };
                }
                renderCompanyInfo();
                return companyInfoState;
            };

            function updatePreview() {
                const summary = summarizeItems();
                const price = summary.totalPrice;
                const tax = summary.totalTax;
                const total = price + tax;
                const owner = ctx.readOwnerSelect(form.owner);
                renderCompanyInfo();
                updateOwnerSeal(owner);
                if (preview.orderNo) preview.orderNo.textContent = form.orderNo.value.trim();
                if (preview.orderDate) preview.orderDate.textContent = ctx.todayText();
                if (preview.customer) {
                    const name = form.customerName.value.trim();
                    preview.customer.textContent = name ? `${name} 御中` : "御中";
                }
                if (preview.project) preview.project.textContent = form.projectName.value.trim();
                if (preview.workContent) preview.workContent.textContent = form.workContent.value.trim();
                if (preview.period) preview.period.textContent = ctx.buildPeriodText(summary.periodStart, summary.periodEnd);
                if (preview.workPlace) preview.workPlace.textContent = form.workPlace.value.trim();
                if (preview.contractType) preview.contractType.textContent = form.contractType.value.trim();
                if (preview.paymentTerms) preview.paymentTerms.textContent = form.paymentTerms.value.trim();
                if (preview.owner) preview.owner.textContent = owner.name || "";
                if (preview.total) preview.total.textContent = ctx.formatYenValue(total);
                if (preview.subtotal) preview.subtotal.textContent = ctx.formatYenValue(price);
                if (preview.tax) preview.tax.textContent = ctx.formatYenValue(tax);
                if (preview.summaryTotal) preview.summaryTotal.textContent = ctx.formatYenValue(total);
                if (preview.remark) preview.remark.textContent = form.remark.value.trim();
                if (preview.detailBody) {
                    const rows = summary.items.map((item) => ({
                        item: item.itemName || form.projectName.value.trim(),
                        unit: item.unit,
                        amount: item.price ? ctx.formatYenValue(item.price) : "",
                        tax: item.tax ? ctx.formatYenValue(item.tax) : "",
                    }));
                    const minRows = 8;
                    preview.detailBody.innerHTML = "";
                    for (let i = 0; i < Math.max(rows.length, minRows); i += 1) {
                        const row = rows[i] || {};
                        const tr = document.createElement("tr");
                        tr.innerHTML = `
                            <td>${ctx.escapeHtml(row.item)}</td>
                            <td>${ctx.escapeHtml(row.amount)}</td>
                            <td>${ctx.escapeHtml(row.unit)}</td>
                            <td>${ctx.escapeHtml(row.tax)}</td>
                        `;
                        preview.detailBody.appendChild(tr);
                    }
                }
            }

            const buildPdfFileName = () => {
                const rawNo = form.orderNo?.value?.trim() || "";
                const normalized = rawNo.replace(/[\\/:*?"<>|]/g, "_");
                return normalized ? `${normalized}.pdf` : `${ctx.buildIssueOrderNo()}.pdf`;
            };

            const buildSafePdfName = (item) => {
                const rawNo = item?.order_no || ctx.buildIssueOrderNo();
                const normalized = String(rawNo).replace(/[\\/:*?"<>|]/g, "_");
                return `${normalized || "purchase_order"}.pdf`;
            };

            const hasStoredPdf = (item) => Boolean(item?.id && item?.pdf_file);

            const getStoredPdfUrl = (item) => (
                hasStoredPdf(item)
                    ? `/api/purchase-orders/${encodeURIComponent(item.id)}/pdf`
                    : ""
            );

            const setSendPdfDisplayMode = (item) => {
                const pdfUrl = getStoredPdfUrl(item);
                if (sendPdfFrame) {
                    sendPdfFrame.hidden = !pdfUrl;
                    sendPdfFrame.src = pdfUrl || "about:blank";
                }
                if (sendNoPdfMessage) sendNoPdfMessage.hidden = Boolean(pdfUrl);
            };

            const getSendPdfBlob = async () => {
                const pdfUrl = getStoredPdfUrl(currentSendItem);
                if (!pdfUrl) throw new Error("没有PDF");
                const response = await fetch(pdfUrl, { credentials: "same-origin" });
                if (!response.ok) throw new Error("PDF文件读取失败");
                return response.blob();
            };

            const renderSendAttachmentList = () => {
                if (!sendFields.attachmentList) return;
                if (sendFields.filesStatus) {
                    sendFields.filesStatus.textContent = sendExtraFiles.length
                        ? `已添加 ${sendExtraFiles.length} 个附件`
                        : "未添加附件";
                }
                const rows = [];
                if (hasStoredPdf(currentSendItem)) {
                    rows.push(`<div class="order-send-attachment-item"><span>PDF文件：${ctx.escapeHtml(buildSafePdfName(currentSendItem))}</span></div>`);
                }
                sendExtraFiles.forEach((file, index) => {
                    rows.push(`
                        <div class="order-send-attachment-item">
                            <span>${ctx.escapeHtml(file.name)}</span>
                            <button type="button" data-remove-send-file="${index}">删除</button>
                        </div>
                    `);
                });
                if (!rows.length) {
                    sendFields.attachmentList.textContent = "暂无附件";
                    return;
                }
                sendFields.attachmentList.innerHTML = rows.join("");
            };

            const closeSendRecipientMenu = () => {
                if (sendFields.toOptions) sendFields.toOptions.hidden = true;
            };

            const renderSendRecipientOptions = () => {
                if (!sendFields.toOptions) return;
                sendFields.toOptions.innerHTML = "";
                sendRecipientOptions.forEach((option) => {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.className = "order-send-combobox-option";
                    button.dataset.email = option.email;
                    button.innerHTML = `
                        <span class="order-send-combobox-name">${ctx.escapeHtml(option.name || option.email)}</span>
                        <span class="order-send-combobox-email">${ctx.escapeHtml(option.email)}</span>
                    `;
                    sendFields.toOptions.appendChild(button);
                });
            };

            const fetchSendRecipient = async (item) => {
                sendRecipientOptions = [];
                if (sendFields.to) sendFields.to.value = "";
                if (sendFields.toOptions) sendFields.toOptions.innerHTML = "";
                closeSendRecipientMenu();
                const customerId = item?.customer_id;
                if (!customerId) return "";
                try {
                    const payload = await window.requestJson(`/api/customers/${encodeURIComponent(customerId)}`, { method: "GET" });
                    const customer = payload?.data?.item || {};
                    const options = [
                        { name: customer.contact1_name || "联系人1", email: customer.contact1_email },
                        { name: customer.company_name || "公司邮箱", email: customer.company_email },
                        { name: customer.contact2_name || "联系人2", email: customer.contact2_email },
                        { name: customer.contact3_name || "联系人3", email: customer.contact3_email },
                    ].map((option) => ({
                        name: String(option.name || "").trim(),
                        email: String(option.email || "").trim(),
                    })).filter((option) => option.email);
                    const seenEmails = new Set();
                    sendRecipientOptions = options.filter((option) => {
                        if (seenEmails.has(option.email)) return false;
                        seenEmails.add(option.email);
                        return true;
                    });
                    renderSendRecipientOptions();
                    if (sendFields.to) sendFields.to.value = sendRecipientOptions[0]?.email || "";
                } catch (error) {
                    console.warn(error);
                }
                return sendFields.to ? sendFields.to.value : "";
            };

            const normalizeMultiline = (text) => {
                if (typeof text !== "string") return "";
                let clean = text
                    .replace(/\r\n/g, "\n")
                    .replace(/\\n/g, "\n")
                    .replace(/\t/g, "    ");
                const trimmed = clean.trim();
                if (trimmed.startsWith('"') && trimmed.endsWith('"')) clean = trimmed.slice(1, -1);
                return clean;
            };

            const loadSendTemplate = async (forceRefresh = false) => {
                if (!forceRefresh && Object.prototype.hasOwnProperty.call(sendTemplateCache, sendTemplateName)) {
                    return sendTemplateCache[sendTemplateName];
                }
                const payload = await window.requestJson(`/api/mail-templates/${encodeURIComponent(sendTemplateName)}`, {
                    method: "GET",
                }, {
                    throwOnFailure: true,
                    fallbackMessage: "加载模板失败",
                });
                const template = payload.data && typeof payload.data.template === "string" ? payload.data.template : "";
                sendTemplateCache[sendTemplateName] = template;
                return template;
            };

            const applySendTemplateToBody = async () => {
                if (!sendFields.body) return;
                try {
                    const template = await loadSendTemplate();
                    if (!sendFields.body.value.trim()) sendFields.body.value = normalizeMultiline(template);
                } catch (error) {
                    console.warn("加载发注邮件模板失败", error);
                }
            };

            const openSendTemplateDialog = async () => {
                if (!sendTemplateDialog || !sendTemplateContent) return;
                try {
                    const template = await loadSendTemplate(true);
                    sendTemplateContent.value = normalizeMultiline(template);
                    sendTemplateDialog.showModal();
                } catch (error) {
                    console.error("加载模板失败", error);
                    alert(error.message || "加载模板失败");
                }
            };

            const saveSendTemplate = async () => {
                if (!sendTemplateContent || !sendTemplateSave) return;
                const originalText = sendTemplateSave.textContent;
                sendTemplateSave.disabled = true;
                sendTemplateSave.textContent = "保存中...";
                try {
                    const template = normalizeMultiline(sendTemplateContent.value);
                    await window.requestJson(`/api/mail-templates/${encodeURIComponent(sendTemplateName)}`, {
                        body: JSON.stringify({ template }),
                    }, {
                        throwOnFailure: true,
                        fallbackMessage: "保存模板失败",
                    });
                    sendTemplateCache[sendTemplateName] = template;
                    if (sendFields.body) {
                        sendFields.body.value = template;
                        sendFields.body.focus();
                    }
                    sendTemplateDialog?.close();
                } catch (error) {
                    console.error("保存模板失败", error);
                    alert(error.message || "保存模板失败");
                } finally {
                    sendTemplateSave.disabled = false;
                    sendTemplateSave.textContent = originalText || "保存";
                }
            };

            const openSendDialog = async (item) => {
                if (!sendDialog || !item) return;
                currentSendItem = item;
                sendExtraFiles = [];
                sendRecipientOptions = [];
                if (sendFields.subject) sendFields.subject.value = item.project_name ? `${item.project_name} 注文書` : "注文書";
                if (sendFields.type) sendFields.type.value = "3";
                if (sendFields.to) sendFields.to.value = "";
                if (sendFields.toOptions) sendFields.toOptions.innerHTML = "";
                closeSendRecipientMenu();
                if (sendFields.body) sendFields.body.value = "";
                if (sendFields.cc) sendFields.cc.value = "";
                if (sendFields.files) sendFields.files.value = "";
                renderSendAttachmentList();
                setSendPdfDisplayMode(item);
                fetchSendRecipient(item);
                sendDialog.showModal();
                applySendTemplateToBody();
            };

            const submitSendMail = async () => {
                if (!currentSendItem || !sendSubmit) return;
                const subject = sendFields.subject?.value.trim() || "";
                const body = sendFields.body?.value.trim() || "";
                const recipient = sendFields.to?.value.trim() || "";
                const mailType = Number(sendFields.type?.value || 3);
                if (!subject) return alert("请输入邮件主题"), sendFields.subject?.focus();
                if (!hasStoredPdf(currentSendItem)) return alert("没有PDF，无法发送。");
                if (!body) return alert("请输入邮件内容"), sendFields.body?.focus();
                if (!recipient) return alert("请输入收件人，或先在客户资料中维护邮箱。"), sendFields.to?.focus();
                const originalText = sendSubmit.textContent;
                sendSubmit.disabled = true;
                sendSubmit.textContent = "发送中...";
                try {
                    const pdfBlob = await getSendPdfBlob();
                    const attachments = [{
                        filename: buildSafePdfName(currentSendItem),
                        content_type: "application/pdf",
                        content: await ctx.readBlobAsBase64(pdfBlob),
                    }];
                    const extraAttachments = await Promise.all(sendExtraFiles.map(async (file) => ({
                        filename: file.name,
                        content_type: file.type || "application/octet-stream",
                        content: await ctx.readBlobAsBase64(file),
                    })));
                    attachments.push(...extraAttachments);
                    await window.requestJson("/api/send-mail", {
                        body: JSON.stringify({
                            to: recipient,
                            cc: sendFields.cc?.value.trim() || "",
                            subject,
                            body,
                            attachments,
                            mail_type: Number.isFinite(mailType) ? mailType : 3,
                        }),
                    }, {
                        throwOnFailure: true,
                        fallbackMessage: "发送失败",
                    });
                    alert("发送成功");
                    sendDialog.close();
                } catch (error) {
                    console.error("发送邮件失败", error);
                    alert(error.message || "发送失败");
                } finally {
                    sendSubmit.disabled = false;
                    sendSubmit.textContent = originalText || "发送 >";
                }
            };

            const exportPdfBlob = async () => {
                if (!pdfPreviewPage) throw new Error("未找到发注书预览区域");
                if (!window.html2canvas || !window.jspdf || !window.jspdf.jsPDF) throw new Error("PDF生成依赖未加载");
                updatePreview();
                const clone = pdfPreviewPage.cloneNode(true);
                clone.style.width = `${pdfPreviewPage.offsetWidth}px`;
                clone.style.maxWidth = `${pdfPreviewPage.offsetWidth}px`;
                clone.style.background = "#ffffff";
                const stage = document.createElement("div");
                stage.style.position = "fixed";
                stage.style.left = "-100000px";
                stage.style.top = "0";
                stage.style.zIndex = "-1";
                stage.appendChild(clone);
                document.body.appendChild(stage);
                try {
                    const canvas = await window.html2canvas(clone, {
                        scale: 2,
                        backgroundColor: "#ffffff",
                        useCORS: true,
                    });
                    const imgData = canvas.toDataURL("image/png");
                    const { jsPDF } = window.jspdf;
                    const pdf = new jsPDF("p", "pt", "a4");
                    const pageWidth = pdf.internal.pageSize.getWidth();
                    const pageHeight = pdf.internal.pageSize.getHeight();
                    const margin = 20;
                    const maxWidth = pageWidth - margin * 2;
                    const maxHeight = pageHeight - margin * 2;
                    const scale = Math.min(maxWidth / canvas.width, maxHeight / canvas.height);
                    const drawWidth = canvas.width * scale;
                    const drawHeight = canvas.height * scale;
                    const x = (pageWidth - drawWidth) / 2;
                    const y = (pageHeight - drawHeight) / 2;
                    pdf.addImage(imgData, "PNG", x, y, drawWidth, drawHeight, undefined, "FAST");
                    return pdf.output("blob");
                } finally {
                    stage.remove();
                }
            };

            const buildFormData = (payload, pdfBlob) => {
                const formData = new FormData();
                Object.entries(payload).forEach(([key, value]) => {
                    if (Array.isArray(value) || (value && typeof value === "object")) {
                        formData.append(key, JSON.stringify(value));
                    } else if (value !== null && value !== undefined) {
                        formData.append(key, String(value));
                    }
                });
                formData.append("pdf_file", pdfBlob, buildPdfFileName());
                return formData;
            };

            const getLineTotal = (item) => {
                const rows = Array.isArray(item && item.line_items) ? item.line_items : [];
                return rows.reduce((sum, row) => {
                    const price = ctx.parseMoneyValue(row.price ?? "");
                    const tax = ctx.parseMoneyValue(row.tax ?? "");
                    return sum + price + tax;
                }, 0);
            };

            const renderRow = (item, status, statusLabel, periodStart, periodEnd) => {
                const totalAmount = getLineTotal(item);
                return `
                    <tr data-id="${ctx.escapeHtml(item.id)}">
                      <td>${ctx.escapeHtml(item.order_no || "-")}</td>
                      ${ctx.renderProjectCustomerCell(item)}
                      <td>${ctx.escapeHtml(item.work_place || "-")}</td>
                      <td>${ctx.escapeHtml(ctx.formatYenValue(totalAmount))}</td>
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

            const buildPayload = (fromDetail) => {
                const owner = ctx.readOwnerSelect(fromDetail ? ctx.detailFields.owner : form.owner);
                const summary = fromDetail ? null : summarizeItems();
                const lineItems = summary
                    ? summary.items.map((item) => ({
                        item: item.itemName,
                        price: item.price,
                        tax: item.tax,
                        unit: item.unit,
                    }))
                    : [];
                const payload = {
                    order_no: fromDetail ? ctx.detailFields.orderNo.value.trim() : form.orderNo.value.trim(),
                    project_name: fromDetail ? ctx.detailFields.project.value.trim() : form.projectName.value.trim(),
                    customer_id: Number(fromDetail ? ctx.detailFields.customerId.value : form.customerId.value) || 0,
                    customer_name: fromDetail ? ctx.detailFields.client.value.trim() : form.customerName.value.trim(),
                    status: fromDetail ? ctx.detailFields.status.value : form.status.value,
                    period_start: fromDetail ? ctx.detailFields.start.value : (summary.periodStart || form.start.value),
                    period_end: fromDetail ? ctx.detailFields.end.value : (summary.periodEnd || form.end.value),
                    person_in_charge_id: owner.id,
                    person_in_charge: owner.name,
                    remark: fromDetail ? ctx.detailFields.remark.value.trim() : form.remark.value.trim(),
                };
                if (!fromDetail) {
                    payload.work_content = form.workContent.value.trim();
                    payload.work_place = form.workPlace.value.trim();
                    payload.contract_type = form.contractType.value.trim();
                    payload.payment_terms = form.paymentTerms.value.trim();
                    payload.line_items = lineItems;
                }
                return payload;
            };

            const validateForm = () => {
                const orderNo = form.orderNo.value.trim();
                if (!orderNo) return ctx.showMissingField(ctx.t("order.field.order_no"), form.orderNo), false;
                const project = form.projectName.value.trim();
                if (!project) return ctx.showMissingField(ctx.t("order.field.project"), form.projectName), false;
                const customer = form.customerName.value.trim();
                if (!customer) return ctx.showMissingField(ctx.t("order.field.customer"), form.customerName), false;
                const status = form.status.value;
                if (!status || status === "请选择状态") return ctx.showMissingField(ctx.t("common.field.status"), form.status), false;
                const items = collectItems();
                if (!items.length) return ctx.showMissingField("契约明细", form.lineAdd), false;
                for (const item of items) {
                    if (!item.itemName) return ctx.showMissingField("项目", getItemInput(item.row, "item")), false;
                    if (!item.priceInput) return ctx.showMissingField("单价", getItemInput(item.row, "price")), false;
                    if (!item.taxInput) return ctx.showMissingField("税金", getItemInput(item.row, "tax")), false;
                    if (!item.unit) return ctx.showMissingField("单位", getItemInput(item.row, "unit")), false;
                }
                const owner = ctx.readOwnerSelect(form.owner);
                if (!owner.id) return ctx.showMissingField(ctx.t("common.field.owner"), form.owner), false;
                return true;
            };

            const openCreateDialog = async () => {
                if (!createDialog) return;
                currentEditId = null;
                currentEditStatus = "";
                setDialogMode("create");
                resetForm();
                await Promise.all([
                    ctx.loadOwnerSelectOptions(form.owner),
                    fetchCompanyInfo(),
                ]);
                updatePreview();
                createDialog.showModal();
            };

            const openEditDialog = async (item) => {
                if (!createDialog || !item) return;
                currentEditId = item.id;
                currentEditStatus = item.status || "已创建";
                setDialogMode("edit");
                populateForm(item);
                await Promise.all([
                    ctx.loadOwnerSelectOptions(form.owner, item.person_in_charge_id || item.person_in_charge || ""),
                    fetchCompanyInfo(),
                ]);
                updatePreview();
                createDialog.showModal();
            };

            const submitUpdate = async () => {
                const statusOnly = currentEditStatus === "承认中";
                if (!currentEditId) return;
                if (statusOnly) {
                    if (!["已承认", "已取消"].includes(form.status.value)) {
                        ctx.showMissingField(ctx.t("common.field.status"), form.status);
                        return;
                    }
                } else if (!validateForm()) {
                    return;
                }
                const payload = statusOnly ? { status: form.status.value } : buildPayload(false);
                const originalText = submitButton ? submitButton.textContent : "";
                if (submitButton) {
                    submitButton.disabled = true;
                    submitButton.textContent = statusOnly ? "保存中..." : "PDF生成中...";
                }
                try {
                    const responsePayload = statusOnly
                        ? await window.requestJson(`/api/purchase-orders/${currentEditId}`, {
                            method: "PUT",
                            body: JSON.stringify(payload),
                        })
                        : await window.requestJson(`/api/purchase-orders/${currentEditId}`, {
                            method: "PUT",
                            headers: {},
                            body: buildFormData(payload, await exportPdfBlob()),
                        });
                    if (!responsePayload.success) {
                        alert(ctx.getRequestErrorMessage({ payload: responsePayload }, ctx.t("common.save_failed")));
                        return;
                    }
                    createDialog.close();
                    currentEditId = null;
                    currentEditStatus = "";
                    setDialogMode("create");
                    resetForm();
                    ctx.fetchOrders();
                } catch (error) {
                    alert(ctx.getRequestErrorMessage(error, ctx.t("common.save_failed_retry")));
                } finally {
                    if (submitButton) {
                        submitButton.disabled = false;
                        submitButton.textContent = originalText || ctx.t("common.save");
                    }
                }
            };

            const submitDialog = () => {
                if (dialogMode === "edit") {
                    submitUpdate();
                    return;
                }
                ctx.submitCreate("issue");
            };

            [
                form.orderNo,
                form.projectName,
                form.customerName,
                form.status,
                form.start,
                form.end,
                form.owner,
                form.workContent,
                form.workPlace,
                form.contractType,
                form.paymentTerms,
                form.remark,
            ].forEach((field) => {
                if (!field) return;
                field.addEventListener("input", updatePreview);
                field.addEventListener("change", updatePreview);
            });
            if (form.lineAdd && form.lineItems) {
                form.lineAdd.addEventListener("click", () => {
                    form.lineItems.appendChild(createItemRow());
                    updatePreview();
                });
            }
            if (form.lineItems) {
                form.lineItems.addEventListener("input", updatePreview);
                form.lineItems.addEventListener("change", updatePreview);
                form.lineItems.addEventListener("click", (event) => {
                    const btn = event.target.closest('[data-action="remove-issue-line"]');
                    if (!btn) return;
                    const row = btn.closest(".order-issue-item-row");
                    if (!row || row === form.lineItems.querySelector(".order-issue-item-row")) return;
                    row.remove();
                    updatePreview();
                });
            }
            if (sendSubmit) sendSubmit.addEventListener("click", submitSendMail);
            if (sendTemplateEdit) {
                sendTemplateEdit.addEventListener("click", (event) => {
                    event.preventDefault();
                    openSendTemplateDialog();
                });
            }
            if (sendTemplateSave) sendTemplateSave.addEventListener("click", saveSendTemplate);
            if (sendFields.files) {
                sendFields.files.addEventListener("change", () => {
                    const files = sendFields.files?.files ? Array.from(sendFields.files.files) : [];
                    if (!files.length) return;
                    sendExtraFiles.push(...files);
                    sendFields.files.value = "";
                    renderSendAttachmentList();
                });
            }
            if (sendFields.filesTrigger) {
                sendFields.filesTrigger.addEventListener("click", () => sendFields.files?.click());
            }
            if (sendFields.attachmentList) {
                sendFields.attachmentList.addEventListener("click", (event) => {
                    const button = event.target.closest("[data-remove-send-file]");
                    if (!button) return;
                    const index = Number(button.dataset.removeSendFile);
                    if (!Number.isInteger(index) || index < 0 || index >= sendExtraFiles.length) return;
                    sendExtraFiles.splice(index, 1);
                    renderSendAttachmentList();
                });
            }
            if (sendFields.toToggle) {
                sendFields.toToggle.addEventListener("click", () => {
                    if (!sendFields.toOptions) return;
                    if (sendFields.toOptions.hidden) {
                        if (!sendRecipientOptions.length) return;
                        renderSendRecipientOptions();
                        sendFields.toOptions.hidden = false;
                    } else {
                        closeSendRecipientMenu();
                    }
                });
            }
            if (sendFields.toOptions) {
                sendFields.toOptions.addEventListener("click", (event) => {
                    const option = event.target.closest(".order-send-combobox-option");
                    if (!option) return;
                    if (sendFields.to) {
                        sendFields.to.value = option.dataset.email || option.textContent.trim();
                        sendFields.to.focus();
                    }
                    closeSendRecipientMenu();
                });
            }
            document.addEventListener("click", (event) => {
                if (sendFields.toCombobox && !sendFields.toCombobox.contains(event.target)) {
                    closeSendRecipientMenu();
                }
            });

            return {
                baseUrl: "/api/purchase-orders",
                actions: [
                    { key: "common.edit", action: "edit", className: "c-btn c-btn-secondary c-btn-sm" },
                    { key: "order.action.send", action: "send", className: "c-btn c-btn-success-lite c-btn-sm" },
                ],
                form,
                customerMap,
                submitButton,
                openCreateDialog,
                openEditDialog,
                openSendDialog,
                closeCreateDialog() {
                    if (createDialog) {
                        createDialog.close();
                        resetForm();
                    }
                },
                submitDialog,
                validateForm,
                buildPayload,
                buildFormData,
                exportPdfBlob,
                renderRow,
                updatePreview,
                cleanup() {
                    clearCompanySealObjectUrl();
                    clearOwnerSealObjectUrls();
                },
            };
        }
    };
})();
