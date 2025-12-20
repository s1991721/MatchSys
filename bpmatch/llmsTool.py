from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage


# ---------------------------
#  初始化 LLM（建议单例）
# ---------------------------
llm = ChatOllama(
    model="llama3.2:3b-instruct-q4_K_M",
    # model="llama3.1:8b-instruct-q4_K_M",
    # model="gpt-oss:20b",
    # model="phi3:mini",
    temperature=0,
)


# ---------------------------
#  分析邮件标题 返回邮件类型
# ---------------------------
def title_analysis(text: str) -> str:
    # 规则 A：出现这些关键词 → 优先判定为 0（求人）
    KEYWORDS_JOB = ["急募案件", "エンド直", "代替"]
    # 规则 B：出现这些关键词 → 优先判定为 1（求案件）
    KEYWORDS_PROJECT = ["歳", "人材", "要員", "社員", "フリーランス"]
    # 检查规则 A（求人）
    matched_job = [kw for kw in KEYWORDS_JOB if kw in text]
    if matched_job:
        print("匹配到【求人（0）】关键词：", matched_job)
        return 0

    # 检查规则 B（求案件）
    matched_project = [kw for kw in KEYWORDS_PROJECT if kw in text]
    if matched_project:
        print("匹配到【求案件（1）】关键词：", matched_project)
        return 1

    messages = [
        SystemMessage(
            content=(
                """
                你现在的任务是：只根据整封邮件的日文标题（subject）来判断这封邮件的类型，并输出一个固定整型标签。

                分类：
                ・0 = 求人：我这边有案件
                ・1 = 求案件：我这边有人
                ・-1 = 其他类型：非以上两种。

                判断要点：
                ・标题中主要在介绍案件，多数是 0（求人），例如：
                　「案件のご紹介」「案件」「エンジニア募集」「支援」「エンド直」「フルリモート」「急募案件」「技術者募集」等。
                ・标题中主要在介绍候補者，多数是 1（求案件），例如：
                　「弊社所属」「弊社のご紹介」「案件募集」「案件探してます」「実績」「人材」「稼働可能」「社員」「フリーランス」「歳」等。。

                关键词规则：
                ・包含「案件のご紹介」「案件」「エンジニア募集」「支援」「エンド直」「フルリモート」「急募案件」「技術者募集」时，优先判定为 0（求人）。
                ・包含「弊社所属」「弊社のご紹介」「案件募集」「案件探してます」「実績」「人材」「稼働可能」「社員」「フリーランス」「〇〇歳」「直個人」「1社下社員」时，优先判定为 1（求案件）。

                其他说明：
                1. 只看标题，不要臆测正文内容。
                2. 邮件标题是日文，你需要根据日文标题的含义进行判断。
                3. 必须只输出一个整数标签：0、1 或 -1，不要输出其它任何文字、符号或说明。
                4. 如果无法确定是「求人」还是「求案件」，默认输出 -1。"""
            )
        ),
        HumanMessage(content=text),
    ]

    ai_msg = llm.invoke(messages)
    return ai_msg.content.strip()


# ---------------------------
#  分析求人邮件内容 返回json
# ---------------------------
def qiuren_detail_analysis(text: str) -> str:
    messages = [
        SystemMessage(
            content=(
                """你是一个信息抽取模型。已知当前邮件类型为「求人」，即发件方这边有案件/项目/工作机会，希望寻找可以做这个案件的人、工程师或候选人。

                现在，请你根据整封日语邮件正文，抽取关键信息，只输出一个 JSON 对象，不包含任何额外文字或说明。

                JSON 对象包含字段：country、skills、price。

                字段规则：
                1. country：整数。0 表示此求人仅招日本籍，1 表示国籍不限。出现「外国籍不可」「日本国籍」则 country=0；出现「外国籍可」「非日本籍」则 country=1；若邮件中未提及国籍，则默认 country=1。
                2. skills：字符串数组。从邮件正文中识别技术相关关键词，全部转为小写并去重。常见技术词包括但不限于：java、vue、react、c#、c++、python、php、ruby、go、typescript、javascript、node、kotlin、swift、spring、.net、azure、aws、gcp、docker、kubernetes、oracle、sql、postgresql、mysql、sap、salesforce、laravel、django。若出现其他明显为技术名 / 框架名 / 云服务名，也一并加入 skills。若未识别到任何技术词，则 skills=[]。
                3. price：整数。从与报酬相关的描述中提取第一个数值，优先从包含「単価」「時給」「月給」「月額」「年収」「報酬」以及包含「円」「万円」「万」等金额表述的部分抽取。
                - 若金额以「万」或「万円」表示（如「60万円」「60万」），则输出对应的整数万数（例：60）。
                - 若金额以「円」表示或为纯数字（如「600000円」「600000」），则输出该数值本身（例：600000）。
                - 若存在多个金额，只取正文中最先出现的一个。
                - 若没有任何可识别的报酬或单价相关数值，则 price=0。

                输出格式要求：
                - 只输出 JSON 对象本身，例如：{"country":1,"skills":["java","aws"],"price":60}
                - 不要输出任何解释性文字、前后缀、markdown 代码块等。"""
            ),
        ),
        HumanMessage(content=text),
    ]
    ai_msg = llm.invoke(messages)
    return ai_msg.content.strip()


# ---------------------------
#  分析求案件邮件内容 返回json
# ---------------------------
def qiuanjian_detail_analysis(text: str) -> str:
    messages = [
        SystemMessage(
            content=(
                """你是一个信息抽取模型。已知当前邮件类型为「求案件」，即发件方这边有人 / 候选人 / 工程师 / 团队，希望寻找合适的案件 / 项目 / 职位 / 工作来对接。

                现在，请你根据整封日语邮件正文，抽取关键信息，只输出一个 JSON 对象，不包含任何额外文字或说明。

                JSON 对象包含字段：country, skills, price。

                字段规则：
                1. country：整数。0 表示求案件的技术者是日本籍，1 表示求案件的技术者是非日本籍。出现「日本籍」「日本国籍」则 country=0；若邮件中未提及国籍，则默认 country=1。
                2. skills：字符串数组。从邮件正文中识别技术相关关键词，全部转为小写并去重。常见技术词包括但不限于：java、vue、react、c#、c++、python、php、ruby、go、typescript、javascript、node、kotlin、swift、spring、.net、azure、aws、gcp、docker、kubernetes、oracle、sql、postgresql、mysql、sap、salesforce、laravel、django。若出现其他明显为技术名 / 框架名 / 云服务名，也一并加入 skills。若未识别到任何技术词，则 skills=[]。
                3. price：整数。从与报酬相关的描述中提取第一个数值，优先从包含「単価」「時給」「月給」「月額」「年収」「報酬」以及包含「円」「万円」「万」等金额表述的部分抽取。
                - 若金额以「万」或「万円」表示（如「60万円」「60万」），则输出对应的整数万数（例：60）。
                - 若金额以「円」表示或为纯数字（如「600000円」「600000」），则输出该数值本身（例：600000）。
                - 若存在多个金额，只取正文中最先出现的一个。
                - 若没有任何可识别的报酬或单价相关数值，则 price=0。

                输出格式要求：
                - 只输出 JSON 对象本身，例如：{"country":1,"skills":["java","aws"],"price":60}
                - 不要输出任何解释性文字、前后缀、markdown 代码块等。"""
            ),
        ),
        HumanMessage(content=text),
    ]
    ai_msg = llm.invoke(messages)
    return ai_msg.content.strip()


# -----------------------------
# 解析求人案件邮件内容，返回 JSON
# -----------------------------
def extract_qiuren_detail(text: str) -> str:
    messages = [
        SystemMessage(
            content=(
                """
                あなたは求人案件メールを解析する情報抽出エンジンです。

                以下のメール本文は、日本語で書かれた求人案件の内容です。
                本文から、明確に記載されている情報のみを抽出してください。
                
                【最重要ルール（厳守）】
                ・推測、補完、要約、言い換えは禁止
                ・本文に明確な記載が存在しない項目は必ず空値を返す
                ・文字列項目は空文字列 ""、配列項目は空配列 [] を返す
                ・日本語は原文のまま使用する
                ・案件情報と無関係な挨拶文、署名、注意書きは抽出対象外とする
                
                【出力制約（絶対遵守）】
                ・出力は JSON 1個のみとする
                ・JSON の前後に、説明文・注釈・理由・補足・挨拶・Markdown・コードブロック（```）を一切付けない
                ・JSON の後に 1 文字でも文字列を出力した場合は不正解
                ・「注:」「備考:」「理由:」「抽出できませんでした」等の説明文は禁止
                ・抽出できない理由は絶対に書かない（空値で表現する）
                
                【出力フォーマット（キー・型を厳守）】
                {
                  "project_name": "",
                  "project_detail": "",
                  "requirement": "",
                  "skills_must": [],
                  "skills_can": [],
                  "remark": ""
                }
                
                【型ルール（絶対遵守）】
                ・project_name / project_detail / requirement / remark は必ず文字列型
                ・skills_must / skills_can は必ず文字列の配列（array of string）
                ・null、未定義、キー省略は禁止
                
                【各項目の定義】
                - project_name：
                本文中に「【案件名】」という見出しが明確に存在する場合のみ抽出する。
                存在しない場合は ""。
                
                - project_detail：
                本文中に「【業務概要】」「業務内容」などの見出しが明確に存在する場合のみ抽出する。
                存在しない場合は ""。
                
                - requirement：
                本文中に「【条件】」「【応募条件】」などの見出しが明確に存在する場合のみ抽出する。
                存在しない場合は ""。
                
                - skills_must：
                「【必須スキル】」に記載されている各スキル名のみを1項目ずつ配列として抽出する。
                経験年数、記号、補足説明は含めない。
                存在しない場合は []。
                
                - skills_can：
                「【尚可スキル】」に記載されている各スキル名のみを1項目ずつ配列として抽出する。
                経験年数、記号、補足説明は含めない。
                存在しない場合は []。
                
                - remark：
                「【備考】」「期間」「開始日」などが明確に存在する場合のみ抽出する。
                存在しない場合は ""。

                """
            )
        ),
        HumanMessage(content=text),
    ]

    ai_msg = llm.invoke(messages)
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
