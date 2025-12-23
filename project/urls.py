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
from attendance.views import attendance_punch_api, attendance_record_today_api
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
    path("profile.html", TemplateView.as_view(template_name="profile.html")),
    path("qiuanjian.html", TemplateView.as_view(template_name="qiuanjian.html")),
    path("qiuren.html", TemplateView.as_view(template_name="qiuren.html")),
    path("songxin.html", TemplateView.as_view(template_name="songxin.html")),
    path("songxinhistory.html", TemplateView.as_view(template_name="songxinhistory.html")),
    path("login.html", TemplateView.as_view(template_name="login.html")),
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
    path("api/attendance/record/today", attendance_record_today_api, name="attendance-record-today"),
    path("messages", messages),
    path("persons", persons),
    path("job-click", log_job_click),
    path("extract-qiuren-detail", extract_qiuren_detail),
    path("send-mail", send_mail),
    path("send-history", send_history),
]
