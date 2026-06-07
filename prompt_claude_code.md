# Prompt — Sistema IA com Tool Calling (Flask + Ollama)

## Contexto do ambiente

- OS: Ubuntu 24.04 LTS
- CPU: Intel Core i5-1334U (10 núcleos, sem GPU dedicada — inferência 100% CPU)
- RAM: 16 GB DDR4 — use processamento leve e sem workers paralelos
- Ollama 0.9.0 instalado, modelo disponível: `llama3.2:latest`
- Python 3.x + pip disponíveis
- Editor: VS Code

---

## Objetivo

Crie um sistema completo chamado `sistema-ia/` com três camadas:

1. **Back-end** — Flask + SQLAlchemy + SQLite com funções CRUD reais
2. **IA Orquestradora** — Ollama com `llama3.2:latest` usando tool calling (loop ReAct)
3. **Front-end** — Interface de chat HTML/JS que renderiza texto, HTML e saída Python

A IA nunca calcula nem inventa dados. Ela sempre chama ferramentas do back-end
para obter valores reais e só responde quando tem todos os dados em mãos.

---

## Estrutura do projeto

```
sistema-ia/
├── app.py                  # Flask: rotas principais
├── config.py               # Configurações centralizadas
├── init_db.py              # Cria tabelas e insere dados de exemplo
├── requirements.txt
├── README.md
│
├── ia/
│   ├── __init__.py
│   ├── orquestrador.py     # Loop de tool calling com Ollama
│   ├── ferramentas.py      # Definições JSON schema das ferramentas
│   └── executor.py         # Mapeia nome → função Python real
│
├── db/
│   ├── __init__.py
│   ├── models.py           # Modelos SQLAlchemy
│   └── crud.py             # Funções CRUD chamadas pelas ferramentas
│
├── static/
│   ├── style.css
│   └── app.js              # Lógica de chat e renderização de partes
│
└── templates/
    └── index.html
```

---

## config.py

```python
OLLAMA_MODEL   = "qwen2.5:7b"
DATABASE_URL   = "sqlite:///sistema.db"
DEBUG          = True
SECRET_KEY     = "sistema-ia-dev"
MAX_LOOP_STEPS = 10   # limite de segurança para o loop de ferramentas
```

---

## db/models.py — Tabelas de exemplo

Crie três tabelas com SQLAlchemy (Base declarativa):

```
Produto:    id, nome, categoria, quantidade (int), preco_unit (float), atualizado_em
Animal:     id, especie, raca, quantidade (int), status, atualizado_em
Transacao:  id, tipo ("entrada"/"saida"), descricao, valor (float), data
```

---

## db/crud.py — Funções reais do back-end

Implemente as seguintes funções que serão chamadas pelo executor da IA.
Todas recebem `session` (SQLAlchemy Session) como primeiro argumento:

```python
def consultar(session, table: str, col: str, fun: str) -> any:
    """
    fun pode ser: "soma", "contagem", "media", "lista", "maximo", "minimo"
    Retorna valor escalar ou lista de dicts (para "lista").
    Nunca levanta exceção para a IA — retorna {"erro": str} em caso de falha.
    """

def cadastrar(session, table: str, dados: dict) -> dict:
    """Insere novo registro. Retorna o registro criado como dict."""

def atualizar(session, table: str, id: int, dados: dict) -> dict:
    """Atualiza registro pelo id. Retorna registro atualizado."""

def deletar(session, table: str, id: int) -> dict:
    """Remove registro. Retorna {"sucesso": True, "id": id}."""
```

---

## ia/ferramentas.py — JSON Schema das ferramentas para Ollama

Defina a lista `TOOLS` no formato compatível com Ollama 0.9 (mesmo formato OpenAI):

### Ferramenta 1 — `consulta`
```
name: "consulta"
description: "Busca dados reais do banco de dados. Use SEMPRE que precisar de
              qualquer número, lista ou valor. Nunca estime — consulte."
parameters:
  table (string, required): nome da tabela ("produto", "animal", "transacao")
  col   (string, required): coluna a consultar (ex: "quantidade", "valor")
  fun   (string, required, enum): "soma" | "contagem" | "media" | "lista" |
                                   "maximo" | "minimo"
```

### Ferramenta 2 — `cadastra`
```
name: "cadastra"
description: "Insere novo registro no banco. Use quando o usuário pedir para
              adicionar, registrar ou criar algo."
parameters:
  table (string, required): tabela de destino
  dados (object, required): campos e valores do novo registro
```

### Ferramenta 3 — `atualiza`
```
name: "atualiza"
description: "Atualiza um registro existente pelo id."
parameters:
  table (string, required)
  id    (integer, required)
  dados (object, required): campos a atualizar
```

### Ferramenta 4 — `deleta`
```
name: "deleta"
description: "Remove um registro pelo id."
parameters:
  table (string, required)
  id    (integer, required)
```

### Ferramenta 5 — `responda` ← FERRAMENTA FINAL
```
name: "responda"
description: "Envia a resposta final ao usuário. Chame SOMENTE quando tiver
              TODOS os dados necessários. Nunca chame antes de consultar os valores."
parameters:
  parts (array, required): lista ordenada de blocos de conteúdo
    cada item:
      tipo     (string, enum): "texto" | "html" | "python"
      conteudo (string): conteúdo do bloco

Exemplos de uso:
  parts=[{"tipo":"texto","conteudo":"Você tem 10 animais cadastrados."}]

  parts=[
    {"tipo":"texto","conteudo":"Resumo do estoque:"},
    {"tipo":"html","conteudo":"<table><tr><th>Item</th><th>Qtd</th></tr>...</table>"},
    {"tipo":"texto","conteudo":"Total geral: 47 unidades."}
  ]

  parts=[
    {"tipo":"texto","conteudo":"Valor calculado:"},
    {"tipo":"python","conteudo":"round(1250 * 0.15, 2)"}
  ]
```

---

## ia/orquestrador.py — Loop ReAct

```python
"""
Loop principal de tool calling. Contrato:
- Recebe: mensagem (str), historico (list de dicts role/content)
- Retorna: list de parts (para o front-end renderizar)
- Nunca levanta exceção para a rota Flask — captura e retorna erro como texto
"""

SYSTEM_PROMPT = """
Você é um assistente de gestão. Responda SEMPRE em português brasileiro.

REGRAS ABSOLUTAS — violá-las é um erro grave:
1. NUNCA diga um número sem antes obtê-lo via consulta().
2. NUNCA invente dados — use SEMPRE as ferramentas para buscar informação real.
3. NUNCA chame responda() sem ter absolutamente todos os dados necessários.
4. Se precisar de várias informações, chame consulta() quantas vezes for necessário.
5. Ao ter todos os dados, chame responda() com o resultado completo e claro.
6. Em caso de dúvida sobre um valor, consulte antes de responder.
"""

def orquestrar(mensagem: str, historico: list = None) -> list:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += (historico or [])
    messages.append({"role": "user", "content": mensagem})

    for _ in range(MAX_LOOP_STEPS):  # limite de segurança
        response = ollama.chat(model=OLLAMA_MODEL, messages=messages, tools=TOOLS)

        if not response.message.tool_calls:
            # fallback: resposta em texto puro sem ferramenta
            return [{"tipo": "texto", "conteudo": response.message.content}]

        for call in response.message.tool_calls:
            nome = call.function.name
            args = call.function.arguments  # dict

            if nome == "responda":
                return args.get("parts", [{"tipo": "texto", "conteudo": str(args)}])

            resultado = executor.executar(nome, args)

            # Adiciona a chamada e o resultado ao histórico
            messages.append(response.message)
            messages.append({
                "role": "tool",
                "content": json.dumps(resultado, ensure_ascii=False)
            })

    return [{"tipo": "texto", "conteudo": "Limite de etapas atingido. Tente reformular a pergunta."}]
```

---

## ia/executor.py — Mapeamento ferramenta → função real

```python
"""
Mapeia nome da ferramenta para a função crud correspondente.
Sempre encapsula em try/except — erros voltam como dict para a IA continuar o loop.
"""

def executar(nome: str, args: dict) -> any:
    try:
        with Session() as session:
            if nome == "consulta":
                return crud.consultar(session, args["table"], args["col"], args["fun"])
            elif nome == "cadastra":
                return crud.cadastrar(session, args["table"], args["dados"])
            elif nome == "atualiza":
                return crud.atualizar(session, args["table"], args["id"], args["dados"])
            elif nome == "deleta":
                return crud.deletar(session, args["table"], args["id"])
            else:
                return {"erro": f"Ferramenta desconhecida: {nome}"}
    except Exception as e:
        return {"erro": str(e)}
```

---

## app.py — Rotas Flask

### POST `/api/chat`
```
Body:    {"mensagem": str, "historico": list (opcional, default [])}
Retorna: {"parts": [...]}  ou  {"erro": str}
```
Chama `orquestrador.orquestrar(mensagem, historico)` e retorna o resultado.

### POST `/api/executar`
```
Body:    {"codigo": str}
Retorna: {"saida": str}  ou  {"erro": str}
```
Executa expressão matemática SEGURA (ver seção de segurança abaixo).

### GET `/`
Serve `templates/index.html`.

---

## Segurança do `/api/executar`

Use `ast.parse()` para validar que o código contém APENAS nós seguros antes de
executar com `eval()` em namespace restrito:

```python
SAFE_NODES = {
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mul, ast.Div, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Call, ast.Name
}
SAFE_NAMES = {"round": round, "abs": abs, "sum": sum,
              "max": max, "min": min, "int": int, "float": float}

def executar_python_seguro(codigo: str) -> str:
    tree = ast.parse(codigo, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in SAFE_NODES:
            raise ValueError(f"Operação não permitida: {type(node).__name__}")
    resultado = eval(compile(tree, "<string>", "eval"), {"__builtins__": {}}, SAFE_NAMES)
    return str(resultado)
```

---

## templates/index.html + static/app.js — Front-end

### Layout do chat (HTML):
- Cabeçalho com nome do sistema
- Área de mensagens com scroll automático para o final
- Cada mensagem: balão à esquerda (IA) ou à direita (usuário)
- Indicador animado "processando..." enquanto aguarda resposta
- Campo de texto + botão Enviar (Enter também envia)
- Histórico mantido em memória JavaScript (array de {role, content})

### Função `renderizarResposta(parts)` em app.js:

```javascript
function renderizarResposta(parts) {
    const balao = document.createElement("div");
    balao.className = "mensagem ia";

    for (const part of parts) {
        if (part.tipo === "texto") {
            const p = document.createElement("p");
            p.textContent = part.conteudo;
            balao.appendChild(p);

        } else if (part.tipo === "html") {
            const wrapper = document.createElement("div");
            wrapper.className = "bloco-html";
            wrapper.innerHTML = part.conteudo;   // insere HTML diretamente
            balao.appendChild(wrapper);

        } else if (part.tipo === "python") {
            // Executa no back-end e exibe resultado
            fetch("/api/executar", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({codigo: part.conteudo})
            })
            .then(r => r.json())
            .then(r => {
                const pre = document.createElement("pre");
                pre.className = "bloco-python";
                pre.textContent = r.saida ?? r.erro;
                balao.appendChild(pre);
            });
        }
    }
    document.getElementById("chat").appendChild(balao);
    balao.scrollIntoView({behavior: "smooth"});
}
```

### Função `enviarMensagem()` em app.js:
```javascript
async function enviarMensagem() {
    const texto = input.value.trim();
    if (!texto) return;

    adicionarMensagemUsuario(texto);
    mostrarIndicadorProcessando();
    input.value = "";

    // Mantém histórico para contexto multi-turno
    historico.push({role: "user", content: texto});

    const resp = await fetch("/api/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mensagem: texto, historico: historico.slice(-10)})
    });
    const data = await resp.json();

    esconderIndicadorProcessando();

    if (data.parts) {
        renderizarResposta(data.parts);
        historico.push({role: "assistant", content: JSON.stringify(data.parts)});
    } else {
        renderizarErro(data.erro || "Erro desconhecido");
    }
}
```

---

## init_db.py — Inicialização com dados de exemplo

Cria todas as tabelas e insere:
- 5 produtos (ex: ração, sal mineral, medicamento, sementes, adubo)
- 5 animais (ex: bovinos, suínos, aves, ovinos, equinos)
- 5 transações (mix de entradas e saídas com valores reais)

---

## requirements.txt

```
flask>=3.0
flask-cors
sqlalchemy>=2.0
ollama>=0.2
python-dotenv
```

---

## README.md

Inclua instruções claras:

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Inicializar banco com dados de exemplo
python init_db.py

# 3. Iniciar o servidor
python app.py

# 4. Acessar em
http://localhost:5000
```

Inclua também 3 exemplos de perguntas que o sistema responde:
- "Quantos animais temos no total?"
- "Cadastra 50 bovinos da raça nelore com status ativo"
- "Qual o valor total das transações de entrada?"

---

## Observações de implementação

- Use `flask_cors` com `CORS(app)` para evitar problemas de CORS durante desenvolvimento
- O histórico enviado ao `/api/chat` deve ser limitado às últimas 10 mensagens para
  não sobrecarregar o contexto do modelo (importante para hardware com CPU limitada)
- O SQLAlchemy Session deve ser criado e fechado por requisição (use context manager)
- Log no console a cada chamada de ferramenta para facilitar debug:
  `print(f"[FERRAMENTA] {nome}({args}) → {resultado}")`
- O `style.css` deve ser responsivo, com fonte sans-serif, cores neutras e layout
  de chat limpo — sem dependências externas (sem Bootstrap, sem Tailwind)
