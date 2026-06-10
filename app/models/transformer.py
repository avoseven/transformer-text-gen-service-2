import math
import torch
import torch.nn as nn
from torch.nn import functional as F
from dataclasses import dataclass

@dataclass
class TransformerConfig:
    """モデルのハイパーパラメータ設定"""
    vocab_size: int = 8000     # 語彙サイズ（SentencePieceで作成したもの）
    block_size: int = 256      # 最大シーケンス長（コンテキスト窓）
    n_layer: int = 6           # Transformerブロックの数
    n_head: int = 8            # Multi-head attentionのヘッド数
    n_embd: int = 384          # 埋め込み次元数
    dropout: float = 0.1       # ドロップアウト率
    bias: bool = True          # LayerNormやLinear層にバイアスを含めるか

class CausalSelfAttention(nn.Module):
    """
    マスク付きMulti-head Self-Attention層。
    未来のトークンを見ないように（Causal）処理を行う。
    """
    def __init__(self, config):
        super().__init__()
        assert config.n_embd % config.n_head == 0   # ① 割り切れるかチェック
        # Key, Query, Valueを一気に計算するためのLinear層
        self.c_attn = nn.Linear(config.n_embd, 3 * config.n_embd, bias=config.bias)
        # 出力投影用, 最後に形を整える Linear 層
        self.c_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        # 正則化
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)
        self.n_head = config.n_head
        self.n_embd = config.n_embd
        self.dropout = config.dropout
        
        # Causal mask（下三角行列）の作成
        # block_size × block_size の行列で、未来のトークンを -inf にするためのマスク
        self.register_buffer("bias", torch.tril(torch.ones(config.block_size, config.block_size))
                                        .view(1, 1, config.block_size, config.block_size))

    def forward(self, x, attention_mask=None):
        # B:Batch size, T:Time (Seq len), C:Channel (n_embd)
        B, T, C = x.size() # batch size, sequence length, embedding dimensionality (n_embd)

        # Q, K, V を計算
        q, k, v  = self.c_attn(x).split(self.n_embd, dim=2)
        k = k.view(B, T, self.n_head, C // self.n_head).transpose(1, 2) # (B, nh, T, hs)
        q = q.view(B, T, self.n_head, C // self.n_head).transpose(1, 2) # (B, nh, T, hs)
        v = v.view(B, T, self.n_head, C // self.n_head).transpose(1, 2) # (B, nh, T, hs)

        # Scaled Dot-Product Attention
        # (B, nh, T, hs) x (B, nh, hs, T) -> (B, nh, T, T)
        att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(k.size(-1)))
        
        # 1. Causal mask（未来の情報遮断）
        att = att.masked_fill(self.bias[:,:,:T,:T] == 0, float('-inf'))
        
        # 2. Attention mask（パディングの遮断）
        if attention_mask is not None:
            # attention_mask: (B, T) -> (B, 1, 1, T) に変形して適用
            att = att.masked_fill(attention_mask.view(B, 1, 1, T) == 0, float('-inf'))

        att = F.softmax(att, dim=-1)
        att = self.attn_dropout(att)
        y = att @ v # (B, nh, T, T) x (B, nh, T, hs) -> (B, nh, T, hs)
        
        # 全てのヘッドの結果を結合
        y = y.transpose(1, 2).contiguous().view(B, T, C)

        # 出力の投影
        y = self.resid_dropout(self.c_proj(y))
        return y

class MLP(nn.Module):
    """
    Position-wise Feed-Forward Network。
    各トークンに対して独立に適用される2層の全結合層。
    """
    def __init__(self, config):
        super().__init__()
        self.c_fc    = nn.Linear(config.n_embd, 4 * config.n_embd, bias=config.bias)
        self.gelu    = nn.GELU() # 活性化関数（GPT-2等で標準的）
        self.c_proj  = nn.Linear(4 * config.n_embd, config.n_embd, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        x = self.c_fc(x)
        x = self.gelu(x)
        x = self.c_proj(x)
        x = self.dropout(x)
        return x

class Block(nn.Module):
    """
    Transformerの基本単位（1レイヤー）。
    LayerNorm -> Attention -> 残差接続 -> LayerNorm -> MLP -> 残差接続
    """
    def __init__(self, config):
        super().__init__()
        self.ln_1 = nn.LayerNorm(config.n_embd)
        self.attn = CausalSelfAttention(config)
        self.ln_2 = nn.LayerNorm(config.n_embd)
        self.mlp = MLP(config)

    def forward(self, x, attention_mask=None):
        # Pre-norm形式を採用（近年の標準）
        x = x + self.attn(self.ln_1(x), attention_mask=attention_mask)
        x = x + self.mlp(self.ln_2(x))
        return x

class Transformer(nn.Module):
    """
    Transformer Decoder全体のモデル。
    """
    def __init__(self, config):
        super().__init__()
        self.config = config

        self.transformer = nn.ModuleDict(dict(
            wte = nn.Embedding(config.vocab_size, config.n_embd), # Word Token Embedding
            wpe = nn.Embedding(config.block_size, config.n_embd), # Word Position Embedding
            drop = nn.Dropout(config.dropout),
            h = nn.ModuleList([Block(config) for _ in range(config.n_layer)]),
            ln_f = nn.LayerNorm(config.n_embd), # 最終LayerNorm
        ))
        # 最終的な単語予測用のヘッド
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        
        # 重みのタイイング（Embeddingと出力層の重みを共有してパラメータ節約）
        self.transformer.wte.weight = self.lm_head.weight

        # 重みの初期化
        self.apply(self._init_weights)
        print(f"Number of parameters: {self.get_num_params()/1e6:.2f}M")

    def get_num_params(self):
        """パラメータ数を計算"""
        n_params = sum(p.numel() for p in self.parameters())
        return n_params

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def configure_optimizers(self, weight_decay, learning_rate, betas):
        # 全てのパラメータを取得
        param_dict = {pn: p for pn, p in self.named_parameters()}
        # 勾配が必要なものだけに絞る
        param_dict = {pn: p for pn, p in param_dict.items() if p.requires_grad}
        
        # 重み減衰を適用するグループと適用しないグループに分ける
        # 2次元以上の重み（Linearのweightなど）は適用する
        # 1次元の重み（biasやLayerNormのweightなど）は適用しない
        decay_params = [p for n, p in param_dict.items() if p.dim() >= 2]
        nodecay_params = [p for n, p in param_dict.items() if p.dim() < 2]
        
        optim_groups = [
            {'params': decay_params, 'weight_decay': weight_decay},
            {'params': nodecay_params, 'weight_decay': 0.0}
        ]
        
        num_decay_params = sum(p.numel() for p in decay_params)
        num_nodecay_params = sum(p.numel() for p in nodecay_params)
        print(f"num decayed parameter tensors: {len(decay_params)}, with {num_decay_params:,} parameters")
        print(f"num non-decayed parameter tensors: {len(nodecay_params)}, with {num_nodecay_params:,} parameters")
        
        # AdamW オプティマイザを作成
        optimizer = torch.optim.AdamW(optim_groups, lr=learning_rate, betas=betas)
        return optimizer

    #def forward(self, idx, targets=None, attention_mask=None):
    def forward(self, input_ids, labels=None, attention_mask=None):
        device = input_ids.device
        b, t = input_ids.size()
        assert t <= self.config.block_size, f"Cannot forward sequence of length {t}, block size is only {self.config.block_size}"
        
        # 位置情報の作成
        pos = torch.arange(0, t, dtype=torch.long, device=device) # (t)

        # トークン埋め込みと位置埋め込みを合体
        tok_emb = self.transformer.wte(input_ids) # (b, t, n_embd)
        pos_emb = self.transformer.wpe(pos) # (t, n_embd)
        x = self.transformer.drop(tok_emb + pos_emb)

        # Transformerブロックを順に適用
        for block in self.transformer.h:
            x = block(x, attention_mask=attention_mask)
        x = self.transformer.ln_f(x)

        if labels is not None:
            # 学習時：Loss（CrossEntropy）も計算
            logits = self.lm_head(x)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), labels.view(-1), ignore_index=-100)
        else:
            # 生成時：最後のトークンの予測結果（Logits）のみ返す
            logits = self.lm_head(x[:, [-1], :]) # (b, 1, vocab_size)
            loss = None

        return logits, loss

if __name__ == "__main__":
    # モデルのテスト
    config = TransformerConfig()
    model = Transformer(config)
    
    # ダミー入力 (Batch=2, Seq=16)
    idx = torch.randint(0, config.vocab_size, (2, 16))
    targets = torch.randint(0, config.vocab_size, (2, 16))
    
    logits, loss = model(idx, targets)
    print(f"Logits shape: {logits.shape}")
    print(f"Loss: {loss.item() if loss else 'N/A'}")
