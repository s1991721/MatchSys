import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

LABEL_NEG1 = -1
LABEL_0 = 0
LABEL_1 = 1
RANDOM_STATE = 42

# 阈值搜索范围
THRESHOLD_0_CANDIDATES = np.arange(0.50, 0.96, 0.02)
THRESHOLD_1_CANDIDATES = np.arange(0.50, 0.96, 0.02)

# 第一优先：0类 precision
MIN_PRECISION_FOR_0 = 0.90


# 加载数据
def load_data(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"训练数据文件不存在: {csv_path}")

    df = pd.read_csv(csv_path)

    required_columns = {"Subject", "label"}
    if not required_columns.issubset(df.columns):
        raise ValueError(f"CSV 必须包含列: {required_columns}")

    df = df.dropna(subset=["Subject", "label"]).copy()
    df["Subject"] = df["Subject"].astype(str).str.strip()
    df = df[df["Subject"] != ""]

    try:
        df["label"] = df["label"].astype(int)
    except Exception as exc:
        raise ValueError("label 列必须可转换为整数 -1 / 0 / 1") from exc

    valid_labels = {LABEL_NEG1, LABEL_0, LABEL_1}
    actual_labels = set(df["label"].unique().tolist())
    if not actual_labels.issubset(valid_labels):
        raise ValueError(f"label 只能包含 {valid_labels}，实际检测到: {actual_labels}")

    return df.reset_index(drop=True)


# 打印日志-各label分布情况
def print_label_distribution(df: pd.DataFrame, title: str) -> None:
    print(f"\n=== {title} ===")
    total = len(df)
    counts = df["label"].value_counts().sort_index()
    for label in [LABEL_NEG1, LABEL_0, LABEL_1]:
        count = int(counts.get(label, 0))
        ratio = count / total if total else 0
        print(f"label {label:>2}: {count:>5} ({ratio:.2%})")


# 流水线 向量化➡️分类器
def build_binary_pipeline(class_weight: Dict[int, float]) -> Pipeline:
    return Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 4),
                min_df=1,
                max_df=0.95,
                sublinear_tf=True,
                lowercase=False
            )
        ),
        (
            "clf",
            LogisticRegression(
                max_iter=2000,
                class_weight=class_weight,
                random_state=RANDOM_STATE
            )
        )
    ])


# 因为二阶段模型的原因，一阶段模型标签由-1、0、1转为True、False
def prepare_stage1_labels(y: pd.Series) -> np.ndarray:
    """
    阶段1：0 vs 非0
    正类 = 1 表示原始 label == 0
    负类 = 0 表示原始 label != 0
    """
    return (y.to_numpy(dtype=int) == LABEL_0).astype(int)


# 二阶段模型的新标签
def prepare_stage2_labels(y: pd.Series) -> np.ndarray:
    """
    阶段2：1 vs 非1
    正类 = 1 表示原始 label == 1
    负类 = 0 表示原始 label != 1
    """
    return (y.to_numpy(dtype=int) == LABEL_1).astype(int)


# 根据传过来的阈值，生成判断，供下一步回归调优
def predict_two_stage(
        stage1_model: Pipeline,
        stage2_model: Pipeline,
        texts: List[str],
        threshold_0: float,
        threshold_1: float
) -> np.ndarray:
    """
    两阶段预测：
      1. 阶段1：P(0) >= threshold_0 -> 输出 0
      2. 否则进入阶段2：P(1) >= threshold_1 -> 输出 1
      3. 否则输出 -1
    """
    texts = [str(x).strip() for x in texts]
    # 默认填充类型为-1类型
    preds = np.full(len(texts), LABEL_NEG1, dtype=int)

    # 使用stage1_model判断为0类型的概率
    proba_stage1 = stage1_model.predict_proba(texts)[:, 1]

    # 概率大于阈值threshold_0时，认为是0类型
    idx_stage0 = np.where(proba_stage1 >= threshold_0)[0]
    preds[idx_stage0] = LABEL_0

    # 找到剩余-1类型，还未分类的数据
    remaining_idx = np.where(preds == LABEL_NEG1)[0]
    if len(remaining_idx) > 0:
        remaining_texts = [texts[i] for i in remaining_idx]
        proba_stage2 = stage2_model.predict_proba(remaining_texts)[:, 1]

        # 注意index的local和global
        idx_stage1_local = np.where(proba_stage2 >= threshold_1)[0]
        idx_stage1_global = remaining_idx[idx_stage1_local]
        preds[idx_stage1_global] = LABEL_1

    return preds


# 计算各个类别的准度、覆盖率
def calc_binary_precision_recall_for_label(
        y_true: np.ndarray, y_pred: np.ndarray, target_label: int
) -> Tuple[float, float]:
    tp = int(((y_true == target_label) & (y_pred == target_label)).sum())  # 真实是目标类，并且也预测成目标类
    fp = int(((y_true != target_label) & (y_pred == target_label)).sum())  # 真实不是目标类，但却被预测成目标类
    fn = int(((y_true == target_label) & (y_pred != target_label)).sum())  # 真实是目标类，但却没有被预测成目标类

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0  # 准度 凡是模型说是 0 的，到底有多少真的是 0？
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0  # 覆盖率 所有真实是 0 的样本里，模型到底找出了多少？
    return precision, recall


# 评估预测的准确率
def score_thresholds(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, Dict[str, float]]:
    p0, r0 = calc_binary_precision_recall_for_label(y_true, y_pred, LABEL_0)
    p1, r1 = calc_binary_precision_recall_for_label(y_true, y_pred, LABEL_1)
    acc = accuracy_score(y_true, y_pred)  # 所有样本里，预测正确的比例是多少。

    penalty = 0.0
    if p0 < MIN_PRECISION_FOR_0:
        penalty = (MIN_PRECISION_FOR_0 - p0) * 10.0

    score = (
            5.0 * p0 +
            2.5 * r0 +
            1.5 * r1 +
            0.5 * p1 +
            0.5 * acc -
            penalty
    )

    metrics = {
        "precision_0": p0,
        "recall_0": r0,
        "precision_1": p1,
        "recall_1": r1,
        "accuracy": acc,
    }
    return score, metrics


# 遍历所有可能性，找出最合适的参数对
def search_best_thresholds(
        stage1_model: Pipeline,
        stage2_model: Pipeline,
        x_val: pd.Series,
        y_val: pd.Series
) -> Tuple[float, float, Dict[str, float]]:
    best_score = -1e18
    best_t0 = 0.85
    best_t1 = 0.75
    best_metrics = {}

    y_val_np = y_val.to_numpy(dtype=int)
    texts = x_val.tolist()

    for t0 in THRESHOLD_0_CANDIDATES:
        for t1 in THRESHOLD_1_CANDIDATES:
            y_pred = predict_two_stage(
                stage1_model=stage1_model,
                stage2_model=stage2_model,
                texts=texts,
                threshold_0=float(t0),
                threshold_1=float(t1)
            )
            score, metrics = score_thresholds(y_val_np, y_pred)
            if score > best_score:
                best_score = score
                best_t0 = float(t0)
                best_t1 = float(t1)
                best_metrics = metrics

    return best_t0, best_t1, best_metrics


# 评估模型
def evaluate_model(
        stage1_model: Pipeline,
        stage2_model: Pipeline,
        x_test: pd.Series,
        y_test: pd.Series,
        threshold_0: float,
        threshold_1: float
) -> None:
    y_true = y_test.to_numpy(dtype=int)
    y_pred = predict_two_stage(
        stage1_model=stage1_model,
        stage2_model=stage2_model,
        texts=x_test.tolist(),
        threshold_0=threshold_0,
        threshold_1=threshold_1
    )

    print("\n=== 测试集评估（两阶段模型） ===")
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
    reject_rate = float((y_pred == LABEL_NEG1).sum()) / len(y_pred)

    print("\n=== 业务重点指标 ===")
    print(f"0类 precision（最重要）: {p0:.4f}")
    print(f"0类 recall             : {r0:.4f}")
    print(f"1类 precision          : {p1:.4f}")
    print(f"1类 recall（次重要）  : {r1:.4f}")
    print(f"拒识率（预测为-1比例） : {reject_rate:.4f}")


# 训练并保存模型
def train_and_save(df: pd.DataFrame, model_output_path: str) -> None:
    print_label_distribution(df, "原始数据分布")

    # 训练集、测试集拆分   stratify（分层）保证各类数据在测试集和训练集中的比例相同
    train_val_df, test_df = train_test_split(
        df,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=df["label"]
    )

    # 训练集拆分为”训练集和验证集” 整体60% train / 20% val / 20% test
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

    # 阶段1：0 vs 非0
    y_train_stage1 = prepare_stage1_labels(y_train)
    stage1_model = build_binary_pipeline(class_weight={0: 1.0, 1: 3.0})  # 判别0标签的比重更大
    stage1_model.fit(x_train, y_train_stage1)

    # 阶段2：1 vs 非1
    y_train_stage2 = prepare_stage2_labels(y_train)
    stage2_model = build_binary_pipeline(class_weight={0: 1.0, 1: 1.5})
    stage2_model.fit(x_train, y_train_stage2)

    threshold_0, threshold_1, val_metrics = search_best_thresholds(
        stage1_model=stage1_model,
        stage2_model=stage2_model,
        x_val=x_val,
        y_val=y_val
    )

    print("\n=== 验证集最优阈值 ===")
    print(f"best threshold_0 = {threshold_0:.2f}")
    print(f"best threshold_1 = {threshold_1:.2f}")
    print("validation metrics =", val_metrics)

    evaluate_model(
        stage1_model=stage1_model,
        stage2_model=stage2_model,
        x_test=x_test,
        y_test=y_test,
        threshold_0=threshold_0,
        threshold_1=threshold_1
    )

    # 最终模型：train + val 重训
    final_x = pd.concat([x_train, x_val], axis=0)
    final_y = pd.concat([y_train, y_val], axis=0)

    final_stage1 = build_binary_pipeline(class_weight={0: 1.0, 1: 3.0})
    final_stage1.fit(final_x, prepare_stage1_labels(final_y))

    final_stage2 = build_binary_pipeline(class_weight={0: 1.0, 1: 1.5})
    final_stage2.fit(final_x, prepare_stage2_labels(final_y))

    artifact = {
        "stage1_model": final_stage1,
        "stage2_model": final_stage2,
        "threshold_0": threshold_0,
        "threshold_1": threshold_1,
        "predict_strategy": "two_stage_0_then_1_else_-1",
        "labels": [LABEL_NEG1, LABEL_0, LABEL_1],
        "config": {
            "stage1_task": "0_vs_non0",
            "stage2_task": "1_vs_non1",
            "stage1_class_weight": {0: 1.0, 1: 3.0},
            "stage2_class_weight": {0: 1.0, 1: 1.5},
        }
    }

    joblib.dump(artifact, model_output_path)
    print(f"\n模型已保存到: {model_output_path}")


# 加载模型
def load_artifact(model_path: str) -> dict:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    return joblib.load(model_path)


def predict_subjects(model_path: str, subjects: List[str]) -> pd.DataFrame:
    artifact = load_artifact(model_path)

    stage1_model = artifact["stage1_model"]
    stage2_model = artifact["stage2_model"]
    threshold_0 = artifact["threshold_0"]
    threshold_1 = artifact["threshold_1"]

    texts = [str(x).strip() for x in subjects]

    proba_stage1 = stage1_model.predict_proba(texts)[:, 1]
    proba_stage2 = stage2_model.predict_proba(texts)[:, 1]

    preds = predict_two_stage(
        stage1_model=stage1_model,
        stage2_model=stage2_model,
        texts=texts,
        threshold_0=threshold_0,
        threshold_1=threshold_1
    )

    rows = []
    for text, pred, p0, p1 in zip(texts, preds, proba_stage1, proba_stage2):
        rows.append({
            "Subject": text,
            "pred_label": int(pred),
            "score_as_0": float(p0),  # 阶段1：像0的概率
            "score_as_1": float(p1),  # 阶段2：像1的概率
        })

    return pd.DataFrame(rows)


@lru_cache(maxsize=4)
def load_artifact_cached() -> dict:
    base_dir = Path(__file__).resolve().parent
    model_path = base_dir / "email_title_classifier_two_stage_v1.joblib"
    return load_artifact(str(model_path))


def predict_subject(text: str) -> int:
    artifact = load_artifact_cached()

    stage1_model = artifact["stage1_model"]
    stage2_model = artifact["stage2_model"]
    threshold_0 = artifact["threshold_0"]
    threshold_1 = artifact["threshold_1"]

    text = str(text).strip()

    proba_stage1 = stage1_model.predict_proba([text])[:, 1]
    if proba_stage1[0] >= threshold_0:
        return 0

    proba_stage2 = stage2_model.predict_proba([text])[:, 1]
    if proba_stage2[0] >= threshold_1:
        return 1

    return -1


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir.parent / "data" / "data_cleand.csv"
    model_output_path = base_dir / "email_title_classifier_two_stage.joblib"

    df = load_data(str(csv_path))
    print(f"读取到 {len(df)} 条训练数据")
    train_and_save(df, str(model_output_path))

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
