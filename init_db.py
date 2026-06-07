from datetime import datetime
from db.models import Base, engine, SessionLocal, Produto, Animal, Transacao


def init():
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas.")

    with SessionLocal() as session:
        produtos = [
            Produto(
                nome="Ração Bovina Premium",
                categoria="Alimentação",
                quantidade=500,
                preco_unit=2.50,
            ),
            Produto(
                nome="Sal Mineral Bovino",
                categoria="Suplemento",
                quantidade=200,
                preco_unit=4.80,
            ),
            Produto(
                nome="Vacina Febre Aftosa",
                categoria="Veterinário",
                quantidade=300,
                preco_unit=1.20,
            ),
            Produto(
                nome="Vermífugo Bovino",
                categoria="Veterinário",
                quantidade=150,
                preco_unit=8.90,
            ),
            Produto(
                nome="Sêmen Nelore Certificado",
                categoria="Reprodução",
                quantidade=50,
                preco_unit=85.00,
            ),
        ]

        animais = [
            Animal(especie="Bovino",      raca="Nelore",          quantidade=120, status="ativo"),
            Animal(especie="Suíno",       raca="Landrace",        quantidade=45,  status="ativo"),
            Animal(especie="Ave de Corte", raca="Cobb 500",       quantidade=2000, status="ativo"),
            Animal(especie="Ovino",       raca="Santa Inês",      quantidade=80,  status="ativo"),
            Animal(especie="Equino",      raca="Quarto de Milha", quantidade=8,   status="ativo"),
        ]

        transacoes = [
            Transacao(
                tipo="entrada",
                descricao="Compra de 30 bovinos nelore",
                valor=90000.00,
                data=datetime(2026, 1, 10),
            ),
            Transacao(
                tipo="saida",
                descricao="Venda de 15 cabeças de gado gordo",
                valor=75000.00,
                data=datetime(2026, 2, 5),
            ),
            Transacao(
                tipo="saida",
                descricao="Gasto veterinário — vacinação febre aftosa",
                valor=1800.00,
                data=datetime(2026, 3, 12),
            ),
            Transacao(
                tipo="entrada",
                descricao="Venda de leite — 5.000 litros",
                valor=15000.00,
                data=datetime(2026, 4, 20),
            ),
            Transacao(
                tipo="saida",
                descricao="Compra de ração bovina e sal mineral",
                valor=3200.00,
                data=datetime(2026, 5, 8),
            ),
        ]

        session.add_all(produtos + animais + transacoes)
        session.commit()

    print(f"  → {len(produtos)} produtos cadastrados")
    print(f"  → {len(animais)} animais cadastrados")
    print(f"  → {len(transacoes)} transações cadastradas")
    print("Banco de dados inicializado com sucesso!")


if __name__ == "__main__":
    init()
