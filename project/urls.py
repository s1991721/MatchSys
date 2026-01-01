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
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from django.views.static import serve as static_serve

from attendance.views import (
    attendance_punch_api,
    attendance_record_edit_api,
    attendance_record_today_api,
    attendance_detail_api,
    attendance_summary_api,
    my_attendance_summary_api,
    my_attendance_detail_api,
)
from bpmatch.views import (
    messages,
    persons,
    log_job_click,
    extract_qiuren_detail,
    send_mail,
    send_history,
)
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
    login_api,
    logout_api,
    technician_detail_api,
    technician_ss_download,
    technician_ss_upload,
    technicians_api,
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

custom_404 = TemplateView.as_view(template_name="404.html")
handler404 = "project.urls.custom_404"

urlpatterns = [
    # ###################################-Front End-###################################
    path("", RedirectView.as_view(url="/index.html", permanent=False)),
    path("index.html", TemplateView.as_view(template_name="index.html")),
    path("home.html", TemplateView.as_view(template_name="home.html")),

    # -------------------------------employee UI-------------------------------
    path("login.html", TemplateView.as_view(template_name="login.html")),
    path("profile.html", TemplateView.as_view(template_name="profile.html")),
    path("personnel.html", TemplateView.as_view(template_name="personnel.html")),
    path("people.html", TemplateView.as_view(template_name="people.html")),
    # -------------------------------attendance UI-------------------------------
    path("attendance.html", TemplateView.as_view(template_name="attendance.html")),
    path("myattendance.html", TemplateView.as_view(template_name="myattendance.html")),
    # -------------------------------bpmatch UI-------------------------------
    path("bpmatch.html", TemplateView.as_view(template_name="bpmatch.html")),
    path("match.html", TemplateView.as_view(template_name="match.html")),
    path("qiuren.html", TemplateView.as_view(template_name="qiuren.html")),
    path("songxin.html", TemplateView.as_view(template_name="songxin.html")),
    path("songxinhistory.html", TemplateView.as_view(template_name="songxinhistory.html")),
    # -------------------------------customer UI-------------------------------
    path("customer.html", TemplateView.as_view(template_name="customer.html")),
    # -------------------------------order UI-------------------------------
    path("order.html", TemplateView.as_view(template_name="order.html")),
    path("pay_request.html", TemplateView.as_view(template_name="pay_request.html")),
    # -------------------------------permission UI-------------------------------
    path("permission.html", TemplateView.as_view(template_name="permission.html")),
    # -------------------------------notification UI-------------------------------
    path("notification.html", TemplateView.as_view(template_name="notification.html")),
    path("analysis.html", TemplateView.as_view(template_name="analysis.html")),
    path("system_settings.html", TemplateView.as_view(template_name="system_settings.html")),
    # -------------------------------common-------------------------------
    path("common.css", TemplateView.as_view(template_name="common.css", content_type="text/css")),
    path("components.css", TemplateView.as_view(template_name="components.css", content_type="text/css")),
    path("common.js", TemplateView.as_view(template_name="common.js", content_type="application/javascript")),
    path("i18n.js", TemplateView.as_view(template_name="i18n.js", content_type="application/javascript")),
    path("favicon.png", static_serve, {"document_root": settings.BASE_DIR, "path": "favicon.png"}),
    path("favicon-32.png", static_serve, {"document_root": settings.BASE_DIR, "path": "favicon-32.png"}),
    path("favicon.ico", RedirectView.as_view(url="/favicon-32.png", permanent=False)),

    # ###################################-API-###################################
    # -------------------------------employee API-------------------------------
    path("api/login", login_api, name="employee-login"),
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
    path("api/my-attendance-summary", my_attendance_summary_api, name="my-attendance-summary"),
    path("api/my-attendance-detail", my_attendance_detail_api, name="my-attendance-detail"),
    # -------------------------------bpmatch API-------------------------------
    path("messages", messages),
    path("persons", persons),
    path("job-click", log_job_click),
    path("extract-qiuren-detail", extract_qiuren_detail),
    path("send-mail", send_mail),
    path("send-history", send_history),
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
]
