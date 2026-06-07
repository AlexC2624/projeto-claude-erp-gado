import json
import logging
import queue
import threading
from typing import Iterator
import ollama
from ia import executor
from ia.ferramentas import TOOLS
import config

logger = logging.getLogger("ia.orquestrador")

SYSTEM_PROMPT = """
Você é um assistente de gestão rural. Responde em português brasileiro.

BANCO DE DADOS:
- tabela "animal":    colunas especie, raca, quantidade, status, id
- tabela "produto":   colunas nome, categoria, quantidade, preco_unit, id
- tabela "transacao": colunas tipo (entrada/saida), descricao, valor, data, id

FLUXO OBRIGATÓRIO para qualquer pergunta sobre dados da fazenda:
  1. Chame consulta() para obter os dados reais.
  2. Chame mais consulta() se precisar de mais informações.
  3. Ao ter TODOS os dados, chame responda() com a resposta.
  Nunca pule o passo 1. Nunca invente valores.

EXEMPLOS de quando chamar consulta():
- "o que tem cadastrado?" ou "o que existe?" →
    consulta(table="animal", col="id", fun="lista")
    consulta(table="produto", col="id", fun="lista")
    consulta(table="transacao", col="id", fun="lista")
- "quantos animais?" →
    consulta(table="animal", col="quantidade", fun="soma")
- "listar produtos" →
    consulta(table="produto", col="id", fun="lista")
- "qual o saldo financeiro?" →
    consulta(table="transacao", col="valor", fun="lista")

Para respostas que NÃO precisam de dados (saudações, dúvidas gerais):
  Responda diretamente em texto sem chamar ferramentas.
"""

_DESCRICOES_FERRAMENTAS = {
    "consulta": "Consultando banco de dados",
    "cadastra": "Cadastrando registro",
    "atualiza": "Atualizando registro",
    "deleta":   "Removendo registro",
}


def _parse_fallback(content: str) -> list | None:
    """Detecta quando o modelo retornou JSON de parts como texto puro."""
    text = content.strip()
    if not (text.startswith("[") or text.startswith("{")):
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed = [parsed]
        if isinstance(parsed, list) and parsed and "tipo" in parsed[0]:
            return parsed
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return None


def _streamar_chat(messages: list):
    """
    Encapsula ollama.chat(stream=True).

    Yields:
      ("token", str)              — token de texto gerado (apenas para respostas em texto puro)
      ("mensagem", msg, str)      — último yield: objeto Message completo + texto acumulado
    """
    texto_partes: list[str] = []
    is_tool_call: bool | None = None   # None=desconhecido, True=JSON/tool-call, False=texto puro
    ultima_msg = None

    for chunk in ollama.chat(
        model=config.OLLAMA_MODEL,
        messages=messages,
        tools=TOOLS,
        keep_alive=-1,
        options=config.OLLAMA_OPTIONS,
        stream=True,
    ):
        delta = chunk.message.content or ""
        if delta:
            texto_partes.append(delta)
            logger.debug("⟳ chunk #%d: %r", len(texto_partes), delta[:30])

            if is_tool_call is None:
                parcial = "".join(texto_partes).lstrip()
                if parcial:
                    is_tool_call = parcial[0] in ("{", "[")

            if is_tool_call is False:
                yield ("token", delta)

        if chunk.message.tool_calls:
            is_tool_call = True

        ultima_msg = chunk.message

    yield ("mensagem", ultima_msg, "".join(texto_partes))


def _streamar_com_heartbeat(messages: list, intervalo: float = 8.0) -> Iterator[tuple]:
    """
    Executa _streamar_chat() numa thread e re-emite os itens aqui.
    A cada `intervalo` segundos sem chunk emite ("heartbeat", None) para manter
    a conexão SSE viva durante o silêncio inicial (modelo ainda processando).
    """
    q: queue.Queue = queue.Queue()

    def _worker():
        try:
            for item in _streamar_chat(messages):
                q.put(("item", item))
        except Exception as exc:
            q.put(("erro", str(exc)))
        finally:
            q.put(("fim", None))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    while True:
        try:
            kind, valor = q.get(timeout=intervalo)
        except queue.Empty:
            yield ("heartbeat", None)
            continue

        if kind == "fim":
            break
        if kind == "erro":
            raise RuntimeError(valor)
        yield valor  # kind == "item"


def orquestrar_stream(mensagem: str, historico: list | None = None):
    """
    Generator principal de eventos SSE.
    Eventos possíveis:
      gerando         — modelo está gerando (sinaliza início de cada etapa)
      heartbeat       — keep-alive enviado a cada 8 s de silêncio do modelo
      token           — token de texto chegando em tempo real
      ferramenta_inicio / ferramenta_fim — execução de ferramentas CRUD
      partes          — resposta final renderizável (encerra o stream)
      erro            — exceção capturada
    """
    messages: list = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += (historico or [])
    messages.append({"role": "user", "content": mensagem})

    logger.info("=== Nova mensagem ===")
    logger.info("Usuário: %r", mensagem)

    try:
        for step in range(1, config.MAX_LOOP_STEPS + 1):
            logger.debug("--- Etapa %d/%d → chamando %s ---",
                         step, config.MAX_LOOP_STEPS, config.OLLAMA_MODEL)

            yield {"tipo": "gerando", "etapa": step}

            texto_completo = ""
            ultima_msg = None

            for item in _streamar_com_heartbeat(messages):
                if item[0] == "heartbeat":
                    yield {"tipo": "heartbeat"}
                elif item[0] == "token":
                    yield {"tipo": "token", "conteudo": item[1]}
                elif item[0] == "mensagem":
                    ultima_msg = item[1]
                    texto_completo = item[2]

            logger.debug(
                "Resposta recebida | tool_calls=%s | content=%r",
                bool(ultima_msg and ultima_msg.tool_calls),
                texto_completo[:120],
            )

            if not (ultima_msg and ultima_msg.tool_calls):
                logger.warning("Modelo não usou ferramenta. Tentando fallback JSON.")
                fallback = _parse_fallback(texto_completo)
                if fallback:
                    logger.info("Fallback JSON parseado (%d parte(s)).", len(fallback))
                    yield {"tipo": "partes", "parts": fallback}
                else:
                    logger.info("Resposta em texto puro (stream concluído).")
                    yield {"tipo": "partes", "parts": [{"tipo": "texto", "conteudo": texto_completo or "Sem resposta."}]}
                return

            messages.append(ultima_msg)  # type: ignore[arg-type]

            for call in ultima_msg.tool_calls:
                nome = call.function.name
                args = call.function.arguments

                if nome == "responda":
                    parts = args.get("parts", [{"tipo": "texto", "conteudo": str(args)}])
                    logger.info("responda() chamado com %d parte(s).", len(parts))
                    yield {"tipo": "partes", "parts": parts}
                    return

                descricao = _DESCRICOES_FERRAMENTAS.get(nome, nome)
                logger.info("[FERRAMENTA] %s(%s)", nome, json.dumps(dict(args), ensure_ascii=False))
                yield {"tipo": "ferramenta_inicio", "nome": nome, "descricao": descricao, "args": dict(args)}

                resultado = executor.executar(nome, dict(args))
                logger.info("[RESULTADO ] %s → %s", nome,
                            json.dumps(resultado, ensure_ascii=False)[:200])
                yield {"tipo": "ferramenta_fim", "nome": nome, "resultado": resultado}

                messages.append({
                    "role": "tool",
                    "content": json.dumps(resultado, ensure_ascii=False),
                })

        logger.warning("Limite de %d etapas atingido.", config.MAX_LOOP_STEPS)
        yield {"tipo": "partes", "parts": [{"tipo": "texto", "conteudo": "Limite de etapas atingido. Tente reformular a pergunta."}]}

    except Exception as e:
        logger.exception("Erro no orquestrador: %s", e)
        yield {"tipo": "erro", "mensagem": str(e)}
