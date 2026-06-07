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

_DESCRICOES = {
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


def orquestrar_stream(mensagem: str, historico: list = None):
    """
    Generator que emite eventos SSE durante o loop ReAct.
    Cada item yielded é um dict que será serializado como 'data: <json>\\n\\n'.
    Eventos possíveis:
      ferramenta_inicio  — ferramenta sendo executada
      ferramenta_fim     — ferramenta concluída
      partes             — resposta final (encerra o stream)
      erro               — exceção capturada (encerra o stream)
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += (historico or [])
    messages.append({"role": "user", "content": mensagem})

    logger.info("=== Nova mensagem ===")
    logger.info("Usuário: %r", mensagem)

    try:
        for step in range(1, config.MAX_LOOP_STEPS + 1):
            logger.debug("--- Etapa %d/%d → chamando %s ---", step, config.MAX_LOOP_STEPS, config.OLLAMA_MODEL)

            response = ollama.chat(
                model=config.OLLAMA_MODEL,
                messages=messages,
                tools=TOOLS,
            )

            logger.debug(
                "Resposta recebida | tool_calls=%s | content=%r",
                bool(response.message.tool_calls),
                (response.message.content or "")[:120],
            )

            # Modelo não chamou nenhuma ferramenta
            if not response.message.tool_calls:
                content = response.message.content or ""
                logger.warning("Modelo não usou ferramenta. Tentando fallback JSON.")

                fallback = _parse_fallback(content)
                if fallback:
                    logger.info("Fallback JSON parseado com sucesso (%d parte(s)).", len(fallback))
                    yield {"tipo": "partes", "parts": fallback}
                else:
                    logger.info("Resposta em texto puro.")
                    yield {"tipo": "partes", "parts": [{"tipo": "texto", "conteudo": content or "Sem resposta."}]}
                return

            messages.append(response.message)

            for call in response.message.tool_calls:
                nome = call.function.name
                args = call.function.arguments

                if nome == "responda":
                    parts = args.get("parts", [{"tipo": "texto", "conteudo": str(args)}])
                    logger.info("responda() chamado com %d parte(s). Encerrando loop.", len(parts))
                    yield {"tipo": "partes", "parts": parts}
                    return

                descricao = _DESCRICOES.get(nome, nome)
                logger.info("[FERRAMENTA] %s(%s)", nome, json.dumps(args, ensure_ascii=False))
                yield {"tipo": "ferramenta_inicio", "nome": nome, "descricao": descricao, "args": args}

                resultado = executor.executar(nome, args)
                logger.info("[RESULTADO ] %s → %s", nome, json.dumps(resultado, ensure_ascii=False)[:200])
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
