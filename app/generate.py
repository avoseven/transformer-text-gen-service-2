import os
import yaml
import torch
import torch.nn.functional as F
#from models.transformer import Transformer, TransformerConfig
from data.tokenizer import JapaneseTokenizer
import argparse
from utils import model_init

# FastAPIから呼び出すためのクラスにリファクタリング
class Generator:
    def __init__(self, ckpt=None):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        config = load_config()
        self.m_cfg = config['model']
        self.t_cfg = config['train']
        self.p_cfg = config['paths']

        # Tokenizer
        self.tokenizer = JapaneseTokenizer(self.p_cfg['tokenizer_model'])

        # チェックポイントの決定
        try:
            checkpoint = select_checkpoint(config['paths']['checkpoint_dir'], self.device, ckpt)
            #checkpoint = select_checkpoint(config['paths']['checkpoint_dir'], self.device)
        except FileNotFoundError as e:
            #print(e)
            #return  # プログラムを終了
            raise e # returnするとInstance生成が不完全になるらしいので

        # Model
        self.model, _ = model_init(self.tokenizer, self.m_cfg, device=self.device)
        missing_keys, unexpected_keys = self.model.load_state_dict(checkpoint['model_state_dict'])

    def generate(self, prompt, max_new_tokens=50, temperature=1.0, top_k=None):
        return generate(self.model, self.tokenizer, prompt, max_new_tokens=max_new_tokens, temperature=temperature, top_k=top_k, device=self.device)

def load_config(config_path="configs/model_config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

@torch.no_grad()
def generate(model, tokenizer, prompt, max_new_tokens=50, temperature=1.0, top_k=None, device='cpu'):
    """
    モデルを使用してテキストを生成する。
    
    Args:
        model: Transformerモデル
        tokenizer: JapaneseTokenizerインスタンス
        prompt: 入力テキスト
        max_new_tokens: 生成する最大トークン数
        temperature: サンプリングの温度。高いほど多様、低いほど決定的。
        top_k: Top-KサンプリングのK。上位K個のトークンからのみサンプリングする。
        device: 使用デバイス
    """
    model.eval()
    
    # プロンプトをトークナイズ
    #encoded = tokenizer.encode(prompt)
    encoded = tokenizer(
        prompt,
        padding=False,
        truncation=True,
        max_length=model.config.block_size if hasattr(model.config, 'block_size') else None,    # HF ModelはNoneでも可らしい
        return_tensors='pt'
    )
    idx = encoded['input_ids'].to(device) # (1, seq_len)
    # Debug
    #print(idx)

    # プロンプトの末尾がEOS（通常2）の場合、それを削除してから生成を開始する
    if idx[0, -1] == tokenizer.eos_token_id:
        idx = idx[:, :-1]
    
    # Debug
    #print(idx)

    # 生成ループ
    if hasattr(model, 'generate') and callable(getattr(model, 'generate')):
        # HFモデルの生成ロジック
        generated_ids = model.generate(
            input_ids=idx,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
        )
        idx = generated_ids
        # Debug
        #print(idx)
    else:
        # scratchモデルの生成ロジック
        for _ in range(max_new_tokens):
            # コンテキスト窓（block_size）を超えないようにクロップ
            #idx_cond = idx if idx.size(1) <= model.config.block_size else idx[:, -model.config.block_size:]
            if hasattr(model.config, 'block_size'):
                block_size = model.config.block_size
            elif hasattr(model.config, 'max_position_embeddings'):
                block_size = model.config.max_position_embeddings
            else:
                block_size = 1024  # デフォルト値
            idx_cond = idx if idx.size(1) <= block_size else idx[:, -block_size:]
        
            # モデルのフォワード (targets=Noneなので最後のトークンの予測結果のみ返ってくる)
            logits, _ = model(idx_cond) # logits: (1, 1, vocab_size)
        
            # 最後のタイムステップのロジットを取り出し、温度を適用
            logits = logits[:, -1, :] / temperature
        
            # Top-K フィルタリング
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float('Inf')
            
            # 確率分布に変換
            probs = F.softmax(logits, dim=-1)
        
            # サンプリング
            idx_next = torch.multinomial(probs, num_samples=1)
        
            # シーケンスに追加
            idx = torch.cat((idx, idx_next), dim=1)
        
            # EOSトークンが出たら終了
            if idx_next.item() == tokenizer.eos_token_id:
                break
            
    # 特殊トークンを除いてデコード
    return tokenizer.decode(idx[0])

def parse_arguments():
    parser = argparse.ArgumentParser(description='Transformer Decoder テキスト生成')
    parser.add_argument('--prompt', type=str, default="今日", help='生成の起点となるテキスト')
    parser.add_argument('--max_new_tokens', type=int, default=100, help='追加で生成する最大トークン数')
    parser.add_argument('--temperature', type=float, default=0.8, help='サンプリングの温度 (0.0~, デフォルト: 0.8)')
    parser.add_argument('--top_k', type=int, default=50, help='Top-KサンプリングのK (デフォルト: 50)')
    parser.add_argument('--checkpoint', type=str, default=None, help='使用するチェックポイントのパス (未指定なら最新を使用)')
    return parser.parse_args()

def select_checkpoint(checkpoint_dir, device='cpu', user_checkpoint_path=None):
    # チェックポイントの決定
    if user_checkpoint_path is None:
        ckpt_files = [f for f in os.listdir(checkpoint_dir) if f.endswith('.pt')]
        if not ckpt_files:
            print(f"No checkpoints found in {checkpoint_dir}")
            #return
            raise FileNotFoundError(f"No checkpoints found in {checkpoint_dir}")
        # ファイルの更新日時が最新のものを取得
        ckpt_files.sort(key=lambda x: os.path.getmtime(os.path.join(checkpoint_dir, x)), reverse=True)
        checkpoint_path = os.path.join(checkpoint_dir, ckpt_files[0])
    else:
        checkpoint_path = user_checkpoint_path
    
    print(f"Using device: {device}")
    print(f"Loading checkpoint: {checkpoint_path}")
    #return torch.load(checkpoint_path, map_location=device)
    return torch.load(checkpoint_path, map_location=device, weights_only=False)

def main():
    args = parse_arguments()

    # 設定のロード
    config = load_config()
    m_cfg = config['model']
    t_cfg = config['train']
    p_cfg = config['paths']
    
    # デバイスの設定
    if torch.cuda.is_available():
        device = 'cuda'
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'
    
    # トークナイザーのロード
    #tokenizer = JapaneseTokenizer(config['paths']['tokenizer_model'])
    if m_cfg['model_name'] == 'scratch':
        # 自作モデル
        tokenizer = JapaneseTokenizer(p_cfg['tokenizer_model'])
    else:
        # 公開モデル
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(m_cfg['model_name'])
    
    # チェックポイントの決定
    #checkpoint = select_checkpoint(config['paths']['checkpoint_dir'], device, args.checkpoint)
    try:
        checkpoint = select_checkpoint(config['paths']['checkpoint_dir'], device, args.checkpoint)
    except FileNotFoundError as e:
        print(e)
        return  # プログラムを終了
    
    # モデルの初期化と重みのロード
    # TransformerConfigの代わりにcheckpointからconfigを復元
    model, _model_config = model_init(tokenizer, m_cfg, device)
    
    #model.load_state_dict(checkpoint['model_state_dict'])
    missing_keys, unexpected_keys = model.load_state_dict(checkpoint['model_state_dict'])
    #print("missing_keys:", missing_keys)
    #print("unexpected_keys:", unexpected_keys)
    
    print(f"\nPrompt: {args.prompt}")
    print("-" * 30)
    
    # テキスト生成の実行
    generated_text = generate(
        model, 
        tokenizer, 
        args.prompt, 
        max_new_tokens=args.max_new_tokens, 
        temperature=args.temperature, 
        top_k=args.top_k,
        device=device
    )
    
    print(generated_text)
    print("-" * 30)

if __name__ == "__main__":
    main()
