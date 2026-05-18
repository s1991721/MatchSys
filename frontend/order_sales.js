(function () {
    window.OrderSales = {
        init(ctx) {
            const createDialog = document.getElementById("createDialogAccept");
            const submitButton = document.getElementById("accept-create-submit");
            const pdfPreviewSlot = document.getElementById("acceptPdfPreviewSlot");
            const form = {
                orderNo: document.getElementById("accept-order-no"),
                projectName: document.getElementById("accept-project-name"),
                purchaseId: document.getElementById("accept-purchase-id"),
                customerName: document.getElementById("accept-customer-name"),
                customerId: document.getElementById("accept-customer-id"),
                customerList: document.getElementById("accept-customer-list"),
                technicianName: document.getElementById("accept-technician-name"),
                technicianId: document.getElementById("accept-technician-id"),
                technicianList: document.getElementById("accept-technician-list"),
                status: document.getElementById("accept-status"),
                price: document.getElementById("accept-price"),
                hours: document.getElementById("accept-hours"),
                start: document.getElementById("accept-start"),
                end: document.getElementById("accept-end"),
                owner: document.getElementById("accept-owner"),
                pdfFile: document.getElementById("accept-pdf-file"),
                remark: document.getElementById("accept-remark"),
            };
            const customerMap = new Map();
            const technicianMap = new Map();
            let pdfObjectUrl = "";

            const resetPdfPreview = () => {
                if (pdfObjectUrl) {
                    URL.revokeObjectURL(pdfObjectUrl);
                    pdfObjectUrl = "";
                }
                if (pdfPreviewSlot) {
                    pdfPreviewSlot.innerHTML = '<div class="order-accept-preview-empty">请选择受注书 PDF 文件进行预览</div>';
                }
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
                if (pdfPreviewSlot) {
                    pdfPreviewSlot.innerHTML = "";
                    const frame = document.createElement("iframe");
                    frame.className = "order-accept-preview-frame";
                    frame.title = "受注书PDF预览";
                    frame.src = pdfObjectUrl;
                    pdfPreviewSlot.appendChild(frame);
                }
            };

            const buildPayload = (fromDetail) => {
                const purchaseIdRaw = (fromDetail ? ctx.detailFields.purchaseId.value : form.purchaseId.value).trim();
                const owner = ctx.readOwnerSelect(fromDetail ? ctx.detailFields.owner : form.owner);
                return {
                    order_no: fromDetail ? ctx.detailFields.orderNo.value.trim() : form.orderNo.value.trim(),
                    project_name: fromDetail ? ctx.detailFields.project.value.trim() : form.projectName.value.trim(),
                    purchase_id: purchaseIdRaw ? Number(purchaseIdRaw) : null,
                    customer_id: Number(fromDetail ? ctx.detailFields.customerId.value : form.customerId.value) || 0,
                    customer_name: fromDetail ? ctx.detailFields.client.value.trim() : form.customerName.value.trim(),
                    technician_id: Number(fromDetail ? ctx.detailFields.technicianId.value : form.technicianId.value) || 0,
                    technician_name: fromDetail ? ctx.detailFields.engineer.value.trim() : form.technicianName.value.trim(),
                    status: fromDetail ? ctx.detailFields.status.value : form.status.value,
                    price: fromDetail ? ctx.detailFields.price.value.trim() : form.price.value.trim(),
                    working_hours: fromDetail ? ctx.detailFields.hours.value.trim() : form.hours.value.trim(),
                    period_start: fromDetail ? ctx.detailFields.start.value : form.start.value,
                    period_end: fromDetail ? ctx.detailFields.end.value : form.end.value,
                    person_in_charge_id: owner.id,
                    person_in_charge: owner.name,
                    remark: fromDetail ? ctx.detailFields.remark.value.trim() : form.remark.value.trim(),
                };
            };

            const validateForm = () => {
                const orderNo = form.orderNo.value.trim();
                if (!orderNo) return ctx.showMissingField(ctx.t("order.field.order_no"), form.orderNo), false;
                const project = form.projectName.value.trim();
                if (!project) return ctx.showMissingField(ctx.t("order.field.project"), form.projectName), false;
                const customer = form.customerName.value.trim();
                if (!customer) return ctx.showMissingField(ctx.t("order.field.customer_accept"), form.customerName), false;
                const technician = form.technicianName.value.trim();
                if (!technician) return ctx.showMissingField(ctx.t("common.field.technician"), form.technicianName), false;
                const status = form.status.value;
                if (!status || status === "请选择状态") return ctx.showMissingField(ctx.t("common.field.status"), form.status), false;
                const price = form.price.value.trim();
                if (!price) return ctx.showMissingField(ctx.t("order.field.price"), form.price), false;
                const hours = form.hours.value.trim();
                if (!hours) return ctx.showMissingField(ctx.t("order.field.hours"), form.hours), false;
                const start = form.start.value;
                const end = form.end.value;
                if (!start || !end) return ctx.showMissingField(ctx.t("order.field.period"), form.start), false;
                const owner = ctx.readOwnerSelect(form.owner);
                if (!owner.id) return ctx.showMissingField(ctx.t("common.field.owner"), form.owner), false;
                const pdfFile = form.pdfFile && form.pdfFile.files ? form.pdfFile.files[0] : null;
                if (!pdfFile) return ctx.showMissingField("受注书PDF", form.pdfFile), false;
                return true;
            };

            const renderRow = (item, status, statusLabel, periodStart, periodEnd) => {
                return `
                    <tr data-id="${ctx.escapeHtml(item.id)}">
                      <td>${ctx.escapeHtml(item.order_no || "-")}</td>
                      ${ctx.renderProjectCustomerCell(item)}
                      <td>${ctx.escapeHtml(item.technician_name || "-")}</td>
                      <td>${ctx.escapeHtml(ctx.formatBlankValue(item.price))}</td>
                      <td>${ctx.escapeHtml(ctx.formatBlankValue(item.working_hours))}</td>
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
                await ctx.loadOwnerSelectOptions(form.owner);
                updatePdfPreview();
                createDialog.showModal();
            };

            if (form.pdfFile) {
                form.pdfFile.addEventListener("change", updatePdfPreview);
            }

            return {
                baseUrl: "/api/sales-orders",
                actions: [
                    { key: "common.edit", action: "edit", className: "c-btn c-btn-secondary c-btn-sm" },
                ],
                form,
                customerMap,
                technicianMap,
                submitButton,
                openCreateDialog,
                closeCreateDialog() {
                    if (createDialog) createDialog.close();
                },
                validateForm,
                buildPayload,
                renderRow,
                cleanup() {
                    resetPdfPreview();
                },
            };
        }
    };
})();
