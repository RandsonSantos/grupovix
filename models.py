from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.types import TypeDecorator, TEXT
import json

db = SQLAlchemy()

# ------------------ Tipo personalizado para listas JSON ------------------ #
class JsonEncodedList(TypeDecorator):
    impl = TEXT

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else '[]'

    def process_result_value(self, value, dialect):
        return json.loads(value) if value else []

# ------------------ Loja ------------------ #
class Loja(db.Model):
    __tablename__ = "loja"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.String(200))

    usuarios = db.relationship("Usuario", back_populates="loja", lazy=True)
    produtos = db.relationship("Produto", back_populates="loja", lazy=True)
    clientes = db.relationship("Cliente", back_populates="loja", lazy=True)
    pedidos = db.relationship("Pedido", back_populates="loja", lazy=True)
    caixas = db.relationship("Caixa", back_populates="loja", lazy=True)

    def __repr__(self):
        return f"<Loja {self.nome}>"

# ------------------ Usuário ------------------ #   
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(50), nullable=False, default="atendimento")
    loja_id = db.Column(db.Integer, db.ForeignKey("loja.id"), nullable=True)

    loja = db.relationship("Loja", back_populates="usuarios")

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def senha(self):
        raise AttributeError("Senha não pode ser lida diretamente.")

    @senha.setter
    def senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def __repr__(self):
        return f"<Usuario {self.nome} ({self.tipo})>"

# ------------------ Produto ------------------ #
class Produto(db.Model):
    __tablename__ = "produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False, default=0.0)
    estoque = db.Column(db.Integer, nullable=False, default=0)
    estoque_minimo = db.Column(db.Integer, nullable=False, default=4)

    loja_id = db.Column(db.Integer, db.ForeignKey("loja.id"), nullable=False)
    loja = db.relationship("Loja", back_populates="produtos")

    def __repr__(self):
        return f"<Produto {self.nome} | R$ {self.preco:.2f} | Estoque: {self.estoque}>"

# ------------------ Cliente ------------------ #
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    loja_id = db.Column(db.Integer, db.ForeignKey("loja.id"), nullable=False)

    loja = db.relationship("Loja", back_populates="clientes")
    pedidos = db.relationship("Pedido", back_populates="cliente", lazy="dynamic")

    def __repr__(self):
        return f"<Cliente {self.nome}>"

# ------------------ Pedido ------------------ #
class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produtos = db.Column(JsonEncodedList, nullable=False)
    total = db.Column(db.Float, nullable=False, default=0.0)
    forma_pagamento = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="pendente")
    data = db.Column(db.DateTime, default=datetime.utcnow)
    fiado = db.Column(db.Boolean, default=False)

    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=True)
    cliente = db.relationship("Cliente", back_populates="pedidos")

    loja_id = db.Column(db.Integer, db.ForeignKey("loja.id"), nullable=False)
    loja = db.relationship("Loja", back_populates="pedidos")

    def __repr__(self):
        return f"<Pedido #{self.id} | Total: R$ {self.total:.2f} | Status: {self.status}>"

# ------------------ Caixa ------------------ #
class Caixa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    saldo_inicial = db.Column(db.Float, nullable=False, default=0.0)
    saldo_atual = db.Column(db.Float, nullable=False, default=0.0)
    saldo_final = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="aberto")
    data_fechamento = db.Column(db.DateTime)
    diferenca = db.Column(db.Float, default=0.0)

    loja_id = db.Column(db.Integer, db.ForeignKey("loja.id"), nullable=False)
    loja = db.relationship("Loja", back_populates="caixas")

    def __repr__(self):
        return f"<Caixa #{self.id} | Status: {self.status}>"
