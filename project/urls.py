"""
URL configuration for project .

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.urls import path
from django.views.decorators.cache import cache_control
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from django.views.static import serve as static_serve

from attendance.views import (
    attendance_punch_api,
    attendance_record_edit_api,
    attendance_record_today_api,
    attendance_detail_api,
    attendance_summary_api,
    attendance_export_api,
    my_attendance_summary_api,
    my_attendance_detail_api,
)
from bpmatch.views import (
    mail_projects_api,
    mail_project_match_api,
    mail_project_search_api,
    wrong_mail_info_api,
    wrong_mail_detail_api,
    wrong_mail_stats_api,
    wrong_mail_export_api,
    mail_technician_search_api,
    my_mails_api,
    my_mails_query_api,
    my_mails_sync_api,
    my_mail_detail_api,
    my_mails_unread_count_api,
    gmail_attachment_open_api,
    extract_project_detail,
    extract_technician_detail,
    send_mail,
    send_bulk_mail,
    send_history,
)
from customer.views import (
    employee_names_api,
    customers_api,
    customer_detail_api,
    customer_contract_upload,
    customer_card_ocr_api,
    line_webhook_api,
)
from data_analysis.views import analysis_stats_api, home_match_stats_api
from employee.views import (
    change_password_api,
    employee_detail_api,
    employee_departments_api,
    employee_permission_api,
    employee_seal_api,
    employees_api,
    login_audit_api,
    login_api,
    logout_api,
    technician_detail_api,
    technician_ss_download,
    technician_ss_upload,
    technicians_api,
    user_logins_by_role_api,
    user_login_names_api,
)
from finance.views import (
    finance_payable_detail_api,
    finance_payable_payments_api,
    finance_payables_api,
    finance_payables_overview_api,
    finance_payment_detail_api,
    finance_payments_api,
    finance_receipt_detail_api,
    finance_receivable_detail_api,
    finance_receivable_receipts_api,
    finance_receivables_api,
    finance_receivables_overview_api,
    payroll_basic_info_api,
    payroll_basic_info_detail_api,
    payroll_monthly_api,
    payroll_monthly_calculate_api,
    payroll_monthly_detail_api,
    payroll_monthly_export_api,
)
from order.views import (
    pay_request_detail_api,
    pay_request_pdf_api,
    pay_request_update_api,
    pay_requests_api,
    purchase_orders_api,
    purchase_order_pdf_api,
    purchase_order_update_api,
    sales_orders_api,
    sales_order_detail_api,
    sales_order_pdf_api,
)
from permission.views import (
    menus_api,
    menu_detail_api,
    roles_api,
    role_detail_api,
)
from settings.views import (
    activation_code_api,
    activation_status_api,
    activation_validate_api,
    company_info_api,
    company_info_seal_api,
    mail_template_detail_api,
    sys_settings_ai_test_api,
    sys_settings_gmail_test_api,
    sys_settings_line_notify_test_api,
    sys_settings_sendmsg_receiver_test_api,
    sys_settings_sendmsg_test_api,
    sys_password_reset_api,
    sys_settings_section_api,
    sys_tasks_api,
    sys_task_logs_api,
    time_to_save,
    time_to_save_day,
    time_to_clean,
    time_to_backup,
    time_to_hello,
    time_to_sync_my_mails,
)

custom_404 = TemplateView.as_view(template_name="frontend/404.html")
handler404 = "project.urls.custom_404"

# Cache static-like templates only in production.
cache_static_asset = (
    cache_control(public=True, max_age=86400) if not settings.DEBUG else lambda view: view
)

urlpatterns = [
    # ###################################-Front End-###################################
    path("", RedirectView.as_view(url="/index.html", permanent=False)),
    path("index.html", TemplateView.as_view(template_name="frontend/index.html")),
    path("home.html", TemplateView.as_view(template_name="frontend/home.html")),

    # -------------------------------employee UI-------------------------------
    path("login.html", xframe_options_deny(TemplateView.as_view(template_name="frontend/login.html"))),
    path("profile.html", TemplateView.as_view(template_name="frontend/profile.html")),
    path("personnel.html", TemplateView.as_view(template_name="frontend/personnel.html")),
    path("people.html", TemplateView.as_view(template_name="frontend/people.html")),
    path("login_audit.html", TemplateView.as_view(template_name="frontend/login_audit.html")),
    # -------------------------------attendance UI-------------------------------
    path("attendance.html", TemplateView.as_view(template_name="frontend/attendance.html")),
    path("myattendance.html", TemplateView.as_view(template_name="frontend/myattendance.html")),
    # -------------------------------bpmatch UI-------------------------------
    path("bpmatch.html", TemplateView.as_view(template_name="frontend/bpmatch.html")),
    path("match.html", TemplateView.as_view(template_name="frontend/match.html")),
    path("bpsongxin.html", TemplateView.as_view(template_name="frontend/bpsongxin.html")),
    path("songxin.html", TemplateView.as_view(template_name="frontend/songxin.html")),
    path("songxinhistory.html", TemplateView.as_view(template_name="frontend/songxinhistory.html")),
    path("my_mail.html", TemplateView.as_view(template_name="frontend/my_mail.html")),
    # -------------------------------customer UI-------------------------------
    path("customer.html", TemplateView.as_view(template_name="frontend/customer.html")),
    path("bulk_email.html", TemplateView.as_view(template_name="frontend/bulk_email.html")),
    # -------------------------------order UI-------------------------------
    path("order.html", TemplateView.as_view(template_name="frontend/order.html")),
    path("pay_request.html", TemplateView.as_view(template_name="frontend/pay_request.html")),
    # -------------------------------finance UI-------------------------------
    path("finance.html", TemplateView.as_view(template_name="frontend/finance.html")),
    path("finance/finance.html", RedirectView.as_view(url="/finance.html", permanent=False)),
    path("finance/receivables.html", TemplateView.as_view(template_name="frontend/finance/receivables.html")),
    path("finance/receivables/overview.html", TemplateView.as_view(template_name="frontend/finance/receivables/overview.html")),
    path("finance/receivables/list.html", TemplateView.as_view(template_name="frontend/finance/receivables/list.html")),
    path("finance/payables.html", TemplateView.as_view(template_name="frontend/finance/payables.html")),
    path("finance/payables/overview.html", TemplateView.as_view(template_name="frontend/finance/payables/overview.html")),
    path("finance/payables/list.html", TemplateView.as_view(template_name="frontend/finance/payables/list.html")),
    path("finance/reimbursements.html", TemplateView.as_view(template_name="frontend/finance/reimbursements.html")),
    path("finance/reimbursements/requests.html", TemplateView.as_view(template_name="frontend/finance/reimbursements/requests.html")),
    path("finance/reimbursements/approval.html", TemplateView.as_view(template_name="frontend/finance/reimbursements/approval.html")),
    path("finance/reimbursements/receipts.html", TemplateView.as_view(template_name="frontend/finance/reimbursements/receipts.html")),
    path("finance/reimbursements/payment.html", TemplateView.as_view(template_name="frontend/finance/reimbursements/payment.html")),
    path("finance/reimbursements/stats.html", TemplateView.as_view(template_name="frontend/finance/reimbursements/stats.html")),
    path("finance/payroll.html", TemplateView.as_view(template_name="frontend/finance/payroll.html")),
    path("finance/payroll/basic-info.html", TemplateView.as_view(template_name="frontend/finance/payroll/basic-info.html")),
    path("finance/payroll/monthly-calculation.html", TemplateView.as_view(template_name="frontend/finance/payroll/monthly-calculation.html")),
    path("finance/payments.html", TemplateView.as_view(template_name="frontend/finance/payments.html")),
    path("finance/payments/ledger.html", TemplateView.as_view(template_name="frontend/finance/payments/ledger.html")),
    path("finance/reports.html", TemplateView.as_view(template_name="frontend/finance/reports.html")),
    path("finance/reports/monthly.html", TemplateView.as_view(template_name="frontend/finance/reports/monthly.html")),
    path("finance/reports/balance.html", TemplateView.as_view(template_name="frontend/finance/reports/balance.html")),
    path("finance/reports/profit.html", TemplateView.as_view(template_name="frontend/finance/reports/profit.html")),
    path("finance/reports/cashflow.html", TemplateView.as_view(template_name="frontend/finance/reports/cashflow.html")),
    path("finance/reports/exports.html", TemplateView.as_view(template_name="frontend/finance/reports/exports.html")),
    path("finance/settings.html", TemplateView.as_view(template_name="frontend/finance/settings.html")),
    path("finance/settings/annuity.html", TemplateView.as_view(template_name="frontend/finance/settings/annuity.html")),
    path("finance/settings/accounts.html", TemplateView.as_view(template_name="frontend/finance/settings/accounts.html")),
    path("finance/settings/terms.html", TemplateView.as_view(template_name="frontend/finance/settings/terms.html")),
    path("finance/settings/banks.html", TemplateView.as_view(template_name="frontend/finance/settings/banks.html")),
    path("finance/settings/payroll.html", TemplateView.as_view(template_name="frontend/finance/settings/payroll.html")),
    path("finance/settings/numbering.html", TemplateView.as_view(template_name="frontend/finance/settings/numbering.html")),
    path("finance/settings/reminders.html", TemplateView.as_view(template_name="frontend/finance/settings/reminders.html")),
    path("finance/my_salary.html", TemplateView.as_view(template_name="frontend/finance/my_salary.html")),
    # -------------------------------permission UI-------------------------------
    path("permission.html", TemplateView.as_view(template_name="frontend/permission.html")),
    # -------------------------------notification UI-------------------------------
    path("notification.html", TemplateView.as_view(template_name="frontend/notification.html")),
    path("analysis.html", TemplateView.as_view(template_name="frontend/analysis.html")),
    path("system_settings.html", TemplateView.as_view(template_name="frontend/system_settings.html")),
    # -------------------------------common-------------------------------
    path(
        "common.css",
        cache_static_asset(TemplateView.as_view(template_name="frontend/common.css", content_type="text/css")),
    ),
    path(
        "components.css",
        cache_static_asset(TemplateView.as_view(template_name="frontend/components.css", content_type="text/css")),
    ),
    path(
        "common.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/common.js", content_type="application/javascript")
        ),
    ),
    path(
        "error_code.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/error_code.js", content_type="application/javascript")
        ),
    ),
    path(
        "i18n.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/i18n.js", content_type="application/javascript")),
    ),
    path(
        "order_common.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/order_common.js", content_type="application/javascript")),
    ),
    path(
        "order_purchase.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/order_purchase.js", content_type="application/javascript")),
    ),
    path(
        "order_sales.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/order_sales.js", content_type="application/javascript")),
    ),
    path(
        "finance/finance.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/finance/finance.js", content_type="application/javascript")),
    ),
    path(
        "finance/receivables.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/finance/receivables.js", content_type="application/javascript")),
    ),
    path(
        "finance/payables.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/finance/payables.js", content_type="application/javascript")),
    ),
    path(
        "finance/reimbursements.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/finance/reimbursements.js", content_type="application/javascript")),
    ),
    path(
        "finance/payroll.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/finance/payroll.js", content_type="application/javascript")),
    ),
    path(
        "finance/payments.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/finance/payments.js", content_type="application/javascript")),
    ),
    path(
        "finance/reports.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/finance/reports.js", content_type="application/javascript")),
    ),
    path(
        "finance/settings.js",
        cache_static_asset(
            TemplateView.as_view(template_name="frontend/finance/settings.js", content_type="application/javascript")),
    ),
    path("favicon.png", static_serve, {"document_root": settings.BASE_DIR, "path": "favicon.png"}),
    path("favicon-32.png", static_serve, {"document_root": settings.BASE_DIR, "path": "favicon-32.png"}),
    path("favicon.ico", RedirectView.as_view(url="/favicon-32.png", permanent=False)),

    # ###################################-API-###################################
    # -------------------------------employee API-------------------------------
    path("api/login", login_api, name="employee-login"),
    path("api/login-audit", login_audit_api, name="login-audit"),
    path("api/user-logins/names", user_login_names_api, name="user-login-names"),
    path("api/user-logins/by-role", user_logins_by_role_api, name="user-logins-by-role"),
    path("api/employees/<int:employee_id>", employee_detail_api, name="employee-detail"),
    path("api/employees/<int:employee_id>/seal", employee_seal_api, name="employee-seal"),
    path("api/employees/<int:employee_id>/permission", employee_permission_api, name="employee-permission"),
    path("api/logout", logout_api, name="employee-logout"),
    path("api/change-password", change_password_api, name="employee-change-password"),
    path("api/employees", employees_api, name="employee-list"),
    path("api/employees/departments", employee_departments_api, name="employee-departments"),
    path("api/finance/receivables/overview", finance_receivables_overview_api, name="finance-receivables-overview"),
    path("api/finance/receivables", finance_receivables_api, name="finance-receivables"),
    path("api/finance/receivables/<int:receivable_id>", finance_receivable_detail_api, name="finance-receivable-detail"),
    path("api/finance/receivables/<int:receivable_id>/receipts", finance_receivable_receipts_api, name="finance-receivable-receipts"),
    path("api/finance/receipts/<int:receipt_id>", finance_receipt_detail_api, name="finance-receipt-detail"),
    path("api/finance/payables/overview", finance_payables_overview_api, name="finance-payables-overview"),
    path("api/finance/payables", finance_payables_api, name="finance-payables"),
    path("api/finance/payables/<int:payable_id>", finance_payable_detail_api, name="finance-payable-detail"),
    path("api/finance/payables/<int:payable_id>/payments", finance_payable_payments_api, name="finance-payable-payments"),
    path("api/finance/payments", finance_payments_api, name="finance-payments"),
    path("api/finance/payments/<int:payment_id>", finance_payment_detail_api, name="finance-payment-detail"),
    path("api/finance/payroll/basic-info", payroll_basic_info_api, name="payroll-basic-info"),
    path("api/finance/payroll/basic-info/<int:payroll_basic_id>", payroll_basic_info_detail_api, name="payroll-basic-info-detail"),
    path("api/finance/payroll/monthly", payroll_monthly_api, name="payroll-monthly"),
    path("api/finance/payroll/monthly/calculate", payroll_monthly_calculate_api, name="payroll-monthly-calculate"),
    path("api/finance/payroll/monthly/export", payroll_monthly_export_api, name="payroll-monthly-export"),
    path("api/finance/payroll/monthly/<int:calculation_id>", payroll_monthly_detail_api, name="payroll-monthly-detail"),
    path("api/technicians", technicians_api, name="technician-list"),
    path("api/technicians/<int:employee_id>", technician_detail_api, name="technician-detail"),
    path("api/technicians/<int:employee_id>/ss", technician_ss_upload, name="technician-ss-upload"),
    path("api/ss/<path:path>", technician_ss_download, name="technician-ss-download"),
    path("api/employees/names", employee_names_api, name="employee-names"),
    # -------------------------------attendance API-------------------------------
    path("api/attendance/punch", attendance_punch_api, name="attendance-punch"),
    path("api/attendance/record/edit", attendance_record_edit_api, name="attendance-record-edit"),
    path("api/attendance/record/today", attendance_record_today_api, name="attendance-record-today"),
    path("api/attendance/summary", attendance_summary_api, name="attendance-summary"),
    path("api/attendance/<int:employee_id>/detail", attendance_detail_api, name="attendance-detail"),
    path("api/attendance/<int:employee_id>/export", attendance_export_api, name="attendance-export"),
    path("api/my-attendance-summary", my_attendance_summary_api, name="my-attendance-summary"),
    path("api/my-attendance-detail", my_attendance_detail_api, name="my-attendance-detail"),
    # -------------------------------bpmatch API-------------------------------
    path("api/mail-projects", mail_projects_api, name="mail-projects"),
    path("api/mail-projects/match", mail_project_match_api, name="mail-projects-match"),
    path("api/mail-projects/search", mail_project_search_api, name="mail-projects-search"),
    path("api/wrong-mails", wrong_mail_info_api, name="wrong-mails"),
    path("api/wrong-mails-detail", wrong_mail_detail_api, name="wrong-mails-detail"),
    path("api/wrong-mails/stats", wrong_mail_stats_api, name="wrong-mails-stats"),
    path("api/wrong-mails/export", wrong_mail_export_api, name="wrong-mails-export"),
    path("api/mail-technicians/search", mail_technician_search_api, name="mail-technicians-search"),
    path("api/extract-project-detail", extract_project_detail, name="extract_project_detail"),
    path("api/extract-technician-detail", extract_technician_detail, name="extract_technician_detail"),
    path("api/my-mails", my_mails_api, name="my-mails"),
    path("api/my-mails/query", my_mails_query_api, name="my-mails-query"),
    path("api/my-mails/sync", my_mails_sync_api, name="my-mails-sync"),
    path("api/my-mails/unread-count", my_mails_unread_count_api, name="my-mails-unread-count"),
    path("api/my-mails/<str:mail_id>", my_mail_detail_api, name="my-mail-detail"),
    path(
        "api/gmail/messages/<str:message_id>/attachments/<str:attachment_id>",
        gmail_attachment_open_api,
        name="gmail-attachment-open",
    ),
    path("api/send-mail", send_mail, name="send_mail"),
    path("api/send-bulk-mail", send_bulk_mail, name="send_bulk_mail"),
    path("api/send-history", send_history, name="send_history"),
    path("api/home/stats", home_match_stats_api, name="home-match-stats"),
    path("api/analysis/stats", analysis_stats_api, name="analysis-stats"),
    # -------------------------------customer API-------------------------------
    path("api/customers", customers_api, name="customer-list"),
    path("api/customers/<int:customer_id>", customer_detail_api, name="customer-detail"),
    path("api/customers/<int:customer_id>/contract", customer_contract_upload, name="customer-contract-upload"),
    path("api/customers/card-ocr", customer_card_ocr_api, name="customer-card-ocr"),
    path("api/line/webhook", line_webhook_api, name="line-webhook"),
    # -------------------------------order API-------------------------------
    path("api/purchase-orders", purchase_orders_api, name="purchase-orders"),
    path("api/purchase-orders/<int:order_id>/update", purchase_order_update_api, name="purchase-order-update"),
    path("api/purchase-orders/<int:order_id>/pdf", purchase_order_pdf_api, name="purchase-order-pdf"),
    path("api/sales-orders", sales_orders_api, name="sales-orders"),
    path("api/sales-orders/<int:order_id>", sales_order_detail_api, name="sales-order-detail"),
    path("api/sales-orders/<int:order_id>/pdf", sales_order_pdf_api, name="sales-order-pdf"),
    path("api/pay-requests", pay_requests_api, name="pay-requests"),
    path("api/pay-requests/<int:pay_request_id>", pay_request_detail_api, name="pay-request-detail"),
    path("api/pay-requests/<int:pay_request_id>/update", pay_request_update_api, name="pay-request-update"),
    path("api/pay-requests/<int:pay_request_id>/pdf", pay_request_pdf_api, name="pay-request-pdf"),
    # -------------------------------permission UI-------------------------------

    # -------------------------------notification UI-------------------------------

    # -------------------------------permission API-------------------------------
    path("api/menus", menus_api, name="menu-list"),
    path("api/menus/<int:menu_id>", menu_detail_api, name="menu-detail"),
    path("api/roles", roles_api, name="role-list"),
    path("api/roles/<int:role_id>", role_detail_api, name="role-detail"),
    # -------------------------------system settings API-------------------------------
    path("api/mail-templates/<str:template_name>", mail_template_detail_api, name="mail-template-detail"),
    path("api/sys-settings/<str:section>", sys_settings_section_api, name="sys-settings-section"),
    path("api/sys-settings/business-email/test", sys_settings_gmail_test_api, name="sys-settings-gmail-test"),
    path("api/sys-settings/sendmsg/test", sys_settings_sendmsg_test_api, name="sys-settings-sendmsg-test"),
    path("api/sys-settings/sendmsg/receiver-test", sys_settings_sendmsg_receiver_test_api, name="sys-settings-sendmsg-receiver-test"),
    path("api/sys-settings/line-notify/test", sys_settings_line_notify_test_api, name="sys-settings-line-notify-test"),
    path("api/sys-settings/ai/test", sys_settings_ai_test_api, name="sys-settings-ai-test"),
    path("api/company-info", company_info_api, name="company-info"),
    path("api/company-info/seal", company_info_seal_api, name="company-info-seal"),
    path("api/sys-password-reset", sys_password_reset_api, name="sys-password-reset"),
    path("api/sys-tasks", sys_tasks_api, name="sys-tasks"),
    path("api/sys-tasks/logs", sys_task_logs_api, name="sys-task-logs"),
    path("api/time-to-save", time_to_save, name="time_to_save"),
    path("api/time-to-save-day", time_to_save_day, name="time_to_save"),
    path("api/time-to-clean", time_to_clean, name="time_to_clean"),
    path("api/time-to-backup", time_to_backup, name="time_to_backup"),
    path("api/time-to-hello", time_to_hello, name="time_to_hello"),
    path("api/time-to-sync-my-mails", time_to_sync_my_mails, name="time_to_sync_my_mails"),
    path("api/activation", activation_code_api, name="activation-code"),
    path("api/activation/status", activation_status_api, name="activation-status"),
    path("api/activation/validate", activation_validate_api, name="activation-validate"),
]
