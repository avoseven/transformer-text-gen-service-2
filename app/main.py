from fastapi import FastAPI # FastAPIのメインクラス。Webフレームワークそのもの
from pydantic import BaseModel  # リクエスト・レスポンスの型（スキーマ）を定義するために使います
# FastAPIは内部でpydanticに依存しているので、pip install fastapi でpydanticも一緒にインストールされます
from generate import Generator

app = FastAPI() # FastAPIインスタンスの作成
# この app に対してルート（エンドポイント）を追加していきます

generator = Generator() # Server起動時に一度だけ読み込む

class GenerateRequest(BaseModel):   # POST /generate で受け取るデータの型を定義
    prompt: str
    max_new_tokens: int = 50
    temperature: float = 1.0
    top_k: int = 50

class GenerateResponse(BaseModel):  # 返すデータの型を定義
    prompt: str
    generated_text: str
    temperature: float
    top_k: int

'''
pydanticを使うことで、FastAPIが自動的に：

リクエストのバリデーション（型チェック）
ドキュメント生成（Swagger UI）
シリアライズ／デシリアライズ

を行ってくれます。
'''

#  ルート（エンドポイント）の定義
'''
ルート1：GET /
- @app.get("/")：GETリクエストで / にアクセスしたときの処理を定義
- read_root 関数が呼ばれ、{"message":"Hello World"} を返す
'''
@app.get("/")
def read_root():
    return {"message": "Transformer文章生成API"}

'''
ルート2：POST /generate
- @app.post("/generate", response_model=GenerateResponse)：POSTリクエストで /generate にアクセスしたときの処理を定義response_model=GenerateResponse で「返すデータの型」を指定
- generate_text 関数の引数 request は GenerateRequest 型→ FastAPIがリクエストボディを自動でパースしてくれる
- 今は固定の文章を返していますが、後でここにモデル呼び出しを追加します
- 返り値は GenerateResponse のインスタンス→ FastAPIが自動でJSONに変換して返す
'''
@app.post("/generate", response_model=GenerateResponse)
def generate_text(request: GenerateRequest):
    # 今は固定のレスポンスを返す（後でモデルを呼び出す）
    #generated_text = "これは生成された文章です（仮）"
    # ちゃんと生成させる
    generated_text = generator.generate(
        request.prompt, max_new_tokens=request.max_new_tokens, temperature=request.temperature, top_k=request.top_k
    )

    return GenerateResponse(
        prompt=request.prompt,
        generated_text=generated_text,
        temperature=request.temperature,
        top_k=request.top_k,
    )