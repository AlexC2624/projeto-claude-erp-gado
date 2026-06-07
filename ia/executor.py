from db.models import SessionLocal
from db import crud


def executar(nome: str, args: dict):
    try:
        with SessionLocal() as session:
            if nome == "consulta":
                return crud.consultar(session, args["table"], args["col"], args["fun"])
            elif nome == "cadastra":
                return crud.cadastrar(session, args["table"], args["dados"])
            elif nome == "atualiza":
                return crud.atualizar(session, args["table"], args["id"], args["dados"])
            elif nome == "deleta":
                return crud.deletar(session, args["table"], args["id"])
            else:
                return {"erro": f"Ferramenta desconhecida: '{nome}'"}
    except Exception as e:
        return {"erro": str(e)}
