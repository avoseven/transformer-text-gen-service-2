
def model_init(tokenizer, m_cfg, device='cpu'):
    # 2. モデルの初期化
    if m_cfg['model_name'] == 'scratch':
        # 自作モデル
        #from models.transformer import Transformer, TransformerConfig
        from models.transformer import Transformer, TransformerConfig
        model_config = TransformerConfig(
            vocab_size=tokenizer.vocab_size,
            block_size=m_cfg['block_size'],
            n_layer=m_cfg['n_layer'],
            n_head=m_cfg['n_head'],
            n_embd=m_cfg['n_embd'],
            dropout=m_cfg['dropout'],
            bias=m_cfg['bias']
        )
        model = Transformer(model_config).to(device)

    else:
        # 公開モデル対応（例：itarutomy/llm_workshop_hands_on_gpt-model）
        from transformers import AutoModelForCausalLM
        model_config = None
        model = AutoModelForCausalLM.from_pretrained(m_cfg['model_name']).to(device)

    return model, model_config

def optimizer_init(t_cfg, model, model_name='scratch'):
    # 3. オプティマイザの初期化
    if model_name == 'scratch':
        # 自作モデル，構造が単純かつ事前学習がないので，Weight Decayを細かく制御
        optimizer = model.configure_optimizers(
            t_cfg['weight_decay'], t_cfg['learning_rate'], 
            (t_cfg['beta1'], t_cfg['beta2'])
        )
    else:
        # 公開モデル対応，構造が複雑で事前学習により安定しているためWeight Decayは一律
        from torch.optim import AdamW
        optimizer = AdamW(
            model.parameters(), 
            lr=t_cfg['learning_rate'], 
            weight_decay=t_cfg['weight_decay'], 
            betas=(t_cfg['beta1'], t_cfg['beta2'])
        )
    return optimizer