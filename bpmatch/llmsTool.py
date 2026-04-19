import json
import os
import ssl
import urllib.request

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from ai.classifier.priority_classification import predict_subject
from settings.models import SysSettings

# ---------------------------
#  LLM Router (local / cloud)
# ---------------------------
DEFAULT_LOCAL_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0
DEFAULT_TIMEOUT = 600
DEFAULT_OPENAI_URL = "https://api.openai.com/v1/chat/completions"

_LLM_CACHE = {"config": None, "client": None}


class _SimpleMessage:
    def __init__(self, content: str):
        self.content = content


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


def _load_ai_settings():
    record = SysSettings.objects.filter(name="ai", deleted_at__isnull=True).first()
    if not record or not isinstance(record.settings, dict):
        return {"model_type": "local", "model_name": "", "api_key": ""}
    return record.settings


def _to_openai_messages(messages):
    converted = []
    for msg in messages:
        role = getattr(msg, "type", None) or "user"
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        converted.append({"role": role, "content": msg.content})
    return converted


class CloudChatOpenAI:
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def invoke(self, messages):
        payload = {
            "model": self.model,
            "messages": _to_openai_messages(messages),
            "temperature": DEFAULT_TEMPERATURE,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(
                req,
                timeout=DEFAULT_TIMEOUT,
                context=_build_ssl_context(),
        ) as resp:
            raw = resp.read().decode("utf-8", "ignore")
        parsed = json.loads(raw or "{}")
        if "error" in parsed:
            message = (parsed.get("error") or {}).get("message") or "OpenAI error"
            raise RuntimeError(message)
        content = ""
        choices = parsed.get("choices") or []
        if choices:
            content = ((choices[0] or {}).get("message") or {}).get("content") or ""
        return _SimpleMessage(content=content)


def _get_llm():
    settings_payload = _load_ai_settings()
    model_type = settings_payload.get("model_type") or "local"
    model_name = (settings_payload.get("model_name") or "").strip()
    api_key = (settings_payload.get("api_key") or "").strip()

    ollama_host = os.environ.get("OLLAMA_HOST", "127.0.0.1").strip() or None
    openai_url = (os.environ.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_URL).strip()

    cache_key = (model_type, model_name, api_key, ollama_host, openai_url)
    if _LLM_CACHE["config"] == cache_key and _LLM_CACHE["client"] is not None:
        return _LLM_CACHE["client"]

    if model_type == "cloud":
        if not model_name or not api_key:
            raise RuntimeError("Cloud model requires model_name and api_key")
        client = CloudChatOpenAI(model=model_name, api_key=api_key, base_url=openai_url)
    else:
        client = ChatOllama(
            model=model_name or DEFAULT_LOCAL_MODEL,
            temperature=DEFAULT_TEMPERATURE,
            base_url=ollama_host,
            client_kwargs={"timeout": DEFAULT_TIMEOUT},
        )

    _LLM_CACHE["config"] = cache_key
    _LLM_CACHE["client"] = client
    return client


# ---------------------------
#  分析邮件标题 返回邮件类型
# ---------------------------
def title_analysis(text: str) -> str:
    label = predict_subject(text)
    print(f"Subject:{text}  label:{label}")
    return str(label)


# ---------------------------
#  分析求人邮件内容 返回json
# ---------------------------
def qiuren_detail_analysis(text: str) -> str:
    messages = [
        SystemMessage(
            content=(
                """
                あなたは「情報抽出モデル」です。
                対象は【日本語で書かれた「求案件（人材側）」のメール本文】です。
                
                以下のルールに従い、JSON オブジェクトのみを出力してください。
                説明文、理由、注釈、コードブロック、見出し、箇条書き、改行を含む補足文は一切出力してはいけません。
                出力は必ず 1 行の JSON のみとしてください。
                
                抽出フィールドは country、skills、price のみです。
                この 3 フィールド以外を出力してはいけません。
                
                ====================
                【共通ルール】
                - 推測・補完・一般的判断は禁止
                - 本文中に文字として存在しない情報は使用禁止
                - 出力形式違反は重大な誤りとみなす
                ====================
                
                【1. country（整数・必須）】
                
                country は「抽出」ではなく「必須分類項目」である。
                
                判定ルール：
                - 0：日本国籍限定が明確に記載されている場合  
                  （例：日本国籍のみ、外国籍不可、日本人限定）
                - 1：国籍不問が明確に記載されている場合  
                  （例：国籍不問、外国籍可、非日本籍可）
                - 1：本文中に国籍条件の明示がない、または判断できない場合
                
                補足規則：
                - 国籍に関する記載が一切ない場合も country = 1
                - 判断不能・不明・記載なしの場合も country = 1
                
                出力制約：
                - country は必ず整数で出力すること
                - 出力可能な値は 0 または 1 のみ
                - null、未定義、空は禁止
                
                --------------------
                
                【2. skills（文字列配列）】
                本文中に【文字として明示的に出現している】技術名のみを抽出する。
                
                ルール：
                - プログラミング言語、フレームワーク、クラウド名などの固有技術名のみ
                - 「等」「など」「を中心とした」からの補完は禁止
                - 技術エコシステムの連想は禁止（例：Java → Spring）
                - 小文字の英語表記に正規化し、重複を除去
                
                以下の語は抽出禁止：
                業務系、Web系、基盤系、設計、開発、保守、経験、スキル、SE、PG
                
                該当なしの場合は空配列 [] を返す。
                
                --------------------
                
                【3. price（整数）】
                報酬・単価として【明確に確定している金額】のみを抽出する。
                
                条件：
                - 「単価」「月額」「時給」「年収」「報酬」「円」「万円」「万」
                  のいずれかと同一文または直近文に出現している数値のみ対象
                - 本文中で最初に出現する確定金額を抽出する
                
                金額形式：
                - 「60万」「60万円」→ 60
                - 「600000円」→ 600000
                
                以下の場合は必ず price = 0：
                - 応相談、未定、スキル見合い、前後、程度
                - 金額が範囲表現（例：60〜80万、〜90万）
                - 人数、期間、稼働率、年齢など金額以外の数値
                
                --------------------
                
                【出力例】
                {"country":2,"skills":["java","aws"],"price":60}
                """
            ),
        ),
        HumanMessage(content=text),
    ]
    ai_msg = _get_llm().invoke(messages)
    return ai_msg.content.strip()


# ---------------------------
#  分析求案件邮件内容 返回json
# ---------------------------
def qiuanjian_detail_analysis(text: str) -> str:
    messages = [
        SystemMessage(
            content=(
                """
                あなたは「情報抽出モデル」です。
                対象は【日本語で書かれた「求案件（人材側）」のメール本文】です。
                
                以下のルールに従い、JSON オブジェクトのみを出力してください。
                説明文、理由、注釈、コードブロック、見出し、箇条書き、改行を含む補足文は一切出力してはいけません。
                出力は必ず 1 行の JSON のみとしてください。
                
                抽出フィールドは country、skills、price のみです。
                この 3 フィールド以外を出力してはいけません。
                
                ====================
                【共通ルール】
                - 推測・補完・一般的判断は禁止
                - 本文中に文字として存在しない情報は使用禁止
                - 出力形式違反は重大な誤りとみなす
                ====================
                
                【1. country（整数・必須）】
                
                country は「抽出」ではなく「必須分類項目」である。
                
                判定ルール：
                - 本文中に、対象者が「日本籍」「日本国籍」「日本人」であると
                  明確に記載されている場合 → country = 0
                - 上記以外のすべての場合 → country = 1
                
                補足規則：
                - 国籍に関する記載が一切ない場合も country = 1
                - 判断不能・不明・記載なしの場合も country = 1
                
                出力制約：
                - country は必ず整数で出力すること
                - 出力可能な値は 0 または 1 のみ
                - null、未定義、空は禁止
                
                【2. skills（文字列配列・必須）】
                
                本文中に【文字として明示的に出現している】技術名のみを抽出する。
                推測は禁止。
                
                抽出方法：
                A) 以下のラベルが存在する場合、その直後から技術名を抽出：
                - スキル：
                - 主なスキル：
                - 技術：
                - 言語：
                - 環境：
                - 使用技術：
                - 経験技術：
                - 開発環境：
                
                B) 本文全体から、以下の技術キーワードに一致する語を抽出
                （大小文字・全角半角は正規化後に一致。部分一致可）
                
                技術キーワード一覧：
                java, vue, vue.js, react, react.js, next.js, nuxt, c#, c++, python, php, ruby, go,
                typescript, javascript, node, node.js, kotlin, swift, spring, .net,
                azure, aws, gcp, docker, kubernetes, oracle, sql, postgresql, postgres, mysql,
                sap, salesforce, laravel, django, fastapi, flask, git, linux, html, css
                
                C) A と B で 1 件も抽出できない場合のみ、
                本文中に出現する英字開始の技術名らしきトークンを最大 5 件抽出する。
                （英数字および . + # - を含んでよい）
                
                正規化ルール：
                - すべて小文字に正規化
                - 重複は除去
                
                除外：
                - 業務系、web系、設計、開発、保守、経験、スキル、se、pg などは抽出禁止
                - 本文に存在しない技術名の連想は禁止
                
                出力制約：
                - skills は必ず配列で出力すること
                - null、未定義は禁止
                - 該当なしの場合は [] を出力すること
                
                【3. price（整数・必須）】
                
                本文中に【明確に希望・提示されている金額】のみを抽出する。
                
                対象条件：
                - 以下の語と同一文または直近文に出現する数値のみ対象：
                  希望単価、希望、単価、月額、時給、年収、円、万円、万
                
                形式：
                - 「70万」「70万円」→ 70
                - 「700000円」→ 700000
                
                必ず price = 0 とする条件：
                - 応相談、未定、相談可
                - 範囲表現（例：60〜80万、〜90万）
                - 過去案件・実績として記載された金額
                - 人数、期間、年齢など金額以外の数値
                - 金額が一切記載されていない場合
                
                出力制約：
                - price は必ず整数で出力すること
                - null、未定義は禁止
                
                ====================
                【最終出力制約（最重要）】
                
                - 出力は必ず 1 行の JSON のみ
                - ```json``` などのコードブロックは禁止
                - 説明文・確認文・チェック結果を一切出力してはいけない
                
                出力例：
                {"country":1,"skills":["java","aws"],"price":70}

                """
            ),
        ),
        HumanMessage(content=text),
    ]
    ai_msg = _get_llm().invoke(messages)
    return ai_msg.content.strip()


# -----------------------------
# 解析求人案件邮件内容，返回 JSON
# -----------------------------
def extract_qiuren_detail(text: str) -> str:
    messages = [
        SystemMessage(
            content=(
                """
                あなたは求人案件メールを解析する「情報抽出エンジン」です。
                対象は【日本語で書かれた求人案件メール本文】のみです。
                
                本文中に【完全一致、または明確に判定可能な見出し直下】に
                記載されている情報のみを抽出してください。
                
                推測・補完・要約・言い換え・一般化は禁止します。
                
                ====================
                【最重要ルール（厳守）】
                ・本文に明確な記載が存在しない項目は必ず空値を返す
                ・空値の表現は以下に従う：
                  - 文字列項目 → ""
                  - 配列項目 → []
                ・記載されていない情報を作り出さない
                ・抽出できない理由は一切書かない
                ・案件内容と無関係な挨拶文、署名、注意書きは抽出対象外
                ====================
                
                【出力制約（絶対遵守）】
                ・出力は JSON オブジェクト 1 個のみ
                ・JSON の前後にいかなる文字も出力しない
                ・Markdown、コードブロック（```）は禁止
                ・null、キー省略は禁止
                
                【出力フォーマット（キー・型固定）】
                {
                  "project_name": "",
                  "project_detail": "",
                  "requirement": "",
                  "skills_must": [],
                  "skills_can": [],
                  "remark": ""
                }
                
                【型ルール】
                ・project_name / project_detail / requirement / remark は文字列
                ・skills_must / skills_can は文字列配列（array of string）
                
                ====================
                【抽出ルール（項目別）】
                ====================
                
                ■ project_name
                以下の見出しが【単独行】として完全一致で存在する場合のみ抽出する：
                - 【案件名】
                - 案件名：
                
                該当見出し直下の 1 行のみを値とする。
                存在しない場合は ""。
                
                --------------------
                
                ■ project_detail
                以下の見出しが【単独行】として存在する場合のみ抽出する：
                - 【業務概要】
                - 【業務内容】
                
                見出し直下から、次の見出し行が現れる直前までを値とする。
                存在しない場合は ""。
                
                --------------------
                
                ■ requirement
                以下の見出しが【単独行】として存在する場合のみ抽出する：
                - 【条件】
                - 【応募条件】
                
                見出し直下から、次の見出し行が現れる直前までを値とする。
                存在しない場合は ""。
                
                --------------------
                
                ■ skills_must
                以下の見出しが【単独行】として存在する場合のみ抽出する：
                - 【必須スキル】
                
                見出し直下の各行から、
                【技術名のみ】を 1 行につき 1 要素として配列に格納する。
                
                抽出ルール：
                ・記号（・、-、※ 等）は除去
                ・括弧内、年数、補足説明は除去
                ・技術名として判定できる語のみ残す
                
                存在しない場合は []。
                
                --------------------
                
                ■ skills_can
                以下の見出しが【単独行】として存在する場合のみ抽出する：
                - 【尚可スキル】
                
                抽出ルールは skills_must と同一。
                存在しない場合は []。
                
                --------------------
                
                ■ remark
                以下の見出しが【単独行】として存在する場合のみ抽出する：
                - 【備考】
                
                見出し直下から、次の見出し行が現れる直前までを値とする。
                存在しない場合は ""。
                """
            )
        ),
        HumanMessage(content=text),
    ]

    ai_msg = _get_llm().invoke(messages)
    return ai_msg.content.strip()


# ---------------------------
#  主运行入口
# ---------------------------
if __name__ == "__main__":
    print("\n=== Running Translation Tests ===\n")
    print(
        title_analysis(
            "【1社下社員】即日/33歳/フルリモート/フロントエンド,UI,TypeScript,vue,React,AWS,API/85万/谷塚"
        )
    )
    print("=== All tests completed ===")
