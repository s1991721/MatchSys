import os

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


def load_data(csv_path: str) -> pd.DataFrame:
    """
    从 CSV 文件读取训练数据。
    要求至少包含两列: title, label
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"训练数据文件不存在: {csv_path}")

    df = pd.read_csv(csv_path)

    required_columns = {"Subject", "label"}
    if not required_columns.issubset(df.columns):
        raise ValueError(f"CSV 必须包含列: {required_columns}")

    # 去除空值
    df = df.dropna(subset=["Subject", "label"]).copy()

    # 转字符串，去空格
    df["Subject"] = df["Subject"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()

    # 去掉空字符串
    df = df[(df["Subject"] != "") & (df["label"] != "")]

    if len(df) == 0:
        raise ValueError("训练数据为空，无法训练。")

    return df


def build_pipeline() -> Pipeline:
    """
    构建文本分类流水线：
    1) TF-IDF 向量化
    2) 朴素贝叶斯分类

    对中文标题，使用字符级 n-gram，通常比默认按空格切词更稳。
    """
    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 4),  # 中文短文本常用配置
                min_df=2,  # 建议改成2（去噪）
                max_df=0.9,  # 去掉过于常见的特征
                sublinear_tf=True,  # 提升效果（推荐）
                lowercase=False
            )
        ),
        ("clf", MultinomialNB(alpha=0.5))
    ])
    return pipeline


def train_and_evaluate(df: pd.DataFrame, model_output_path: str) -> None:
    X = df["Subject"]
    y = df["label"]

    unique_labels = sorted(y.unique())
    print("检测到标签:", unique_labels)

    if len(unique_labels) < 2:
        raise ValueError("训练标签至少需要 2 个类别。")

    # 若样本过少，不做切分，直接全量训练
    if len(df) < 10:
        print("样本量较少，跳过验证集切分，直接全量训练。")
        pipeline = build_pipeline()
        pipeline.fit(X, y)

        artifact = {
            "model": pipeline,
            "labels": unique_labels,
            "has_other_class": "其他" in unique_labels,
            "threshold_for_other": 0.60  # 当没有“其他”类时，可用于预测阶段阈值判断
        }

        joblib.dump(artifact, model_output_path)
        print(f"模型已保存到: {model_output_path}")
        return

    # 分层切分，保证各类分布更合理
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)

    print("\n=== 验证集评估 ===")
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print(classification_report(y_test, y_pred, digits=4))

    artifact = {
        "model": pipeline,
        "labels": unique_labels,
        "has_other_class": "其他" in unique_labels,
        "threshold_for_other": 0.60
    }

    joblib.dump(artifact, model_output_path)
    print(f"模型已保存到: {model_output_path}")


from pathlib import Path
if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir.parent / "data" / "data_cleand.csv"
    model_output_path = base_dir / "email_title_classifier.joblib"

    df = load_data(str(csv_path))
    print(f"读取到 {len(df)} 条训练数据")
    train_and_evaluate(df, str(model_output_path))
