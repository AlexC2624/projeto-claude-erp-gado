import json
import ollama
from ia import executor
from ia.ferramentas import TOOLS
import config

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


def orquestrar(mensagem: str, historico: list = None) -> list:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += (historico or [])
    messages.append({"role": "user", "content": mensagem})

    try:
        for _ in range(config.MAX_LOOP_STEPS):
            response = ollama.chat(
                model=config.OLLAMA_MODEL,
                messages=messages,
                tools=TOOLS,
            )

            if not response.message.tool_calls:
                return [{"tipo": "texto", "conteudo": response.message.content or "Sem resposta."}]

            # Registra a mensagem do assistente uma única vez
            messages.append(response.message)

            resposta_final = None
            for call in response.message.tool_calls:
                nome = call.function.name
                args = call.function.arguments

                if nome == "responda":
                    resposta_final = args.get(
                        "parts", [{"tipo": "texto", "conteudo": str(args)}]
                    )
                    break

                resultado = executor.executar(nome, args)
                print(f"[FERRAMENTA] {nome}({args}) → {resultado}")

                messages.append({
                    "role": "tool",
                    "content": json.dumps(resultado, ensure_ascii=False),
                })

            if resposta_final is not None:
                return resposta_final

        return [{"tipo": "texto", "conteudo": "Limite de etapas atingido. Tente reformular a pergunta."}]

    except Exception as e:
        return [{"tipo": "texto", "conteudo": f"Erro no orquestrador: {str(e)}"}]
