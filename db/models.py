from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import config

Base = declarative_base()


class Produto(Base):
    __tablename__ = "produto"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    nome          = Column(String, nullable=False)
    categoria     = Column(String)
    quantidade    = Column(Integer, default=0)
    preco_unit    = Column(Float, default=0.0)
    atualizado_em = Column(DateTime, default=datetime.utcnow)


class Animal(Base):
    __tablename__ = "animal"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    especie       = Column(String, nullable=False)
    raca          = Column(String)
    quantidade    = Column(Integer, default=0)
    status        = Column(String, default="ativo")
    atualizado_em = Column(DateTime, default=datetime.utcnow)


class Transacao(Base):
    __tablename__ = "transacao"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    tipo      = Column(String, nullable=False)   # "entrada" ou "saida"
    descricao = Column(String)
    valor     = Column(Float, default=0.0)
    data      = Column(DateTime, default=datetime.utcnow)


engine       = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
