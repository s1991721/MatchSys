import json
import os
import ssl
import subprocess
import urllib

from project.api import api_error, api_success


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
    ollama_host = os.environ.get("OLLAMA_HOST", "127.0.0.1").strip()
    if ollama_host:
        try:
            url = ollama_host.rstrip("/") + "/api/tags"
            with urllib.request.urlopen(url, timeout=10) as resp:
                if resp.status != 200:
                    return api_error("Ollama 接口返回失败")
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")
            return api_error(detail or "Ollama 接口返回失败")
        except urllib.error.URLError as exc:
            return api_error(str(exc.reason) or "Ollama 接口请求失败")
        except (ValueError, TypeError):
            return api_error("Ollama 接口返回无效数据")
        models = {
            (item or {}).get("name")
            for item in (payload or {}).get("models", [])
        }
        models.discard(None)
        if model_name not in models:
            return api_error("模型不存在，请先下载。")
        return api_success()

    try:
        list_result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        return api_error("Ollama 未安装或命令不可用")
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "Ollama 执行失败").strip()
        return api_error(message)
    models = set()
    for line in (list_result.stdout or "").splitlines():
        line = line.strip()
        if not line or line.lower().startswith("name"):
            continue
        model = line.split()[0]
        if model:
            models.add(model)
    if model_name not in models:
        return api_error("模型不存在，请先下载。")

    return api_success()


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
                return api_error("OpenAI 接口返回失败")
            return api_success()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        return api_error(detail or "OpenAI 接口返回失败")
    except urllib.error.URLError as exc:
        return api_error(str(exc.reason) or "OpenAI 接口请求失败")
