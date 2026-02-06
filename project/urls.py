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
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.cache import cache_control
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
    mail_technician_search_api,
    extract_project_detail,
    extract_technician_detail,
    send_mail,
    send_history,
)
from data_analysis.views import analysis_stats_api, home_match_stats_api
from customer.views import (
    employee_names_api,
    customers_api,
    customer_detail_api,
    customer_contract_upload,
)
from employee.views import (
    change_password_api,
    employee_detail_api,
    employee_departments_api,
    employee_permission_api,
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
from order.views import (
    purchase_orders_api,
    purchase_order_detail_api,
    sales_orders_api,
    sales_order_detail_api,
)
from permission.views import (
    menus_api,
    menu_detail_api,
    roles_api,
    role_detail_api,
)
from settings.views import (
    sys_settings_ai_test_api,
    sys_settings_gmail_test_api,
    sys_settings_sendmsg_test_api,
    sys_password_reset_api,
    sys_settings_section_api,
    sys_tasks_api,
    time_to_save,
    time_to_clean,
    time_to_backup,
    time_to_hello,
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
    path("qiuren.html", TemplateView.as_view(template_name="frontend/qiuren.html")),
    path("songxin.html", TemplateView.as_view(template_name="frontend/songxin.html")),
    path("songxinhistory.html", TemplateView.as_view(template_name="frontend/songxinhistory.html")),
    # -------------------------------customer UI-------------------------------
    path("customer.html", TemplateView.as_view(template_name="frontend/customer.html")),
    # -------------------------------order UI-------------------------------
    path("order.html", TemplateView.as_view(template_name="frontend/order.html")),
    path("pay_request.html", TemplateView.as_view(template_name="frontend/pay_request.html")),
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
        "i18n.js",
        cache_static_asset(TemplateView.as_view(template_name="frontend/i18n.js", content_type="application/javascript")),
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
    path("api/employees/<int:employee_id>/permission", employee_permission_api, name="employee-permission"),
    path("api/logout", logout_api, name="employee-logout"),
    path("api/change-password", change_password_api, name="employee-change-password"),
    path("api/employees", employees_api, name="employee-list"),
    path("api/employees/departments", employee_departments_api, name="employee-departments"),
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
    path("api/mail-technicians/search", mail_technician_search_api, name="mail-technicians-search"),
    path("api/extract-project-detail", extract_project_detail, name="extract_project_detail"),
    path("api/extract-technician-detail", extract_technician_detail, name="extract_technician_detail"),
    path("api/send-mail", send_mail, name="send_mail"),
    path("api/send-history", send_history, name="send_history"),
    path("api/home/stats", home_match_stats_api, name="home-match-stats"),
    path("api/analysis/stats", analysis_stats_api, name="analysis-stats"),
    # -------------------------------customer API-------------------------------
    path("api/customers", customers_api, name="customer-list"),
    path("api/customers/<int:customer_id>", customer_detail_api, name="customer-detail"),
    path("api/customers/<int:customer_id>/contract", customer_contract_upload, name="customer-contract-upload"),
    # -------------------------------order API-------------------------------
    path("api/purchase-orders", purchase_orders_api, name="purchase-orders"),
    path("api/purchase-orders/<int:order_id>", purchase_order_detail_api, name="purchase-order-detail"),
    path("api/sales-orders", sales_orders_api, name="sales-orders"),
    path("api/sales-orders/<int:order_id>", sales_order_detail_api, name="sales-order-detail"),
    # -------------------------------permission UI-------------------------------

    # -------------------------------notification UI-------------------------------

    # -------------------------------permission API-------------------------------
    path("api/menus", menus_api, name="menu-list"),
    path("api/menus/<int:menu_id>", menu_detail_api, name="menu-detail"),
    path("api/roles", roles_api, name="role-list"),
    path("api/roles/<int:role_id>", role_detail_api, name="role-detail"),
    # -------------------------------system settings API-------------------------------
    path("api/sys-settings/<str:section>", sys_settings_section_api, name="sys-settings-section"),
    path("api/sys-settings/business-email/test", sys_settings_gmail_test_api, name="sys-settings-gmail-test"),
    path("api/sys-settings/sendmsg/test", sys_settings_sendmsg_test_api, name="sys-settings-sendmsg-test"),
    path("api/sys-settings/ai/test", sys_settings_ai_test_api, name="sys-settings-ai-test"),
    path("api/sys-password-reset", sys_password_reset_api, name="sys-password-reset"),
    path("api/sys-tasks", sys_tasks_api, name="sys-tasks"),
    path("api/time-to-save", time_to_save, name="time_to_save"),
    path("api/time-to-claen", time_to_clean, name="time_to_clean"),
    path("api/time-to-backup", time_to_backup, name="time_to_backup"),
    path("api/time-to-hello", time_to_hello, name="time_to_hello"),
]
