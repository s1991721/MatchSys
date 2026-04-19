import os
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


# =========================
# 配置区
# =========================
LABEL_NEG1 = -1
LABEL_0 = 0
LABEL_1 = 1

RANDOM_STATE = 42

# 是否对 1 类做下采样，避免过度压制 0 类
ENABLE_DOWNSAMPLE_LABEL_1 = False
MAX_LABEL_1_SAMPLES = 1500  # 启用下采样后，1 类最多保留多少条

# 阈值搜索范围
THRESHOLD_0_CANDIDATES = np.arange(0.50, 0.96, 0.02)
THRESHOLD_1_CANDIDATES = np.arange(0.50, 0.96, 0.02)

# 目标：优先保证 0 类 precision
MIN_PRECISION_FOR_0 = 0.90


def load_data(csv_path: str) -> pd.DataFrame:
    """
    读取训练数据。
    要求至少包含两列:
      - Subject
      - label
    label 必须是 -1 / 0 / 1
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"训练数据文件不存在: {csv_path}")

    df = pd.read_csv(csv_path)

    required_columns = {"Subject", "label"}
    if not required_columns.issubset(df.columns):
        raise ValueError(f"CSV 必须包含列: {required_columns}")

    df = df.dropna(subset=["Subject", "label"]).copy()
    df["Subject"] = df["Subject"].astype(str).str.strip()
    df = df[df["Subject"] != ""]

    # label 转为整数
    try:
        df["label"] = df["label"].astype(int)
    except Exception as exc:
        raise ValueError("label 列必须能转换为整数（-1 / 0 / 1）") from exc

    valid_labels = {LABEL_NEG1, LABEL_0, LABEL_1}
    actual_labels = set(df["label"].unique().tolist())
    if not actual_labels.issubset(valid_labels):
        raise ValueError(f"label 只能包含 {valid_labels}，实际检测到: {actual_labels}")

    if len(df) == 0:
        raise ValueError("训练数据为空，无法训练。")

    return df.reset_index(drop=True)


def print_label_distribution(df: pd.DataFrame, title: str) -> None:
    print(f"\n=== {title} ===")
    counts = df["label"].value_counts().sort_index()
    total = len(df)
    for label in [LABEL_NEG1, LABEL_0, LABEL_1]:
        count = int(counts.get(label, 0))
        ratio = count / total if total > 0 else 0
        print(f"label {label:>2}: {count:>5} ({ratio:.2%})")


def downsample_label_1(df: pd.DataFrame, max_label_1_samples: int, random_state: int) -> pd.DataFrame:
    """
    可选：对 1 类做下采样，减弱 1 类对模型的压制。
    """
    df_1 = df[df["label"] == LABEL_1]
    df_other = df[df["label"] != LABEL_1]

    if len(df_1) <= max_label_1_samples:
        return df.sample(frac=1.0, random_state=random_state).reset_index(drop=True)

    df_1_sampled = df_1.sample(n=max_label_1_samples, random_state=random_state)
    result = pd.concat([df_other, df_1_sampled], axis=0)
    return result.sample(frac=1.0, random_state=random_state).reset_index(drop=True)


def build_pipeline() -> Pipeline:
    """
    文本分类流水线：
      1) 字符级 TF-IDF
      2) 朴素贝叶斯
    """
    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 4),
                min_df=1,          # 改为1，避免稀有但有用的关键词被丢掉
                max_df=0.95,
                sublinear_tf=True,
                lowercase=False
            )
        ),
        ("clf", MultinomialNB(alpha=0.3))
    ])
    return pipeline


def get_class_index_map(model: Pipeline) -> Dict[int, int]:
    """
    返回 label -> 概率列索引 的映射
    """
    clf = model.named_steps["clf"]
    classes = clf.classes_
    return {int(label): idx for idx, label in enumerate(classes)}


def predict_with_priority(
    model: Pipeline,
    texts: List[str],
    threshold_0: float,
    threshold_1: float
) -> np.ndarray:
    """
    保守型预测逻辑：
      1) 若 P(0) >= threshold_0，则判 0
      2) 否则若 P(1) >= threshold_1，则判 1
      3) 否则判 -1
    """
    proba = model.predict_proba(texts)
    index_map = get_class_index_map(model)

    idx_0 = index_map[LABEL_0]
    idx_1 = index_map[LABEL_1]

    preds = []
    for row in proba:
        p0 = float(row[idx_0])
        p1 = float(row[idx_1])

        if p0 >= threshold_0:
            preds.append(LABEL_0)
        elif p1 >= threshold_1:
            preds.append(LABEL_1)
        else:
            preds.append(LABEL_NEG1)

    return np.array(preds, dtype=int)


def calc_binary_precision_recall_for_label(y_true: np.ndarray, y_pred: np.ndarray, target_label: int) -> Tuple[float, float]:
    """
    计算某个 label 的 precision / recall
    """
    tp = int(((y_true == target_label) & (y_pred == target_label)).sum())
    fp = int(((y_true != target_label) & (y_pred == target_label)).sum())
    fn = int(((y_true == target_label) & (y_pred != target_label)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def score_thresholds(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, Dict[str, float]]:
    """
    业务目标评分：
      - 第一优先：0 类 precision 高
      - 第二优先：0 类 recall
      - 第三优先：1 类 recall
      - 第四优先：整体 accuracy
    """
    p0, r0 = calc_binary_precision_recall_for_label(y_true, y_pred, LABEL_0)
    p1, r1 = calc_binary_precision_recall_for_label(y_true, y_pred, LABEL_1)
    acc = accuracy_score(y_true, y_pred)

    # 若 0 类 precision 低于底线，严重扣分
    penalty = 0.0
    if p0 < MIN_PRECISION_FOR_0:
        penalty = (MIN_PRECISION_FOR_0 - p0) * 10.0

    score = (
        5.0 * p0 +
        2.5 * r0 +
        1.5 * r1 +
        0.5 * p1 +
        0.5 * acc
        - penalty
    )

    metrics = {
        "precision_0": p0,
        "recall_0": r0,
        "precision_1": p1,
        "recall_1": r1,
        "accuracy": acc,
    }
    return score, metrics


def search_best_thresholds(model: Pipeline, x_val: pd.Series, y_val: pd.Series) -> Tuple[float, float, Dict[str, float]]:
    """
    在验证集上搜索最优阈值
    """
    best_score = -1e18
    best_t0 = 0.85
    best_t1 = 0.75
    best_metrics = {}

    y_val_np = y_val.to_numpy(dtype=int)

    for t0 in THRESHOLD_0_CANDIDATES:
        for t1 in THRESHOLD_1_CANDIDATES:
            y_pred = predict_with_priority(model, x_val.tolist(), threshold_0=float(t0), threshold_1=float(t1))
            score, metrics = score_thresholds(y_val_np, y_pred)

            if score > best_score:
                best_score = score
                best_t0 = float(t0)
                best_t1 = float(t1)
                best_metrics = metrics

    return best_t0, best_t1, best_metrics


def evaluate_model(model: Pipeline, x_test: pd.Series, y_test: pd.Series, threshold_0: float, threshold_1: float) -> None:
    """
    在测试集上评估
    """
    y_true = y_test.to_numpy(dtype=int)
    y_pred = predict_with_priority(model, x_test.tolist(), threshold_0=threshold_0, threshold_1=threshold_1)

    print("\n=== 测试集评估（保守型预测） ===")
    print(f"threshold_0 = {threshold_0:.2f}")
    print(f"threshold_1 = {threshold_1:.2f}")
    print(f"Accuracy    = {accuracy_score(y_true, y_pred):.4f}")

    print("\n[Classification Report]")
    print(classification_report(
        y_true,
        y_pred,
        labels=[LABEL_NEG1, LABEL_0, LABEL_1],
        digits=4,
        zero_division=0
    ))

    print("[Confusion Matrix] 行是真实标签，列是预测标签")
    cm = confusion_matrix(y_true, y_pred, labels=[LABEL_NEG1, LABEL_0, LABEL_1])
    cm_df = pd.DataFrame(
        cm,
        index=["true_-1", "true_0", "true_1"],
        columns=["pred_-1", "pred_0", "pred_1"]
    )
    print(cm_df)

    p0, r0 = calc_binary_precision_recall_for_label(y_true, y_pred, LABEL_0)
    p1, r1 = calc_binary_precision_recall_for_label(y_true, y_pred, LABEL_1)

    print("\n=== 业务重点指标 ===")
    print(f"0类 precision（最重要）: {p0:.4f}")
    print(f"0类 recall             : {r0:.4f}")
    print(f"1类 precision          : {p1:.4f}")
    print(f"1类 recall（次重要）  : {r1:.4f}")

    reject_rate = float((y_pred == LABEL_NEG1).sum()) / len(y_pred)
    print(f"拒识率（预测为-1比例） : {reject_rate:.4f}")


def train_and_save(df: pd.DataFrame, model_output_path: str) -> None:
    """
    训练流程：
      1) 可选下采样 1 类
      2) train / val / test 切分
      3) 训练模型
      4) 在 val 上搜阈值
      5) 在 test 上评估
      6) 用 train+val 重训最终模型并保存
    """
    print_label_distribution(df, "原始数据分布")

    if ENABLE_DOWNSAMPLE_LABEL_1:
        df = downsample_label_1(df, MAX_LABEL_1_SAMPLES, RANDOM_STATE)
        print_label_distribution(df, "下采样后的数据分布")

    # 先切 test（20%）
    train_val_df, test_df = train_test_split(
        df,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=df["label"]
    )

    # 再从剩余中切 val（25% of 80% = 20%）
    train_df, val_df = train_test_split(
        train_val_df,
        test_size=0.25,
        random_state=RANDOM_STATE,
        stratify=train_val_df["label"]
    )

    print_label_distribution(train_df, "训练集分布")
    print_label_distribution(val_df, "验证集分布")
    print_label_distribution(test_df, "测试集分布")

    x_train = train_df["Subject"]
    y_train = train_df["label"]

    x_val = val_df["Subject"]
    y_val = val_df["label"]

    x_test = test_df["Subject"]
    y_test = test_df["label"]

    # 先训练初始模型，用于搜阈值
    model = build_pipeline()
    model.fit(x_train, y_train)

    threshold_0, threshold_1, val_metrics = search_best_thresholds(model, x_val, y_val)

    print("\n=== 验证集最优阈值 ===")
    print(f"best threshold_0 = {threshold_0:.2f}")
    print(f"best threshold_1 = {threshold_1:.2f}")
    print("validation metrics =", val_metrics)

    # 测试集评估
    evaluate_model(model, x_test, y_test, threshold_0, threshold_1)

    # 用 train + val 重训最终模型
    final_x = pd.concat([x_train, x_val], axis=0)
    final_y = pd.concat([y_train, y_val], axis=0)

    final_model = build_pipeline()
    final_model.fit(final_x, final_y)

    artifact = {
        "model": final_model,
        "labels": [LABEL_NEG1, LABEL_0, LABEL_1],
        "threshold_0": threshold_0,
        "threshold_1": threshold_1,
        "predict_strategy": "priority_0_then_1_else_-1",
        "config": {
            "label_neg1": LABEL_NEG1,
            "label_0": LABEL_0,
            "label_1": LABEL_1,
            "enable_downsample_label_1": ENABLE_DOWNSAMPLE_LABEL_1,
            "max_label_1_samples": MAX_LABEL_1_SAMPLES,
        }
    }

    joblib.dump(artifact, model_output_path)
    print(f"\n模型已保存到: {model_output_path}")


def load_artifact(model_path: str) -> dict:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    return joblib.load(model_path)


def predict_subjects(model_path: str, subjects: List[str]) -> pd.DataFrame:
    """
    预测接口示例
    """
    artifact = load_artifact(model_path)
    model: Pipeline = artifact["model"]
    threshold_0: float = artifact["threshold_0"]
    threshold_1: float = artifact["threshold_1"]

    subjects_clean = [str(x).strip() for x in subjects]
    preds = predict_with_priority(model, subjects_clean, threshold_0, threshold_1)
    proba = model.predict_proba(subjects_clean)

    index_map = get_class_index_map(model)
    idx_neg1 = index_map[LABEL_NEG1]
    idx_0 = index_map[LABEL_0]
    idx_1 = index_map[LABEL_1]

    rows = []
    for text, pred, p in zip(subjects_clean, preds, proba):
        rows.append({
            "Subject": text,
            "pred_label": int(pred),
            "proba_-1": float(p[idx_neg1]),
            "proba_0": float(p[idx_0]),
            "proba_1": float(p[idx_1]),
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir.parent / "data" / "data_cleand.csv"
    model_output_path = base_dir / "email_title_classifier_priority.joblib"

    df = load_data(str(csv_path))
    print(f"读取到 {len(df)} 条训练数据")
    train_and_save(df, str(model_output_path))

    # ===== 预测示例 =====
    demo_subjects = [
        "案件のご紹介 / Python案件 / リモート可",
        "弊社所属エンジニアのご提案",
        "セミナー開催のお知らせ",
        "要件定義から対応可能な人材のご紹介",
        "急募案件のご案内",
    ]

    print("\n=== 预测示例 ===")
    pred_df = predict_subjects(str(model_output_path), demo_subjects)
    print(pred_df)