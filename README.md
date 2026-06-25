# transformer-text-gen-service
Transformer文章生成モデルのWebサービス化とクラウドデプロイ

## 概要
- Transformer Decoderを用いた文章生成ModelをCloud DeployしてWeb Serviceとして公開する
- FastAPIによるAPI化とGradioによるWeb UI化を行う
- Docker ImageをBuildし，Singularity / ApptainerでContainer化する
- AWS EC2にDeployし，外部からの利用を可能にする

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

---
## memo

### 進捗
- [x] setup (docker/Dockerfile, docker/requirements.txt, docker-compose.yml)
- [x] FastAPI Server動作確認
    - [x] main.py (最小Sample)
    - [x] Docker composeで環境を起動
    - [x] http://localhost:8000 で"Hello World"が返ってくる
    - [x] http://localhost:8000/generate で固定のResponseが返ってくる
- [x] FastAPIにTransformerモデルを連携し、文章生成APIを完成させる
    - [x] 推論用のコードをコピー (モデル定義（TransformerDecoder など）, トークナイザ（AutoTokenizer）, モデル読み込み（from_pretrained または load_state_dict）, 生成関数（generate メソッド）)
    - [x] FastAPIの /generate エンドポイントから、前回のTransformerモデルを呼び出して文章生成を行う
    - [x] 生成結果をJSONで返す
    - [x] curl で動作確認し、「文章生成Web API」として完成させる
        - `
        $ curl -X POST "http://localhost:8000/generate" \
        -H "Content-Type: application/json" \
        -d '{"prompt": "私は", "max_length": 50}'
        `
        - `
        {"prompt":"私は","generated_text":"私はこの“男は別れる”とは? なぜ“女\"いい”をあらわれたことも、女友達と感じる。女が心行かれたりばり、仕事にくことから誘われていたら、なかなか私より友","temperature":1.0,"top_k":50}
        `
- [x] Gradio UIの実装
    - [x] app/gradio.py でGradio UIを作成
    - [x] Docker composeにServiceを追加
    - [x] 動作確認 (`docker compose up --build` で再起動, ブラウザで `http://localhost:7860` にアクセスしGradio UIを確認, プロンプトを入力して生成結果を確認)
- [x] Dockerイメージのビルドとレジストリへのpush
    - [x] (オマケ)Dockerfileの分割(FastAPI用とGradio用)，再構築，動作確認
    - [x] Docker Hubへの登録
    - [x] Docker ImageのBuild
    - [x] Docker HubへのPush
- [x] Singularityでの起動確認（ローカル）
    - [x] SingularityのInstall
    - [x] Docker HubからImageをPull
    - [x] 起動確認
        - [x] 通常起動
        - [x] net指定起動
        - [x] 同時起動`curl http://127.0.0.1:8000/docs`, `curl http://127.0.0.1:7860`
- [x] Cloudで実行
    - [x] AWS Account準備
    - [x] EC2 Instanceの作成 13.211.147.83
    - [x] EC2へのSSH接続
    - [x] Singularity(が無理だったのでApptainer)のInstall
    - [x] ローカルから .sif を EC2 に転送（scp）
    - [x] Apptainer Containerの起動
    - [x] 動作確認 (FastAPI/Gradio)
        - [x] `curl http://127.0.0.1:8000/docs`
        - [x] Browser`http://13.211.177.118:7860/`
        - [x] Browser`http://13.211.177.118:8000/docs`
        - [x] 同時起動
        - [x] `/generator`End PointのTest
        - [x] Smart phoneのテザリングでAccess
        - [x] Smart phoneからAccess
- [ ] HTTPS 化
    - [ ] ACM で SSL 証明書を発行
    - [ ] CloudFront でディストリビューションを作成
    - [ ] Route 53 でドメインを CloudFront に紐付け
    - [ ] https://text-gen.example.com で Gradio にアクセス可能
- [ ] 余裕があれば
    - [ ] 追加学習改善
    - [ ] Dockerfileを分けたときに，Gradioの標準出力？が出なくなったものの分析
        - 起動時の`api-1  | INFO:     Will watch for changes in these directories: ['/code']`系のやつがGradioだけ出なくなった
        - `docker compose logs gradio`で何も出ない
        - Gradioの起動CMDに"-u"Optionを指定したら以前とは異なるが何かしら出力されるようにはなった`CMD ["python", "-u", "app/gradio_ui.py"]`

#### Command
- pwd
    - `singularity exec transformer-text-gen-service_api.sif pwd`

#### FastAPI
- Root: 「どのURLにアクセスしたときに、どの処理を実行するか」を決めるもの
- シリアライズ／デシリアライズ: データの形式を変換する処理
- シリアライズ（serialize）：プログラム内のオブジェクト（Pythonのdictやクラスインスタンスなど）を、ネットワークで送れる形式（JSONなど）に変換すること
- デシリアライズ（deserialize）：ネットワークから受け取ったデータ（JSONなど）を、プログラム内のオブジェクト（Pythonのdictやクラスインスタンスなど）に変換すること
- FastAPIでは、pydanticの BaseModel を使うことで、このシリアライズ／デシリアライズを自動でやってくれます
- 
```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"こんにちは"}'
```
- `curl`: HTTPリクエストを送るコマンドラインツール
- `-X POST`: HTTPメソッドをPOSTに指定
- `"http://localhost:8000/generate"`：送信先のURL
- `-H "Content-Type: application/json"`：リクエストのヘッダーを指定（JSON形式）, 「送るデータがJSON形式ですよ」
- `-d '{"prompt":"こんにちは"}'`：リクエストボディ（送るデータ）を指定, FastAPIはこれを GenerateRequest の prompt フィールドとして受け取ります
    - `-d '{"prompt":"こんにちは", "temperature": 0.5}'`とかもOK

#### Gradio
- `demo = gr.Interface()`: 「どんな入力を受け取って、どんな関数を実行し、どんな出力を表示するか」 を定義
- `fn=gradio_generate`: 実行する関数
- `inputs=[gr.Textbox(label="プロンプト", placeholder="文章の続きを入力してください"),...]`: 入力UI（テキストボックスやスライダーなど）
- `outputs=gr.Textbox(label="生成結果")`: 出力UI（テキストボックスなど）
- `title="Transformer文章生成モデル"`: ページタイトル
- `description="プロンプトを入力すると、文章の続きを生成します。"`: ページの説明文
- `demo.launch(server_name="0.0.0.0", server_port=7860, share=False)`: Gradioサーバの起動
    - server_name="0.0.0.0"：すべてのIPアドレスからアクセス可能
    - server_port=7860：ポート番号（http://localhost:7860）
    - share=False：公開URLを作成しない（ローカルでのみアクセス可能）

#### Docker ImageのBuild
- `docker build [オプション] <ビルドコンテキストのパス>`
    - <ビルドコンテキストのパス>：Dockerfileやコピーするファイルが置かれているディレクトリ（通常は . でカレントディレクトリ）
    - [オプション]：タグ名やDockerfileのパスなどを指定
        - `docker build -t イメージ名:タグ .`: -t は --tag の略で、ビルドするイメージに名前（タグ）を付けます
        - `docker build -f docker/Dockerfile.api .`: -f は --file の略で、使用するDockerfileのパスを指定
            - デフォルトではカレントディレクトリの Dockerfile を探しますが、このプロジェクトでは docker/Dockerfile.api のようにサブディレクトリに置いているので、-f で指定
        - `docker build -t transformer-text-gen-service:api -f docker/Dockerfile.api .`: ビルドコンテキスト
            - Dockerfile内の COPY . . などは、この . 以下のファイルを対象にします
            - プロジェクトルートで実行するのが一般的
```bash
docker build -t transformer-text-gen-service:api -f docker/Dockerfile.api .
docker build -t transformer-text-gen-service:gradio -f docker/Dockerfile.gradio .
# Image一覧の確認
docker images
```

#### Docker ImageのPush
- Registry: コンテナイメージを保存・共有する場所
    - Docker Hub：Docker公式のパブリックレジストリ
    - ECR（Elastic Container Registry）：AWSのプライベートレジストリ
    - Dockerイメージをレジストリにpushしておけば、どこからでもpullできるようになります
- Docker Hub上でRipository `transformer-text-gen-service`を作成
- `docker tag transformer-text-gen-service:api avoseven/transformer-text-gen-service:api`: ImageのTag付け
- `docker push avoseven/transformer-text-gen-service:api`: Push
- Tag付けとまとめて?`docker build -t avoseven/transformer-text-gen-service:api -f docker/Dockerfile.api .`
- SingularityでDocker Imageを利用する方法
    1. Registry経由（推奨）
        - どこからでもpullできる
        - クラウドやHPC環境でも利用可能
        - バージョン管理がしやすい
    2. ローカル経由（可能だが非推奨）
        - イメージの共有が面倒（tarファイルを転送する必要がある）
        - クラウドやHPC環境での利用が不便
        - バージョン管理がしづらい
- Docker Hub上にImageがあがっていることを確認
```bash
# 1. Registry経由
# Docker Hubの場合
singularity pull docker://your-dockerhub-username/transformer-text-gen-service:latest

# ECRの場合
singularity pull docker://123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/transformer-text-gen-service:latest
```
```bash
# 2. Local経由
# Dockerイメージをtarファイルに保存
docker save transformer-text-gen-service:latest -o transformer-text-gen-service.tar

# Singularityでtarファイルからイメージを作成
singularity build transformer-text-gen-service.sif docker-archive://transformer-text-gen-service.tar
```

#### Singularity
- HPC（High Performance Computing）環境でよく使われるコンテナランタイム
- Dockerイメージをそのまま使える（docker:// プレフィックスでpull可能）
- ルート権限なしでコンテナを実行できるのが特徴
- Install
    - 依存PackageのInstall
        - `sudo apt update`
        - `sudo apt install -y wget build-essential libssl-dev uuid-dev libgpgme-dev squashfs-tools`
    - Goのインストール（Singularityのビルドに必要）
        - `wget https://go.dev/dl/go1.21.6.linux-amd64.tar.gz`: Goのバイナリをダウンロード（例：1.21.6）
        - `sudo tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz`: # /usr/localに展開
        - `echo 'export PATH=/usr/local/go/bin:$PATH' >> ~/.bashrc`: # PATHに追加
        - `source ~/.bashrc`
    - Singularityのインストール
        - `wget https://github.com/sylabs/singularity/releases/download/v3.11.4/singularity-ce_3.11.4-jammy_amd64.deb`: # Singularity CEのdebパッケージをダウンロード（例：3.11.4）
        - `sudo dpkg -i singularity-ce_3.11.4-jammy_amd64.deb`: Install
    - 確認
        - `singularity --version`: Versionが表示されればOK
- Docker HubからImageをPull
    - `singularity pull docker://your-dockerhub-username/transformer-text-gen-service:gradio`
    - `singularity pull --force docker://avoseven/transformer-text-gen-service:api`: Defaultでは上書きできないので
- Singularity コンテナの起動
    - `singularity run transformer-text-gen-service_api.sif`
        - `ModuleNotFoundError: No module named 'generate'`: docker composeで指定していたPYTHONPATHをDokerfileへ
- 停止
    - Ctrl+C, `docker compose down`みたいなCommandはないらしい
    - `ps aux | grep singularity`: Processが残っていないかの確認
- 動作確認
    - 別Terminalで両方とも起動 (1つのターミナルで2つ同時に起動すると、1つ目のプロセスがブロックされます)
    - `sudo singularity run --net --network-args "portmap=8000:8000/tcp" \
  transformer-text-gen-service_api.sif`
    - `sudo singularity run --net --network-args "portmap=7860:7860/tcp" \
  transformer-text-gen-service_gradio.sif`
    - `curl`で確認
- 独立Network起動 (--net)
    - `sudo singularity run --net --network-args "portmap=8000:8000/tcp" transformer-text-gen-service_api.sif`
    - `--net`: Networkの隔離
        - 通常起動だと，NetworkはWSLと共有
        - net指定によりSingularity専用Networkで実行できる
        - WSLとは別のネットワーク名前空間(Network Namespace)が作られる
    - `--nerwark-args`: ネットワーク作成時の追加オプション
        - `--net`で困ること: FastAPIは`0.0.0.0:8000`で待ち受けるが，実際には`10.22.0.23:8000`のような専用NICで待ち受け
        - (NIC: Network Interface Card)
            - もともとは、PCをネットワークに接続するためのハードウェアのこと
            - 最近では物理カードだけでなく、IPアドレスを持つネットワーク接続口全般をNICと呼ぶことが多い
        - つまり，Windowsから`localhost:8000`へ行ってもFastAPIは見えない
        - そこで`portmap`
            - `--network-args "portmap=8000:8000/tcp"`
            - `WSL:8000` -> `Singularity:8000`というPort転送を作る
            - (Dockerなら`docker run -p 8000:8000`みたいな)
        - `portmap`のほかにも，`IP固定`, `MTU`, `MACアドレス`など指定できるらしい
    - 通常起動だと，WSL Networkをそのまま使っているので，コンテナが本当に独立して動けるかが検証しきれていない
    - そのためこれを用いることで，完全に独立した環境での確認を行った
#### AWS EC2
- EC2 InstanceにSSH接続
- SingularityのInstall
    - yum: Red Hat 系 Linux（Amazon Linux もその仲間）で使われるパッケージ管理ツール
- 自分のIPが変わるとSSH接続ができなくなるので注意
- SCPで.sif転送
    - LocalでScreen sessionを開始
    - `scp -i ~/.ssh/transformer-key.pem transformer-text-gen-service_api.sif ubuntu@3.25.234.172:/home/ubuntu/`
    - 転送中に SSH 接続が切れても大丈夫なようにデタッチ
    - 必要に応じて再接続して進捗確認
- Cloudで実行：次の手順（Apptainer 起動 + 動作確認）
    - EC2でScreen session開始
#### Screen/tmux
- terminal multiplexer
- 1つのターミナルウィンドウの中で、複数の「タブ」や「ペイン」を切り替えたり、バックグラウンドでプロセスを動かし続けたりできます
- SSH 接続が切れても、裏で動かしている処理が終わらないようにする「デタッチ（切り離し）」機能が便利
- Scteen
    - 古くからあるツールで、多くの Linux ディストリビューションに標準で入っています
    - 長時間かかる処理（例：大きなファイルの転送、ビルド、トレーニング）をバックグラウンドで動かし続ける
    - SSH 接続が切れても処理を続けたいとき
    - `screen -S scp_session`: 新しい Screen セッションを開始（名前付き）
    - `Ctrl + a` を押してから `d` を押す
        - セッションから「デタッチ」（切り離し）する
            - `[detached from 6015.scp_session]`
            - セッションをバックグラウンドに退避できます（SSH 接続が切れても処理は続きます）
    - `screen -ls`: デタッチしたセッションの一覧を表示
    - `screen -r scp_session`: 特定のセッションに再接続（アタッチ）
    - やりたい処理が完了し，Sessionの役目を終えたら
        - 基本は放置でOK
        - Screen セッションは、中で動いているプロセス（この場合は scp）が終了すると、実質的に「終了状態」になります
        - ただし、Screen の管理上は「終了したセッション」として一覧に`(Dead ???)` のように表示されることがあります
        - メモリやリソースを消費していないため実害はほぼないが、一覧が煩雑になるのが気になる場合は明示的に終了してもよい
            - セッションに再接続してから、`exit` または `Ctrl + d`

- tmux
    - screen の後継的な存在で、より高機能
- なぜ？
    - .sif の転送（scp）や Apptainer の起動は、数分〜数十分かかることがある
    - その間に SSH 接続が切れると、処理が中断されるが，screen や tmux を使うと、接続が切れても裏で処理が続くので安心
#### FastAPI Document
- `\generator`End PointのTest
    0. `http://13.211.177.118:8000/docs`
    1. /generate エンドポイントをクリック  
    2. 「Try it out」ボタンをクリック  
    3. text パラメータに生成したいテキストを入力（例："こんにちは"）  
    4. 「Execute」ボタンをクリック  
    5. 「Response body」に生成されたテキストが表示される
#### ACM（AWS Certificate Manager）
- 「このドメインは本当にあなたのものですか？」を確認してから証明書を発行

### Error
- `api-1  | ImportError: cannot import name 'JapaneseTokenizer' from 'data.tokenizer' (unknown location)`
    - importできない問題
    - app.data.tokenizerで行けるが，前Projectや生成コマンドで動いていた状態から変えたくない
    - `    environment:  - PYTHONPATH=/code/app`で成功
        - コンテナ内で `data/` や `utils/` をPythonパスから見えるようにする必要があります
        - docker-compose.yml の api サービスに環境変数を追加
        - これで、コンテナ内のPythonが /code と /code/app をパスに含めてくれます
- ` ImportError: cannot import name 'HfFolder' from 'huggingface_hub' (/usr/local/lib/python3.10/site-packages/huggingface_hub/__init__.py)`
    - Version互換性問題
    - HfFolder クラスは huggingface_hub v1.0.x で削除された
    - Gradioが古いバージョンの huggingface_hub に依存しているため、HfFolder を参照しようとしてエラーに
    - requirements試行錯誤
        - `gradio==3.50.2`, `huggingface_hub>=0.19.3,<2.0`: NG(gradio古いError)
        - `gradio`, `huggingface_hub>=0.19.3,<2.0`: NG(HfFolderがないError)
        - `gradio`, `huggingface_hub<1.0.0`: NG(Transformers==5.7.0に反する)
        - `gradio`, `huggingface_hub<1.0.0`, `transformers==4.30.2`: NG(gradioとfastAPIとの互換性Error)
        - `gradio==3.50.2`, `huggingface_hub<1.0.0`, `transformers==4.30.2`: NG(gradioとfastAPIとの互換性Error)
        - Gradio 3.50.2は2023年ごろRelease, Pydantic 1系を前提に動いているらしい
        - `huggingface_hub==0.19.4`, `pydantic==1.10.13`: OK(起動時Error出ず)
- dpkg-newによるFile Error
    - `FATAL:   While initializing: couldn't parse configuration file /etc/singularity/singularity.conf: open /etc/singularity/singularity.conf: no such file or directory`
        - SingularityでPull時，設定ファイル（/etc/singularity/singularity.conf）が存在しないことが原因
        - `sudo singularity config global`: 設定ファイルを作ってみる -> NG (なんか引数が必要)
        - `sudo mv /etc/singularity/singularity.conf.dpkg-new /etc/singularity/singularity.conf`: etc/singularityを見ると，.dpkg-newならあったのでそれを単にRename -> OK, あとで不都合なければよいが
    - `FATAL:   /etc/singularity/capability.json must be owned by root`
        - これもRename, バンバン変えていいのかなぁ
        - `sudo mv /etc/singularity/capability.json.dpkg-new /etc/singularity/capability.json`
    - `FATAL:   /etc/singularity/ecl.toml must be owned by root`
        - Rename
- VS Code 切断
    - singularityでpullやrunすると頻繁に発生
    - 根本的解決ではないが，PC再起動するとよくなる
    - 処理が重いとかそういうこと？
    - apiのpull後，gradioのpull時に初観測
    - 聞いた話だとPCのSpeckや，VS Code開きすぎなどが原因で経験ある人がいた
    - .sifがデカすぎてなにか起きていると推測
    - .sifのSizeがapi(9GB)とgradio(16GB)で違う
        - apiのbuildで.sifが作成された後，gradioでapiの.sifをbuildに含めているためと思われる
        - 少しでも軽量にするため，dockerignoreなるもので.sifを除外する (.dockerignore)
            - OK, .sif自体も3GB程度になり，VS Code切断も解消
            - Gitが壊れてしまったため，別Ripositoryに移行することにはなった
- コンテナに--net と --network-args "portmap=8000:8000/tcp" を使ってホストの 8000 ポートにマッピングして起動ができない
    - `singularity run --net --network-args "portmap=8000:8000/tcp" \
  transformer-text-gen-service_api.sif`: NG (管理者権限要求)
    - `sudo`: NG (`etc/singularity/network`の設定File異常)
    - .dpkg-new除去Rename: NG (`ModuleNotFoundError: No module named 'app'`)
    - `--fakeroot` Option指定: NG (iptables 関連のエラー, たぶんInstallを要求)
    - `singularity run transformer-text-gen-service_api.sif`（--net なし）では正常に起動し、ブラウザからもアクセスできる
    - `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`: NG (`FileNotFoundError: [Errno 2] No such file or directory: 'configs/model_config.yaml'`)
    - `ENV PYTHONPATH=/code:/code/app`: NG (変わらず)
    - `CMD`だけ戻す: NG (変わらず)
    - `ENV`も戻して`COPY configs/ configs/`追加: NG (appなしError)
    - `ENV PYTHONPATH=/code:/code/app`: NG (変わらずconfigない)
    - `COPY`を明示的に指定して`. .`でなくapp, configs, data, docker, outputsを指定: NG (変わらず)
    - `COPY configs/ ./configs/`: NG (変わらず)
    - Container内のFile存在確認
        - `singularity exec transformer-text-gen-service_api.sif \
  ls -la /code/configs`
            - `model_config.yaml`: ある
    - Current Directoryを確認
        - `singularity exec transformer-text-gen-service_api.sif pwd`
            - `/home/seven/workspace/transformer-text-gen-service-2`
        - `sudo singularity exec \
  --net \
  --network-args "portmap=8000:8000/tcp" \
  transformer-text-gen-service_api.sif pwd`
            - `/root`
        - sudoだとCurrent Directoryが変わる！？
            - pwd指定だと起動成功: `sudo singularity run \
  --pwd /code \
  --net \
  --network-args "portmap=8000:8000/tcp" \
  transformer-text-gen-service_api.sif`
        - 対策：相対パス参照を廃止し、コード位置基準で絶対パスを生成するよう修正
            - `ROOT_DIR = Path(__file__).resolve().parent.parent`
        - OK `sudo singularity run \
  --net \
  --network-args "portmap=8000:8000/tcp" \
  transformer-text-gen-service_api.sif`
- `ERR_CONNECTION_REFUSED (-102)`: 起動はできたっぽいが，Browserから見れない
    - `INFO: Uvicorn running on http://0.0.0.0:8000`: 起動Logは正常
    - `http://localhost:8000`: 上記Error
    - `http://127.0.0.1:8000`: 同様
    - `curl http://127.0.0.1:8000`
        - `{"message":"Transformer文章生成API"}`: これはOK
    - Singularity Network確認: `sudo singularity exec \
  --net \
  --network-args "portmap=8000:8000/tcp" \
  transformer-text-gen-service_api.sif \
  hostname -I`
        - `10.22.0.23`
    - WSL Port確認: `ss -lntp | grep 8000`
        - 何も表示されない
    - 利用環境は `Windows -> WSL -> Singularity`
        - 通常実行時`singularity run`: WSLのNetwork名前空間を共有するため，
            - Windows Browser -> localhost:8000 -> WSL:8000 -> FastAPI
            - となり，BrowserからAccess可能
        - net指定実行時`sudo singularity run --net`: 独立したNetwork名前空間が生成されるらしい
            - `Windows -> WSL -> Singularity専用Network(CNI Network)`になる
            - Windows Browser -> localhost:8000  x  WSL localhost:8000(誰もListenしていない)
            - FastAPIは`0.22.0.23:8000`で待ち受け
        - WSL内部からの`curl`は成功する
        - しかし，WindowsのBrowserからのAccessは，WSLのlocalhost転送対象外となるため接続できない
        - WSLの localhost forwarding は「WSL上で直接待受しているポート」は転送しますが、Singularity が CNI bridge の中に作った仮想ネットワークまでは面倒を見ません らしい
    - アプリケーション問題ではなく，WSL + Singularity独立ネットワーク構成による挙動だった
    - `curl`が成功しているため，Containerとしての検証としては動作確認完了でよいものとする
- `/usr/local/bin/python: can't open file '/root/app/gradio_ui.py': [Errno 2] No such file or directory`
    - Gradio Container起動時`sudo singularity run --net --network-args "portmap=7860:7860/tcp"   transformer-text-gen-service_gradio.sif`
    - net指定によるWorkDir違い問題
    - 実行時Command修正，Moduleとして起動することで，Current Directoryによらないはず
        - `CMD ["python", "-u", "-m", "app/gradio_ui"]`: NG (Mod実行することでapp を含む親ディレクトリを探す挙動に)
        - `ENV PYTHONPATH=/code:/code/app`: OK
- `No match for argument: singularity`
    - EC2でSingularity Install時`sudo yum install -y singularity`
    - Amazon Linux 2023 のデフォルトリポジトリに singularity パッケージが含まれていないことを意味
    - EPEL（Extra Packages for Enterprise Linux） という追加リポジトリを有効にすると、singularity がインストールできるようになります
        - NG (`Error: Unable to find a match: epel-release`)
    - Singularity の公式 RPM を直接インストールする
        - `sudo yum install -y openssl-devel libuuid-devel libseccomp-devel wget squashfs-tools`
        - `sudo yum install -y golang`
        - Amazon Linux 2023 と互換性のある RPM を探します
            - Amazon Linux 2023 は RHEL 9 系互換なので、「RHEL/CentOS/AlmaLinux/Rocky 9 (el9)」用の RPM が最も互換性が高い
        - RPM をダウンロード`wget https://github.com/sylabs/singularity/releases/download/v4.4.2/singularity-ce-4.4.2-1.el9.x86_64.rpm`
        - Install`sudo rpm -ivh singularity-ce-4.4.2-1.el9.x86_64.rpm`
            - `error: Failed dependencies:`
                -  Singularity が動くために必要なパッケージがまだ入っていないだけ
    - Amazon LinuxじゃなくてUbuntuでInstanceを作り直す
        - `Ubuntu 22.04 LTS - Jammy`
        - 起動
        - SSH接続`ssh -i transformer-key.pem ubuntu@13.211.147.83`
        - `sudo apt update`
        - `sudo apt install -y wget build-essential libssl-dev libuuid-dev libseccomp-dev pkg-config squashfs-tools cryptsetup`
            - `E: Unable to locate package libuuid-dev`: Package名が違うだけ
        - `sudo apt install -y wget build-essential libssl-dev uuid-dev libseccomp-dev pkg-config squashfs-tools cryptsetup`
        - `VERSION=4.4.2`
        - `get https://github.com/sylabs/singularity/releases/download/v${VERSION}/singularity-ce-${VERSION}.tar.gz`
        - `tar -xzf singularity-ce-${VERSION}.tar.gz`
        - `cd singularity-ce-${VERSION}`
        - `./mconfig`
            - NG(Goがない)`checking: host Go compiler (at least version 1.25)... not found!`
            - `wget https://go.dev/dl/go1.22.5.linux-amd64.tar.gz`
            - `sudo tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz`
            - `echo 'export PATH=/usr/local/go/bin:$PATH' >> ~/.bashrc`
            - `source ~/.bashrc`
            - `go version`: OK
            - `./mconfig`: NG(変わらず)
        - 無理，Apptainer入れてみる
            - `sudo apt update`
            - `sudo apt install -y software-properties-common`
            - `sudo add-apt-repository -y ppa:apptainer/ppa`
            - `sudo apt update`
            - `sudo apt install -y apptainer`
            - OK`apptainer --version`, `singularity --version`