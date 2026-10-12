from django.urls import path
from . import views, candidate, media

# 企业入口使用 session 身份；internal 路由仅供持有服务密钥的后台调用。
urlpatterns = [
    path("candidate/health", candidate.health),
    path("candidate/recording/chunk", media.upload),
    path("candidate/recording/seal", media.seal),
    path("candidate/abort", candidate.abort),
    path("candidate/verify", candidate.verify),
    path("candidate/start", candidate.start),
    path("candidate/client-secret", candidate.client_secret),
    path("candidate/heartbeat", candidate.heartbeat),
    path("candidate/finish", candidate.finish),
    path("candidate/evaluation", candidate.evaluation),
]
for route, view, name in [
    ("interviews", views.interviews, "interviews"),
    ("interviews/<int:pk>", views.interview_detail, "interview_detail"),
    ("interviews/<int:pk>/recording", media.recording, "recording"),
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
