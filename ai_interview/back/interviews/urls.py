from django.urls import path
from . import views

# 企业入口使用 session 身份；internal 路由仅供持有服务密钥的后台调用。
urlpatterns = []
for route, view, name in [
    ("interviews", views.interviews, "interviews"),
    ("interviews/<int:pk>", views.interview_detail, "interview_detail"),
    ("interviews/<int:pk>/invitation", views.invitation_rotate, "invitation_rotate"),
    ("reports", views.reports, "reports"),
    ("reports/<int:pk>", views.report_detail, "report_detail"),
    ("reports/<int:pk>/read", views.report_read, "report_read"),
    ("quota", views.quota, "quota"),
    ("dashboard", views.dashboard, "dashboard"),
    ("internal/interviews/<int:pk>", views.runtime_update, "runtime_update"),
    ("internal/interviews/<int:pk>/report", views.report_write, "report_write"),
]:
    # 同时接受有、无末尾斜杠，避免 POST/PATCH 依赖重定向处理请求体。
    urlpatterns.extend([path(route, view, name=name), path(route + "/", view)])
