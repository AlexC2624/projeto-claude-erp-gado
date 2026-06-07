from sqlalchemy import func
from db.models import Produto, Animal, Transacao

TABLE_MAP = {
    "produto":   Produto,
    "animal":    Animal,
    "transacao": Transacao,
}


def _get_model(table: str):
    model = TABLE_MAP.get(table.lower())
    if model is None:
        raise ValueError(f"Tabela desconhecida: '{table}'. Use: produto, animal, transacao")
    return model


def _row_to_dict(row) -> dict:
    result = {}
    for c in row.__table__.columns:
        val = getattr(row, c.name)
        if val is None:
            result[c.name] = None
        elif hasattr(val, "isoformat"):
            result[c.name] = val.isoformat()
        else:
            result[c.name] = val
    return result


def consultar(session, table: str, col: str, fun: str):
    try:
        model = _get_model(table)
        if not hasattr(model, col):
            return {"erro": f"Coluna '{col}' não existe na tabela '{table}'"}
        column = getattr(model, col)

        if fun == "soma":
            result = session.query(func.sum(column)).scalar()
            return result or 0
        elif fun == "contagem":
            result = session.query(func.count(column)).scalar()
            return result or 0
        elif fun == "media":
            result = session.query(func.avg(column)).scalar()
            return round(float(result), 2) if result is not None else 0
        elif fun == "maximo":
            result = session.query(func.max(column)).scalar()
            return result
        elif fun == "minimo":
            result = session.query(func.min(column)).scalar()
            return result
        elif fun == "lista":
            rows = session.query(model).all()
            return [_row_to_dict(r) for r in rows]
        else:
            return {"erro": f"Função desconhecida: '{fun}'. Use: soma, contagem, media, lista, maximo, minimo"}
    except Exception as e:
        return {"erro": str(e)}


def cadastrar(session, table: str, dados: dict) -> dict:
    try:
        model = _get_model(table)
        obj = model(**dados)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return _row_to_dict(obj)
    except Exception as e:
        session.rollback()
        return {"erro": str(e)}


def atualizar(session, table: str, id: int, dados: dict) -> dict:
    try:
        model = _get_model(table)
        obj = session.get(model, id)
        if obj is None:
            return {"erro": f"Registro id={id} não encontrado na tabela '{table}'"}
        for key, val in dados.items():
            setattr(obj, key, val)
        session.commit()
        session.refresh(obj)
        return _row_to_dict(obj)
    except Exception as e:
        session.rollback()
        return {"erro": str(e)}


def deletar(session, table: str, id: int) -> dict:
    try:
        model = _get_model(table)
        obj = session.get(model, id)
        if obj is None:
            return {"erro": f"Registro id={id} não encontrado na tabela '{table}'"}
        session.delete(obj)
        session.commit()
        return {"sucesso": True, "id": id}
    except Exception as e:
        session.rollback()
        return {"erro": str(e)}
