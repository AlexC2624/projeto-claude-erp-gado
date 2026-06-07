import ast
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from ia import orquestrador
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
CORS(app)

SAFE_NODES = {
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mul, ast.Div, ast.Mod, ast.Pow,
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
    try:
        parts = orquestrador.orquestrar(mensagem, historico)
        return jsonify({"parts": parts})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/executar", methods=["POST"])
def executar():
    data = request.get_json()
    codigo = data.get("codigo", "").strip()
    if not codigo:
        return jsonify({"erro": "Código vazio"}), 400
    try:
        saida = executar_python_seguro(codigo)
        return jsonify({"saida": saida})
    except Exception as e:
        return jsonify({"erro": str(e)}), 400


if __name__ == "__main__":
    app.run(debug=config.DEBUG, port=5000)
