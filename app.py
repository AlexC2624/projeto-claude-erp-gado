import ast
import atexit
import json
import logging
import os
import ollama
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from flask_cors import CORS
from ia import orquestrador
import config

# ── Logging detalhado ──────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.INFO)

logger = logging.getLogger("app")

# ── Flask ──────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
CORS(app)

SAFE_NODES = {
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Call, ast.Name,
}
SAFE_NAMES = {
    "round": round, "abs": abs, "sum": sum,
    "max": max, "min": min, "int": int, "float": float,
}


def executar_python_seguro(codigo: str) -> str:
    tree = ast.parse(codigo, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in SAFE_NODES:
            raise ValueError(f"Operação não permitida: {type(node).__name__}")
    resultado = eval(compile(tree, "<string>", "eval"), {"__builtins__": {}}, SAFE_NAMES)
    return str(resultado)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    mensagem = data.get("mensagem", "").strip()
    historico = data.get("historico", [])

    if not mensagem:
        return jsonify({"erro": "Mensagem vazia"}), 400

    logger.info("POST /api/chat — mensagem: %r", mensagem)

    def generate():
        try:
            for evento in orquestrador.orquestrar_stream(mensagem, historico):
                payload = json.dumps(evento, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as e:
            logger.exception("Erro no stream SSE: %s", e)
            erro = json.dumps({"tipo": "erro", "mensagem": str(e)}, ensure_ascii=False)
            yield f"data: {erro}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/executar", methods=["POST"])
def executar():
    data = request.get_json()
    codigo = data.get("codigo", "").strip()
    if not codigo:
        return jsonify({"erro": "Código vazio"}), 400
    try:
        saida = executar_python_seguro(codigo)
        logger.debug("executar_python: %r → %r", codigo, saida)
        return jsonify({"saida": saida})
    except Exception as e:
        logger.warning("executar_python erro: %s", e)
        return jsonify({"erro": str(e)}), 400


def _aquecer_modelo() -> None:
    """Carrega o modelo na RAM antes de aceitar requisições."""
    try:
        logger.info(
            "Carregando modelo '%s' na memória (num_ctx=%s, num_thread=%s)…",
            config.OLLAMA_MODEL,
            config.OLLAMA_OPTIONS["num_ctx"],
            config.OLLAMA_OPTIONS["num_thread"],
        )
        ollama.generate(model=config.OLLAMA_MODEL, keep_alive=-1, options=config.OLLAMA_OPTIONS)
        logger.info("Modelo '%s' pronto.", config.OLLAMA_MODEL)
    except Exception as e:
        logger.error("Falha ao carregar modelo: %s", e)


def _descarregar_modelo() -> None:
    """Libera o modelo da RAM ao encerrar o servidor."""
    try:
        logger.info("Descarregando modelo '%s'…", config.OLLAMA_MODEL)
        ollama.generate(model=config.OLLAMA_MODEL, keep_alive=0)
        logger.info("Modelo descarregado.")
    except Exception as e:
        logger.warning("Falha ao descarregar modelo: %s", e)


if __name__ == "__main__":
    # Com debug=True o Werkzeug spawna um processo filho (WERKZEUG_RUN_MAIN=true)
    # que é o que realmente serve as requisições — o warmup roda só nele.
    if not config.DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        _aquecer_modelo()
        atexit.register(_descarregar_modelo)
    app.run(debug=config.DEBUG, port=5000, threaded=True)
