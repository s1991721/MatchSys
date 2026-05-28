import json
import os
import ssl
import urllib.error
import urllib.request

from project.api import api_error, api_success
from project.error_codes import ErrorCode


def _build_ssl_context():
    verify = os.environ.get("OPENAI_SSL_VERIFY", "1").strip().lower()
    if verify in {"0", "false", "no"}:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


# 检测本地模型
def check_local_model(model_name):
    try:
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
        req = urllib.request.Request(
            ollama_host.rstrip("/") + "/api/generate",
            data=json.dumps({"model": model_name, "prompt": "hi"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            if resp.status != 200:
                return api_error(ErrorCode.EXTERNAL_LLM, "模型连接失败")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return api_error(ErrorCode.EXTERNAL_LLM, "模型连接失败")

    return api_success(
        data={
            "model_name": model_name,
            "model_type": "local",
            "status": "ready",
        }
    )


# 检测云端模型
def check_cloud_model(model_name, api_key):
    try:
        request_payload = json.dumps(
            {
                "model": model_name,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=request_payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(
            req,
            timeout=20,
            context=_build_ssl_context(),
        ) as resp:
            if resp.status != 200:
                return api_error(ErrorCode.EXTERNAL_OPENAI_RESPONSE_FAILED, "OpenAI 接口返回失败")
            return api_success()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        return api_error(ErrorCode.EXTERNAL_OPENAI_RESPONSE_FAILED, detail or "OpenAI 接口返回失败")
    except urllib.error.URLError as exc:
        return api_error(ErrorCode.EXTERNAL_OPENAI_REQUEST_FAILED, str(exc.reason) or "OpenAI 接口请求失败")
