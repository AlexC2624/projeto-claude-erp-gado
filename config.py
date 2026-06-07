import os

OLLAMA_MODEL   = "qwen2.5:7b"
DATABASE_URL   = "sqlite:///sistema.db"
DEBUG          = True
SECRET_KEY     = "sistema-ia-dev"
MAX_LOOP_STEPS = 10

# Opções de inferência — críticas para CPU sem GPU
OLLAMA_OPTIONS = {
    # Janela de contexto: padrão do qwen2.5:7b é 32 768 tokens,
    # o que exige cache KV enorme e torna a CPU lenta.
    # 2048 é mais que suficiente para o histórico deste app.
    "num_ctx":    2048,

    # Threads de CPU: usa todos os núcleos disponíveis.
    # i5-1334U tem 10 núcleos (6P + 4E).
    "num_thread": os.cpu_count() or 4,

    # Temperatura baixa melhora aderência ao system prompt e uso de ferramentas.
    # Com temperatura padrão (~0.7) o qwen2.5:7b ignora tools com frequência.
    "temperature": 0.1,
}
