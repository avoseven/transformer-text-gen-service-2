# transformer-text-gen-service
Transformer文章生成モデルのWebサービス化とクラウドデプロイ

## 概要
- 本プロジェクトは、前回開発した Transformer 文章生成モデルを、外部からツールとして利用できる形にすることを目的とする
- Web Service化: FastAPIによるAPI化とGradioによるWeb UI化を行う
- Container化: Docker ImageをBuildし，Singularity / ApptainerでContainer化する
- Cloud Deploy: AWS EC2にDeployし，外部からの利用を可能にする

## Web Service化 (FastAPI / Gradio)
- ### FastAPI
    - FastAPI Serverは `app/main.py` に実装，以下のEnd Pointを提供
    1. `GET /`：Health Check用（"Hello World" を返す）
    2. `POST /generate`：文章生成 API
- Request例（curl）
```bash
curl -X POST "http://localhost:8000/generate" -H "Content-Type: application/json" \
-d '{"prompt": "私は", "max_length": 50}'
```
- Response例
```bash
{
  "prompt": "私は",
  "generated_text": "私はこの“男は別れる”とは? なぜ“女\"いい”をあらわれたことも、女友達と感じる。女が心行かれたりばり、仕事にくことから誘われていたら、なかなか私より友",
  "temperature": 1.0,
  "top_k": 50
}
```
- ### Gradio UI
    - Gradio による Web UI は `app/gradio.py` に実装, ブラウザからプロンプトを入力すると、文章の続きを生成
    - 入力：プロンプト（テキストボックス）、max_length、temperature、top_k（スライダー）
    - 出力：生成された文章（テキストボックス）
- FastAPI による API と Gradio による UI の両方を実装することで、モデルを「ツールとして利用できる形」にしています

## Container化 (Singularity / Apptainer)
- ### 作成
    1. Docker imageをBuild
        - `docker build -t avoseven/transformer-text-gen-service:api -f docker/Dockerfile.api .`
    2. Docker HubにImageをPush
        - `docker push avoseven/transformer-text-gen-service:api`
    3. Docker ImageをSingularityでPullして.sif Fileを取得
        - `singularity pull --force docker://avoseven/transformer-text-gen-service:api`
- ### 起動
    - 通常起動
        - `singularity run transformer-text-gen-service_api.sif`
    - net指定起動
        - `sudo singularity run --net --network-args "portmap=8000:8000/tcp"   transformer-text-gen-service_api.sif`
- ### Container動作確認 (応答確認)
    - `curl http://127.0.0.1:8000`

## Cloud Deployと外部Accessの確認
- ### AWS EC2
    - Instance Type: t3.small (microだと重すぎて厳しい)
    - OS: Ubuntu 22.04 LTS (aws-marketplace/ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20260610-47489723-7305-4e22-8b22-b0d57054f216)
    - Security Group:
        - SSH / TCP / Port: 22 / Source: 自分のIP
        - Custom TCP / TCP / Port: 8000 / source: 0.0.0.0/0 (For FastAIP)
        - Custom TCP / TCP / Port: 7860 / source: 0.0.0.0/0 (For Gradio)
- ### Deploy
    #### 1. EC2 Instance起動
    #### 2. SSH接続 (キーペア)
    - `ssh -i ~/.ssh/transformer-key.pem ubuntu@13.211.147.83`
    #### 3. ApptainerのInstall (Singularityより簡単にできて互換性があるため)
    #### 4. ローカルから .sif を EC2 に転送（scp）
    1. Screen セッションを開始
        - `screen -S scp_session`
        - SSH 接続が切れても、裏で動かしている処理が終わらないようにするため
    2. 転送
        - `scp -i ~/.ssh/transformer-key.pem transformer-text-gen-service_api.sif ubuntu@3.25.234.172:/home/ubuntu/`
    3. 転送中に SSH 接続が切れても大丈夫なようにデタッチ, 必要に応じて再接続して進捗確認
    #### 5. Containerの起動
    - `sudo singularity run --net --network-args "portmap=8000:8000/tcp"   transformer-text-gen-service_api.sif`
    #### 6. 外部からのAccessを確認
    - 応答確認: `curl http://127.0.0.1:8000/docs`
    - BrowserでGradio: `http://<EC2のPublic IP>:7860/` (例: `http://13.211.177.118:7860/`)
    - BrowserでFastAPI: `http://<EC2のPublic IP>:8000/docs`
    - テザリングでAccess
    - Smart PhoneからAccess

## Directory構成
.
├── README.md
├── app
│   ├── data
│   │   ├── __init__.py
│   │   └── tokenizer.py    # Tokenizer
│   ├── generate.py         # 生成器
│   ├── gradio_ui.py        # Gradio UI
│   ├── main.py             # FastAPI
│   ├── models
│   │   ├── __init__.py
│   │   └── transformer.py  # 自前のTransformer Model
│   └── utils.py            # 共通処理 (Model loadなど)
├── configs
│   └── model_config.yaml   # 設定 (Model, 学習, Path)
├── data
│   └── tokenizer
│       └── news_spm.model  # Tokenizer用spm
├── docker
│   ├── Dockerfile
│   ├── Dockerfile.api      # FastAPI用
│   ├── Dockerfile.gradio   # Gradio UI用
│   └── requirements.txt
├── docker-compose.yml
├── flagged                 # UIで生成例を保存
│   └── log.csv
├── outputs
│   └── checkpoints
│       └── ckpt_final.pt   # 保存されたModel
├── transformer-text-gen-service_api.sif
└── transformer-text-gen-service_gradio.sif
