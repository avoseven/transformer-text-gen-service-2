# app/gradio.py

import gradio as gr
from generate import Generator

# Generatorクラスを読み込み
generator = Generator()

def gradio_generate(prompt, max_length, temperature, top_k):
    generated_text = generator.generate(
        prompt=prompt,
        max_new_tokens=max_length,
        temperature=temperature,
        top_k=top_k
    )
    return generated_text

# 「どんな入力を受け取って、どんな関数を実行し、どんな出力を表示するか」 を定義
demo = gr.Interface(
    fn=gradio_generate, # 実行する関数
    # 入力UI（テキストボックスやスライダーなど）
    inputs=[
        gr.Textbox(label="プロンプト", placeholder="文章の続きを入力してください"),
        gr.Slider(minimum=10, maximum=200, value=50, step=10, label="最大長"),
        gr.Slider(minimum=0.1, maximum=2.0, value=1.0, step=0.1, label="温度"),
        gr.Slider(minimum=1, maximum=100, value=50, step=1, label="top_k")
    ],
    outputs=gr.Textbox(label="生成結果"),   # 出力UI（テキストボックスなど）
    title="Transformer文章生成モデル",  # ページタイトル
    description="プロンプトを入力すると、文章の続きを生成します。"  # ページの説明文
)

if __name__ == "__main__":
    # Gradioサーバの起動
    # server_name="0.0.0.0"：すべてのIPアドレスからアクセス可能
    # server_port=7860：ポート番号（http://localhost:7860）
    # share=False：公開URLを作成しない（ローカルでのみアクセス可能）
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)