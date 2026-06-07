# CLAUDE.md — ERP Rural com IA

Contexto completo do projeto para o assistente Claude Code. Leia este arquivo antes de qualquer tarefa.

## Visão geral

ERP de gestão rural com interface de chat. O usuário conversa com um LLM local (Ollama) que usa **tool calling** para consultar/modificar um banco SQLite. A resposta final é renderizada no frontend em blocos (texto, HTML, Python).

- **Backend**: Flask 3.x + SSE (Server-Sent Events) para streaming token a token
- **LLM**: `qwen2.5:7b` via Ollama (CPU-only, sem GPU)
- **Banco**: SQLite + SQLAlchemy 2.0
- **Frontend**: JavaScript puro com `fetch()` + `ReadableStream`

## Estrutura de arquivos

```
app.py              — Flask: rotas, SSE endpoint, StreamingHandler, warmup do modelo
config.py           — OLLAMA_MODEL, DATABASE_URL, OLLAMA_OPTIONS (num_ctx, num_thread, temperature)
init_db.py          — Cria tabelas e insere dados iniciais (5 produtos, 5 animais, 5 transações)
ia/
  orquestrador.py   — Loop ReAct com streaming: _streamar_chat(), _streamar_com_heartbeat(), orquestrar_stream()
  ferramentas.py    — Definição das 5 tools em formato OpenAI: consulta, cadastra, atualiza, deleta, responda
  executor.py       — Mapeia nome da tool → função CRUD com SessionLocal
db/
  models.py         — SQLAlchemy models: Produto, Animal, Transacao + engine + SessionLocal
  crud.py           — consultar(), cadastrar(), atualizar(), deletar() — nunca levantam exceção ao AI
static/
  app.js            — SSE consumer (fetch + ReadableStream), processarEvento(), historico[]
  style.css         — Layout do chat, .stream-texto, .log-item.ativo/concluido, .bloco-html
templates/
  index.html        — HTML do chat
```

## Como rodar

```bash
# Primeira vez: criar banco com dados de exemplo
.venv/bin/python init_db.py

# Iniciar servidor (use sempre python app.py, não flask run)
.venv/bin/python app.py
# → http://127.0.0.1:5000
```

O servidor usa `use_reloader=False` (importante para SSE). Reinicie manualmente após mudanças em código.

## Banco de dados

### Tabela `produto`
| col | tipo | exemplo |
|-----|------|---------|
| id | Integer PK | 1 |
| nome | String | "Ração Bovina Premium" |
| categoria | String | "Alimentação" / "Veterinário" / "Suplemento" / "Reprodução" |
| quantidade | Integer | 500 |
| preco_unit | Float | 2.50 |
| atualizado_em | DateTime | — |

### Tabela `animal`
| col | tipo | exemplo |
|-----|------|---------|
| id | Integer PK | 1 |
| especie | String | "Bovino" / "Suíno" / "Ave de Corte" / "Ovino" / "Equino" |
| raca | String | "Nelore" / "Landrace" / "Cobb 500" |
| quantidade | Integer | 120 |
| status | String | "ativo" |
| atualizado_em | DateTime | — |

### Tabela `transacao`
| col | tipo | exemplo |
|-----|------|---------|
| id | Integer PK | 1 |
| tipo | String | "entrada" / "saida" |
| descricao | String | "Venda de gado gordo" |
| valor | Float | 75000.00 |
| data | DateTime | — |

## Tools disponíveis

O modelo pode chamar 5 ferramentas:

| Tool | Parâmetros | Quando usar |
|------|-----------|-------------|
| `consulta` | table, col, fun (soma/contagem/media/lista/maximo/minimo) | SEMPRE ao buscar dados |
| `cadastra` | table, dados{} | Criar novo registro |
| `atualiza` | table, id, dados{} | Editar registro existente |
| `deleta` | table, id | Remover registro |
| `responda` | parts[] | Resposta final ao usuário |

`responda.parts` é um array de blocos: `{tipo: "texto", conteudo: "..."}`, `{tipo: "html", conteudo: "<table>..."}`, `{tipo: "python", conteudo: "2+2"}`.

## Fluxo SSE (streaming)

```
POST /api/chat
  └─ generate() generator → Flask Response(mimetype="text/event-stream")
       └─ orquestrar_stream() → eventos:
            gerando       → frontend mostra "Gerando resposta…"
            heartbeat     → keep-alive a cada 8s (ignorado no frontend)
            token         → texto sendo construído progressivamente no balão
            ferramenta_inicio / ferramenta_fim → log de ferramenta com pulsação
            partes        → resposta final renderizável (encerra o stream)
            erro          → mensagem de erro no balão
```

### Por que StreamingHandler?
O Werkzeug dev server usa `socket.makefile('wb')` com buffer ~8 KB. Eventos SSE de ~50 bytes se acumulam e só chegam ao browser quando a conexão fecha. `StreamingHandler` substitui `self.wfile` por `makefile("wb", 0)` (sem buffer), forçando cada `yield` a chegar imediatamente.

### Por que _streamar_com_heartbeat?
O modelo pode ficar 1–2 minutos processando antes do primeiro token. Sem heartbeats, proxies e alguns browsers podem fechar a conexão SSE. A função roda `_streamar_chat()` em thread separada e emite `("heartbeat", None)` a cada 8 s enquanto aguarda.

## Configuração de performance (CPU)

`config.py → OLLAMA_OPTIONS`:
- `num_ctx: 2048` — janela de contexto reduzida (padrão do qwen2.5:7b é 32768, muito lento na CPU)
- `num_thread: os.cpu_count()` — usa todos os núcleos (i5-1334U tem 10)
- `temperature: 0.1` — temperatura baixa melhora a aderência ao system prompt e o uso de tools

O modelo é mantido na RAM com `keep_alive=-1` (carregado no startup via `_aquecer_modelo()`). Descarregado com `atexit` ao encerrar o servidor.

## Problemas conhecidos e suas soluções

### Modelo não usa ferramentas
**Causa**: `qwen2.5:7b` com temperatura alta (~0.7) não segue system prompt de forma confiável. Com perguntas como "o que tem cadastrado?" retorna `'\n'` em vez de chamar `consulta`.
**Solução**: `temperature: 0.1` em OLLAMA_OPTIONS + system prompt com exemplos explícitos de chamadas de ferramenta.

### Modelo retorna JSON como texto em vez de chamar `responda`
**Causa**: O modelo às vezes retorna `[{"tipo":"texto","conteudo":"..."}]` como texto puro.
**Solução**: `_parse_fallback()` em `orquestrador.py` detecta este padrão e converte para o formato de `partes`.

### SSE não chegava ao browser em tempo real
**Causa**: Buffer do socket do Werkzeug (~8 KB). Tokens de 50 bytes ficavam presos até a conexão fechar.
**Solução**: `StreamingHandler` com `wfile = connection.makefile("wb", 0)`.

### Demora de 2+ minutos por requisição (resolvido)
**Causa**: Modelo sendo carregado/descarregado a cada requisição.
**Solução**: `keep_alive=-1` no startup + `_aquecer_modelo()`.

### `ast.Mul` AttributeError em Python 3.12
**Causa**: `ast.Mul` não existe no Python 3.12; o nó chama-se `ast.Mult`.
**Solução**: Corrigido para `ast.Mult` em `app.py SAFE_NODES`.

## Decisões de arquitetura

- **`use_reloader=False`**: O reloader do Werkzeug envolve o app em middleware extra que bufferiza SSE.
- **`stream=True` no ollama.chat**: Habilita streaming token a token do modelo.
- **Fallback JSON parser**: Necessário porque o `qwen2.5:7b` nem sempre chama a tool `responda` — às vezes retorna o JSON diretamente no conteúdo de texto.
- **`with SessionLocal() as session:`**: Garante que a sessão do SQLAlchemy é fechada mesmo em caso de erro.
- **Executor nunca levanta exceção**: `crud.py` captura tudo e retorna `{"erro": "..."}`, mantendo o loop do modelo operacional.

## Dependências principais

```
flask, flask-cors
ollama>=0.6.2       (Python SDK do Ollama)
sqlalchemy>=2.0
werkzeug            (vem com Flask)
```

Verificar: `.venv/bin/pip list | grep -E "flask|ollama|sqlalchemy"`
