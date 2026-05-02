import json
import os
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

# ========= 配置区（你只需要改这里） =========

INPUT_CSV = "dataset_llm_v1.csv"
OUTPUT_DIR = "data"

ID_COL = "id"
TEXT_COL = "Body"
LABEL_COL = "label"
AI_RESULT_COL = "ai_result"

# label 映射（可改）
LABEL_MAP = {
    0: "求人",
    1: "求案件"
}

SYSTEM_PROMPT = "日本語メールから country, skills, price を抽出し、JSONのみ出力せよ。"

TEST_SIZE = 0.1
RANDOM_SEED = 42


# ==========================================

# 转为json类型
def safe_json_load(s):
    try:
        return json.loads(s)
    except:
        return None


# skills格式化
def normalize_skills(skills):
    if isinstance(skills, list):
        return list({str(s).lower().strip() for s in skills if str(s).strip()})
    elif isinstance(skills, str):
        return list({s.strip().lower() for s in skills.split(",") if s.strip()})
    return []


# 创建样本数据
def build_sample(row):
    id = str(row.get(ID_COL, "")).strip()
    body = str(row.get(TEXT_COL, "")).strip()
    label = row.get(LABEL_COL, None)
    ai_result_raw = row.get(AI_RESULT_COL, "")

    if pd.isna(ai_result_raw) or str(ai_result_raw).strip() == "":
        return None

    result = safe_json_load(ai_result_raw)
    if not result:
        print(f"json格式错误{id}")
        return None

    # 必须字段
    if "country" not in result or "skills" not in result or "price" not in result:
        print("缺失字段")
        return None

    try:
        country = int(result["country"])
        price = int(result["price"])
        skills = normalize_skills(result["skills"])
    except:
        return None

    task_type = LABEL_MAP.get(label, "未知")

    assistant_json = {
        "country": country,
        "skills": skills,
        "price": price
    }

    return {
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": f"タスク: {task_type}\n抽出フィールド: country, skills, price\nメール本文:\n{body}"
            },
            {
                "role": "assistant",
                "content": json.dumps(assistant_json, ensure_ascii=False)
            }
        ]
    }


def write_jsonl(path, data):
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def main():
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir.parent / "data" / INPUT_CSV
    df = pd.read_csv(csv_path)

    samples = []
    skipped = 0

    for _, row in df.iterrows():
        item = build_sample(row)
        if item:
            samples.append(item)
        else:
            skipped += 1

    print(f"有效样本: {len(samples)}")
    print(f"跳过样本: {skipped}")

    if len(samples) == 0:
        print("❌ 没有可用数据")
        return

    train_data, valid_data = train_test_split(
        samples,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED
    )

    out_path = base_dir.parent / OUTPUT_DIR
    write_jsonl(os.path.join(out_path, "train.jsonl"), train_data)
    write_jsonl(os.path.join(out_path, "valid.jsonl"), valid_data)

    print(f"train: {len(train_data)}")
    print(f"valid: {len(valid_data)}")
    print("✅ 转换完成")


if __name__ == "__main__":
    main()
