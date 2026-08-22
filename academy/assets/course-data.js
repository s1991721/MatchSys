(() => {
  const courses = {
    aws: {
      title: "AWS Cloud Practitioner Essentials",
      description: "AWS クラウドの基本概念から主要サービス、セキュリティ、料金、アーキテクチャまで、AWS の基礎を体系的に学べる入門コースです。",
      level: "入門",
      prerequisites: "前提知識なし",
      cover: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.16.0/icons/amazonwebservices/amazonwebservices-original-wordmark.svg",
      type: "external",
      link: "https://skillbuilder.aws/learn/94T2BEN85A/aws-cloud-practitioner-essentials/8D79F3AVR7",
      chapters: [
        "クラウド入門",
        "クラウドでのコンピューティング",
        "コンピューティングサービス",
        "AWS グローバルインフラストラクチャ",
        "ネットワーキング",
        "ストレージ",
        "データベース",
        "AI・機械学習・データ分析",
        "セキュリティ",
        "モニタリング・コンプライアンス・ガバナンス",
        "料金とサポート",
        "AWS クラウドへの移行",
        "Well-Architected ソリューション"
      ]
    },
    terraform: {
      title: "Terraform Get Started - AWS",
      description: "Terraform の基本概念から、AWS インフラストラクチャの作成・変更・削除、HCP Terraform を利用した共同管理まで、Infrastructure as Code の基本ワークフローを学べる HashiCorp 公式入門コースです。",
      level: "入門",
      prerequisites: "コマンドライン・AWS の基礎",
      cover: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.16.0/icons/terraform/terraform-original.svg",
      type: "external",
      link: "https://developer.hashicorp.com/terraform/tutorials/aws-get-started",
      chapters: [
        "Infrastructure as Code と Terraform",
        "Terraform のインストール",
        "AWS インフラストラクチャの作成",
        "インフラストラクチャの管理",
        "インフラストラクチャの削除",
        "HCP Terraform を使用した共同作業"
      ]
    },
    docker: {
      title: "Docker Tutorial for Beginners",
      description: "Docker の基本概念からコンテナ、イメージ、Docker Compose、Dockerfile、Registry、Volume までを、実際のアプリケーションを使いながら体系的に学べる TechWorld with Nana の Docker 完全入門コースです。",
      level: "入門",
      prerequisites: "コマンドラインの基本操作",
      cover: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.16.0/icons/docker/docker-original.svg",
      type: "external",
      link: "https://www.youtube.com/watch?v=3c-iBn73dDE",
      chapters: [
        "Docker とは",
        "コンテナの仕組み",
        "Docker と仮想マシン",
        "Docker のインストール",
        "Docker の基本コマンド",
        "コンテナのデバッグ",
        "Docker 実践プロジェクト",
        "コンテナを使った開発",
        "Docker Compose",
        "Dockerfile とイメージの作成",
        "Private Docker Registry",
        "コンテナアプリケーションのデプロイ",
        "Docker Volume",
        "Volume を使ったデータ永続化"
      ]
    },
    kubernetes: {
      title: "Kubernetes Tutorial for Beginners",
      description: "Kubernetes の基本概念からアーキテクチャ、kubectl、YAML、Namespace、Ingress、Helm、Volume、StatefulSet、Service までを実践的に学べる TechWorld with Nana の Kubernetes 完全入門コースです。",
      level: "基礎",
      prerequisites: "Docker・Linux・ネットワークの基礎",
      cover: "https://cdn.jsdelivr.net/gh/devicons/devicon@v2.16.0/icons/kubernetes/kubernetes-original.svg",
      type: "external",
      link: "https://www.youtube.com/watch?v=X48VuDVv0do",
      chapters: [
        "Kubernetes とは",
        "Kubernetes の主要コンポーネント",
        "Kubernetes アーキテクチャ",
        "Minikube と kubectl",
        "kubectl の基本コマンド",
        "Kubernetes YAML 設定ファイル",
        "MongoDB・Mongo Express 実践プロジェクト",
        "Namespace",
        "Ingress",
        "Helm",
        "Persistent Volume",
        "StatefulSet",
        "Kubernetes Service"
      ]
    },
    gpt: {
      title: "Let's build GPT: from scratch, in code, spelled out",
      description: "Andrej Karpathy による実践的な GPT 入門講座です。Python と PyTorch を使用して、文字レベルの言語モデルから始め、Self-Attention、Multi-Head Attention、Feed Forward Network、Residual Connection、Layer Normalization などを段階的に実装し、最終的に Transformer ベースの GPT をゼロから構築します。",
      level: "実践",
      prerequisites: "Python・PyTorch の基礎",
      cover: "https://img.youtube.com/vi/kCc8FmEb1nY/maxresdefault.jpg",
      type: "external",
      link: "https://www.youtube.com/watch?v=kCc8FmEb1nY",
      chapters: [
        "言語モデルと GPT の基本概念",
        "データセット・Tokenization・Training Data の準備",
        "Bigram Language Model の実装",
        "Self-Attention の仕組みと実装",
        "Multi-Head Attention の実装",
        "Feed Forward・Residual Connection・LayerNorm",
        "Transformer Block と GPT モデルの構築",
        "GPT の学習・生成とモデルのスケーリング",
        "GPT-3・ChatGPT・Pretraining・Fine-tuning・RLHF"
      ]
    }
  };

  window.AcademyCourseData = Object.freeze({
    defaultCourseKey: "aws",
    courses: Object.freeze(courses)
  });
})();
