# ERP Rural — Sistema de Gestão Agropecuária com IA

Sistema de gestão rural com assistente de inteligência artificial, integrando Flask,
SQLAlchemy e Ollama com tool calling (loop ReAct). A IA nunca inventa dados — ela sempre
consulta o banco antes de responder.

## Requisitos

- Python 3.10+
- Ollama instalado com o modelo `qwen2.5:7b` disponível (`ollama pull qwen2.5:7b`)
- pip

## Instalação e Uso

```bash
# 1. Criar e ativar ambiente virtual (Ubuntu 24.04 exige venv)
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Inicializar banco com dados de exemplo
python init_db.py

# 4. Iniciar o servidor
python app.py

# 5. Acessar em
# http://localhost:5000
```

## Exemplos de Perguntas

- "Quantos animais temos no total?"
- "Cadastra 50 bovinos da raça nelore com status ativo"
- "Qual o valor total das transações de entrada?"

## Estrutura

```
projeto-claude-erp-gado/
├── app.py              # Flask: rotas e segurança do executor Python
├── config.py           # Configurações centralizadas
├── init_db.py          # Cria tabelas e insere dados de exemplo
├── requirements.txt
├── README.md
├── ia/
│   ├── __init__.py
│   ├── orquestrador.py # Loop ReAct com Ollama (qwen2.5:7b)
│   ├── ferramentas.py  # JSON Schema das 5 ferramentas (tool calling)
│   └── executor.py     # Mapeia nome da ferramenta → função CRUD
├── db/
│   ├── __init__.py
│   ├── models.py       # Modelos SQLAlchemy: Produto, Animal, Transacao
│   └── crud.py         # Funções CRUD chamadas pelas ferramentas
├── static/
│   ├── style.css       # Layout de chat responsivo, sem dependências externas
│   └── app.js          # Renderização de partes: texto, html, python
└── templates/
    └── index.html      # Interface de chat
```

## Arquitetura

```
Usuário → [Front-end HTML/JS]
             ↓ POST /api/chat
          [Flask app.py]
             ↓
          [ia/orquestrador.py]  ← loop ReAct (máx. 10 etapas)
             ↓ tool call
          [ia/executor.py]
             ↓
          [db/crud.py]  →  SQLite (sistema.db)
```
