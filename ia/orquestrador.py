import json
import logging
import ollama
from ia import executor
from ia.ferramentas import TOOLS
import config

logger = logging.getLogger("ia.orquestrador")

SYSTEM_PROMPT = """
Você é um assistente especializado em gestão rural e pecuária. Auxilia produtores rurais no
gerenciamento de rebanhos (bovinos nelore, suínos, aves de corte, ovinos, equinos), controle
de insumos e produtos veterinários (ração, sal mineral, vacinas, vermífugos, sêmen), e
acompanhamento financeiro da fazenda (compras, vendas, gastos veterinários, venda de leite).
Responda SEMPRE em português brasileiro, de forma clara e objetiva.

REGRAS ABSOLUTAS — violá-las é um erro grave:
1. NUNCA diga um número sem antes obtê-lo via consulta().
2. NUNCA invente dados — use SEMPRE as ferramentas para buscar informação real do banco.
3. NUNCA chame responda() sem ter absolutamente todos os dados necessários.
4. Se precisar de várias informações, chame consulta() quantas vezes for necessário.
5. Ao ter todos os dados, chame responda() com o resultado completo e claro.
6. Em caso de dúvida sobre um valor, consulte antes de responder.
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


def _streamar_chat(messages):
    """
    Encapsula ollama.chat(stream=True).

    Yields:
      ("token", str)              — token de texto gerado (apenas para respostas em texto puro)
      ("mensagem", msg, str)      — último yield: objeto Message completo + texto acumulado
    """
    texto_partes = []
    is_tool_call = None   # None=desconhecido, True=JSON/tool-call, False=texto puro
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
            # ← diagnóstico: confirma que o Ollama libera tokens progressivamente
            logger.debug("⟳ chunk #%d: %r", len(texto_partes), delta[:30])

            # Determina o tipo a partir do primeiro caractere significativo
            if is_tool_call is None:
                parcial = "".join(texto_partes).lstrip()
                if parcial:
                    is_tool_call = parcial[0] in ("{", "[")

            # Só emite tokens para o front quando é uma resposta em texto
            if is_tool_call is False:
                yield ("token", delta)

        if chunk.message.tool_calls:
            is_tool_call = True

        ultima_msg = chunk.message

    yield ("mensagem", ultima_msg, "".join(texto_partes))


def orquestrar_stream(mensagem: str, historico: list = None):
    """
    Generator principal de eventos SSE.
    Eventos possíveis:
      gerando         — modelo está gerando (sinaliza início de cada etapa)
      token           — token de texto chegando em tempo real
      ferramenta_inicio / ferramenta_fim — execução de ferramentas CRUD
      partes          — resposta final renderizável (encerra o stream)
      erro            — exceção capturada
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += (historico or [])
    messages.append({"role": "user", "content": mensagem})

    logger.info("=== Nova mensagem ===")
    logger.info("Usuário: %r", mensagem)

    try:
        for step in range(1, config.MAX_LOOP_STEPS + 1):
            logger.debug("--- Etapa %d/%d → chamando %s ---",
                         step, config.MAX_LOOP_STEPS, config.OLLAMA_MODEL)

            # Sinaliza imediatamente ao front que a geração começou
            yield {"tipo": "gerando", "etapa": step}

            texto_completo = ""
            ultima_msg = None

            for item in _streamar_chat(messages):
                if item[0] == "token":
                    yield {"tipo": "token", "conteudo": item[1]}
                else:  # "mensagem"
                    _, ultima_msg, texto_completo = item

            logger.debug(
                "Resposta recebida | tool_calls=%s | content=%r",
                bool(ultima_msg and ultima_msg.tool_calls),
                texto_completo[:120],
            )

            # ── Sem tool_calls: resposta final de texto ────────────────
            if not (ultima_msg and ultima_msg.tool_calls):
                logger.warning("Modelo não usou ferramenta. Tentando fallback JSON.")
                fallback = _parse_fallback(texto_completo)
                if fallback:
                    logger.info("Fallback JSON parseado (%d parte(s)).", len(fallback))
                    yield {"tipo": "partes", "parts": fallback}
                else:
                    logger.info("Resposta em texto puro (stream concluído).")
                    # Texto já foi enviado token a token; partes confirma o fim
                    yield {"tipo": "partes", "parts": [{"tipo": "texto", "conteudo": texto_completo or "Sem resposta."}]}
                return

            # ── Com tool_calls: processa cada ferramenta ───────────────
            messages.append(ultima_msg)

            for call in ultima_msg.tool_calls:
                nome = call.function.name
                args = call.function.arguments

                if nome == "responda":
                    parts = args.get("parts", [{"tipo": "texto", "conteudo": str(args)}])
                    logger.info("responda() chamado com %d parte(s).", len(parts))
                    yield {"tipo": "partes", "parts": parts}
                    return

                descricao = _DESCRICOES_FERRAMENTAS.get(nome, nome)
                logger.info("[FERRAMENTA] %s(%s)", nome, json.dumps(args, ensure_ascii=False))
                yield {"tipo": "ferramenta_inicio", "nome": nome, "descricao": descricao, "args": args}

                resultado = executor.executar(nome, args)
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
