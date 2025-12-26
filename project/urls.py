"""
URL configuration for project project.

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

from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

from bpmatch.views import (
    messages,
    persons,
    log_job_click,
    extract_qiuren_detail,
    send_mail,
    send_history,
)
from attendance.views import (
    attendance_punch_api,
    attendance_record_edit_api,
    attendance_record_today_api,
    attendance_detail_api,
    attendance_summary_api,
    my_attendance_summary_api,
    my_attendance_detail_api,
)
from employee.views import (
    change_password_api,
    employee_detail_api,
    employees_api,
    login_api,
    logout_api,
    technician_detail_api,
    technician_ss_download,
    technician_ss_upload,
    technicians_api,
)
from customer.views import (
    employee_names_api,
    customers_api,
    customer_detail_api,
    customer_contract_upload,
)
from order.views import (
    purchase_orders_api,
    purchase_order_detail_api,
    sales_orders_api,
    sales_order_detail_api,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(url="/index.html", permanent=False)),
    path("index.html", TemplateView.as_view(template_name="index.html")),
    path("home.html", TemplateView.as_view(template_name="home.html")),
    path("attendance.html", TemplateView.as_view(template_name="attendance.html")),
    path("myattendance.html", TemplateView.as_view(template_name="myattendance.html")),
    path("match.html", TemplateView.as_view(template_name="match.html")),
    path("people.html", TemplateView.as_view(template_name="people.html")),
    path("personnel.html", TemplateView.as_view(template_name="personnel.html")),
    path("customer.html", TemplateView.as_view(template_name="customer.html")),
    path("profile.html", TemplateView.as_view(template_name="profile.html")),
    path("qiuanjian.html", TemplateView.as_view(template_name="qiuanjian.html")),
    path("qiuren.html", TemplateView.as_view(template_name="qiuren.html")),
    path("order.html", TemplateView.as_view(template_name="order.html")),
    path("pay_request.html", TemplateView.as_view(template_name="pay_request.html")),
    path("songxin.html", TemplateView.as_view(template_name="songxin.html")),
    path("songxinhistory.html", TemplateView.as_view(template_name="songxinhistory.html")),
    path("permission.html", TemplateView.as_view(template_name="permission.html")),
    path("notification.html", TemplateView.as_view(template_name="notification.html")),
    path("login.html", TemplateView.as_view(template_name="login.html")),
    path("common.css", TemplateView.as_view(template_name="common.css", content_type="text/css")),
    path("common.js", TemplateView.as_view(template_name="common.js", content_type="application/javascript")),
    path("api/employees/names", employee_names_api, name="employee-names"),
    path("api/customers", customers_api, name="customer-list"),
    path("api/customers/<int:customer_id>", customer_detail_api, name="customer-detail"),
    path("api/customers/<int:customer_id>/contract", customer_contract_upload, name="customer-contract-upload"),
    path("api/purchase-orders", purchase_orders_api, name="purchase-orders"),
    path("api/purchase-orders/<int:order_id>", purchase_order_detail_api, name="purchase-order-detail"),
    path("api/sales-orders", sales_orders_api, name="sales-orders"),
    path("api/sales-orders/<int:order_id>", sales_order_detail_api, name="sales-order-detail"),
    path("api/login", login_api, name="employee-login"),
    path("api/logout", logout_api, name="employee-logout"),
    path("api/change-password", change_password_api, name="employee-change-password"),
    path("api/employees", employees_api, name="employee-list"),
    path("api/employees/<int:employee_id>", employee_detail_api, name="employee-detail"),
    path("api/technicians", technicians_api, name="technician-list"),
    path("api/technicians/<int:employee_id>", technician_detail_api, name="technician-detail"),
    path("api/technicians/<int:employee_id>/ss", technician_ss_upload, name="technician-ss-upload"),
    path("api/ss/<path:path>", technician_ss_download, name="technician-ss-download"),
    path("api/attendance/punch", attendance_punch_api, name="attendance-punch"),
    path("api/attendance/record/edit", attendance_record_edit_api, name="attendance-record-edit"),
    path("api/attendance/record/today", attendance_record_today_api, name="attendance-record-today"),
    path("api/attendance/summary", attendance_summary_api, name="attendance-summary"),
    path("api/attendance/<int:employee_id>/detail", attendance_detail_api, name="attendance-detail"),
    path("api/my-attendance-summary", my_attendance_summary_api, name="my-attendance-summary"),
    path("api/my-attendance-detail", my_attendance_detail_api, name="my-attendance-detail"),
    path("messages", messages),
    path("persons", persons),
    path("job-click", log_job_click),
    path("extract-qiuren-detail", extract_qiuren_detail),
    path("send-mail", send_mail),
    path("send-history", send_history),
]
