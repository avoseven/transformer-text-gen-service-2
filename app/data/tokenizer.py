import sentencepiece as spm
import torch
import os

class JapaneseTokenizer:
    """
    SentencePieceモデルを使用した日本語用トークナイザークラス。
    """
    def __init__(self, model_path: str = "data/tokenizer/news_spm.model"):
        """
        Args:
            model_path: 学習済みのSentencePieceモデルファイルのパス。
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"SentencePiece model not found at {model_path}. Please train it first.")
        
        self.sp = spm.SentencePieceProcessor()
        self.sp.load(model_path)
        
        # 特殊トークンのIDを取得
        self._pad_id = self.sp.pad_id()
        self._bos_id = self.sp.bos_id()
        self._eos_id = self.sp.eos_id()
        self._unk_id = self.sp.unk_id()

    def encode(self, text: str, max_length: int = None, padding: bool = False, truncation: bool = True):
        """
        テキストをトークンIDに変換する。
        HuggingFace Tokenizerのインターフェースに寄せて実装。
        """
        # BOS/EOSを付与してエンコード
        ids = [self._bos_id] + self.sp.encode_as_ids(text) + [self._eos_id]
        
        # 切り捨て
        if truncation and max_length is not None:
            ids = ids[:max_length]
            
        attention_mask = [1] * len(ids)
        
        # パディング
        if padding and max_length is not None:
            padding_len = max_length - len(ids)
            if padding_len > 0:
                ids += [self._pad_id] * padding_len
                attention_mask += [0] * padding_len
                
        return {
            "input_ids": torch.tensor([ids]),
            "attention_mask": torch.tensor([attention_mask])
        }

    def __call__(self, text: str, max_length: int = None, padding: str = "max_length", truncation: bool = True, **kwargs):
        """
        クラスを関数のように呼び出した際の挙動（encodeのラッパー）。
        Datasetクラスなどからの呼び出しに対応。
        """
        # padding="max_length" の場合は padding=True として扱う
        do_padding = (padding == "max_length" or padding is True)
        return self.encode(text, max_length=max_length, padding=do_padding, truncation=truncation)

    def decode(self, token_ids, skip_special_tokens: bool = True):
        """トークンIDをテキストに変換する"""
        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.tolist()
            
        if skip_special_tokens:
            # 特殊トークンを除外
            special_ids = {self._pad_id, self._bos_id, self._eos_id, self._unk_id}
            token_ids = [tid for tid in token_ids if tid not in special_ids]
            
        return self.sp.decode_ids(token_ids)

    @property
    def vocab_size(self) -> int:
        """語彙サイズを返す"""
        return self.sp.get_piece_size()

    @property
    def pad_token_id(self) -> int:
        return self._pad_id

    @property
    def bos_token_id(self) -> int:
        return self._bos_id

    @property
    def eos_token_id(self) -> int:
        return self._eos_id

if __name__ == "__main__":
    # 動作確認
    tokenizer = JapaneseTokenizer()
    text = "吾輩は猫である。名前はまだ無い。"
    
    encoded = tokenizer.encode(text, max_length=20, padding=True)
    print(f"Text: {text}")
    print(f"Encoded IDs: {encoded['input_ids']}")
    print(f"Attention Mask: {encoded['attention_mask']}")
    print(f"Vocab size: {tokenizer.vocab_size}")
    
    decoded = tokenizer.decode(encoded['input_ids'][0])
    print(f"Decoded text: {decoded}")
