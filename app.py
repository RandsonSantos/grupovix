from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os

app = Flask(__name__)

# 🔧 Configuração do banco
app.config["SQLALCHEMY_DATABASE_URI"] = 'postgresql://db_grupovix_user:fEqgm3in39AmzWb4fQ3Omsowxrd5hDSl@dpg-d21pb77fte5s73ftcl7g-a.oregon-postgres.render.com/db_grupovix'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'sua_chave_super_secreta'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5)
SENHA_MASTER = os.getenv("SENHA_MASTER", "admin@123")

# Banco e modelos
from models import db, Loja, Usuario, Produto, Cliente, Pedido, Caixa
db.init_app(app)


# ---------------------- LOGIN ---------------------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.verificar_senha(senha):
            session["usuario_id"] = usuario.id
            session["usuario_tipo"] = usuario.tipo
            session["loja_id"] = usuario.loja_id  # ← ESSENCIAL
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("dashboard_admin"))
        else:
            flash("Credenciais inválidas", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema com sucesso", "info")
    return redirect(url_for("login"))



@app.route("/")
def home():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado para acessar a frente de caixa", "warning")
        return redirect(url_for("login"))

    produtos = Produto.query.filter_by(loja_id=session["loja_id"]).all()
    clientes = Cliente.query.filter_by(loja_id=session["loja_id"]).order_by(Cliente.nome.asc()).all()
    ultimo_pedido = Pedido.query.filter_by(loja_id=session["loja_id"]).order_by(Pedido.id.desc()).first()

    if ultimo_pedido:
        try:
            ultimo_pedido.produtos = json.loads(ultimo_pedido.produtos)
        except Exception:
            ultimo_pedido.produtos = []

    usuario = Usuario.query.get(session["usuario_id"])

    return render_template("home.html",
        produtos=produtos,
        clientes=clientes,
        ultimo_pedido=ultimo_pedido,
        usuario=usuario
    )

@app.route("/cadastrar_usuario", methods=["GET", "POST"])
def cadastrar_usuario():
    #if session.get("usuario_tipo") != "admin":
    #    flash("Acesso restrito aos administradores", "danger")
    #    return redirect(url_for("home"))

    lojas = Loja.query.order_by(Loja.nome.asc()).all()

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        tipo = request.form.get("tipo")
        loja_id = request.form.get("loja_id") if tipo == "atendimento" else None

        if not nome or not email or not senha or tipo not in ["admin", "atendimento"]:
            flash("Preencha todos os campos corretamente", "warning")
            return redirect(url_for("cadastrar_usuario"))

        if tipo == "atendimento" and not loja_id:
            flash("Selecione a loja para o atendimento", "warning")
            return redirect(url_for("cadastrar_usuario"))

        # 🧠 Verifica se o e-mail já existe
        email_existente = Usuario.query.filter_by(email=email).first()
        if email_existente:
            flash("Já existe um usuário com este e-mail", "danger")
            return redirect(url_for("cadastrar_usuario"))

        senha_hash = generate_password_hash(senha)

        novo_usuario = Usuario(
            nome=nome,
            email=email,
            senha_hash=senha_hash,
            tipo=tipo,
            loja_id=loja_id
        )

        db.session.add(novo_usuario)
        db.session.commit()
        flash(f"Usuário '{nome}' cadastrado com sucesso!", "success")
        return redirect(url_for("cadastrar_usuario"))

    return render_template("cadastrar_usuario.html", lojas=lojas)

@app.route("/usuarios")
def listar_usuarios():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario_logado = Usuario.query.get(session["usuario_id"])

    if usuario_logado.tipo == "admin":
        usuarios = Usuario.query.order_by(Usuario.nome.asc()).all()
    else:
        usuarios = Usuario.query.filter_by(loja_id=usuario_logado.loja_id).order_by(Usuario.nome.asc()).all()

    return render_template("usuarios.html", usuarios=usuarios)

@app.route("/excluir_usuario/<int:id>", methods=["POST"])
def excluir_usuario(id):
    if session.get("usuario_tipo") != "admin":
        flash("Acesso negado", "danger")
        return redirect(url_for("home"))

    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash("Usuário excluído com sucesso!", "success")
    return redirect(url_for("listar_usuarios"))

@app.route("/processar_venda", methods=["POST"])
def processar_venda():
    pedido_json = request.form.get("pedido")
    forma_pagamento = request.form.get("forma_pagamento", "Dinheiro")
    cliente_id = request.form.get("cliente_id")
    venda_fiado = request.form.get("fiado") == "on"

    if not pedido_json or pedido_json == "[]":
        return jsonify({"success": False, "message": "Nenhum produto selecionado."}), 400

    if venda_fiado and not cliente_id:
        return jsonify({"success": False, "message": "Venda fiado exige cliente."}), 400

    try:
        produtos_selecionados = json.loads(pedido_json)
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Erro ao processar os produtos."}), 400

    total = 0
    itens = []
    for item in produtos_selecionados:
        produto = Produto.query.filter_by(id=item["id"], loja_id=session["loja_id"]).first()
        if not produto or produto.estoque < item["quantidade"]:
            return jsonify({"success": False, "message": f"Estoque insuficiente para {item['nome']}"}), 400
        produto.estoque -= item["quantidade"]
        total += produto.preco * item["quantidade"]
        itens.append({
            "id": produto.id,
            "nome": produto.nome,
            "quantidade": item["quantidade"],
            "preco": produto.preco
        })

    nova_venda = Pedido(
        produtos=json.dumps(itens, ensure_ascii=False),
        total=total,
        status="finalizado",
        forma_pagamento=forma_pagamento,
        fiado=venda_fiado,
        cliente_id=cliente_id if venda_fiado else None,
        loja_id=session["loja_id"]
    )
    db.session.add(nova_venda)
    db.session.commit()
    return redirect(url_for("cupom", id=nova_venda.id))

@app.route("/cupom/<int:id>")
def cupom(id):
    pedido = Pedido.query.get_or_404(id)
    if pedido.loja_id != session["loja_id"]:
        flash("Esse cupom não pertence à sua loja.", "danger")
        return redirect(url_for("home"))
    try:
        pedido.produtos = json.loads(pedido.produtos)
    except (json.JSONDecodeError, TypeError):
        pedido.produtos = []
    return render_template("cupom.html", pedido=pedido)

# ---------------------- ROTA DE VENDAS ---------------------- #
from flask import request, session, redirect, url_for, flash, render_template
from datetime import date
from sqlalchemy import func
from models import Pedido, Usuario  # Certifique-se de importar seus modelos corretamente

from flask import request, session, redirect, url_for, flash, render_template
from datetime import date
from sqlalchemy import func
from models import Pedido, Usuario  # ajuste conforme suas importações

@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])

    # 🔎 Define consulta conforme tipo de usuário
    if session.get("usuario_tipo") == "admin":
        query = Pedido.query
    else:
        query = Pedido.query.filter_by(loja_id=session["loja_id"])

    # 📅 Filtro por data do dia usando o campo 'data'
    hoje = date.today()
    query = query.filter(func.date(Pedido.data) == hoje)

    # 🧾 Filtros adicionais via formulário
    if request.method == "POST":
        status = request.form.get("status")
        forma = request.form.get("forma_pagamento")
        if status:
            query = query.filter_by(status=status)
        if forma:
            query = query.filter_by(forma_pagamento=forma)

    pedidos = query.order_by(Pedido.id.desc()).all()

    # 💰 Totais por forma de pagamento
    resumo_formas_pagamento = {}
    for pedido in pedidos:
        forma = pedido.forma_pagamento or "Não informado"
        resumo_formas_pagamento[forma] = resumo_formas_pagamento.get(forma, 0) + pedido.total

    # 📊 Resumo consolidado
    resumo = {
        "Total geral": sum(p.total for p in pedidos),
        "Cancelado": sum(p.total for p in pedidos if p.status == "cancelado"),
        "Fiado": sum(p.total for p in pedidos if p.forma_pagamento == "Fiado")
    }

    # Adiciona os totais por forma ao resumo sem sobrescrever
    for forma, valor in resumo_formas_pagamento.items():
        if forma not in resumo:
            resumo[forma] = valor

    return render_template(
        "vendas.html",
        pedidos=pedidos,
        usuario=usuario,
        resumo_formas_pagamento=resumo_formas_pagamento,
        resumo=resumo,
        agora=date.today()  # usado no título do template
    )
    

@app.route("/cancelar_venda/<int:id>", methods=["POST"])
def cancelar_venda(id):
    pedido = Pedido.query.get_or_404(id)

    if pedido.status == "cancelado":
        return jsonify({"success": False, "message": "Venda já está cancelada"}), 400

    try:
        # Fallback seguro
        itens = pedido.produtos
        if isinstance(itens, str):
            itens = json.loads(itens)

        for item in itens:
            produto = Produto.query.get(item["id"])
            if produto:
                produto.estoque += item["quantidade"]

        pedido.status = "cancelado"
        db.session.commit()
        return jsonify({"success": True, "message": "Venda cancelada com sucesso"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Erro ao cancelar venda: {str(e)}"}), 500
    
from datetime import datetime
from flask import request

from datetime import datetime
from flask import render_template, request, session, redirect, url_for, flash
from models import Pedido, Usuario, Loja
from sqlalchemy import func

@app.route("/relatorio_vendas", methods=["GET", "POST"])
def relatorio_vendas():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado para acessar o relatório", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    lojas = Loja.query.order_by(Loja.nome.asc()).all()

    hoje = datetime.utcnow().date()
    data_inicio = data_fim = hoje
    loja_id = None
    pedidos = []

    if request.method == "POST":
        loja_id = request.form.get("loja_id")
        data_inicio_str = request.form.get("data_inicio")
        data_fim_str = request.form.get("data_fim")

        try:
            if data_inicio_str:
                data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
            if data_fim_str:
                data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Formato de data inválido", "danger")
            return redirect(url_for("relatorio_vendas"))

    # 🔎 Query base
    query = Pedido.query.filter(
        func.date(Pedido.data) >= data_inicio,
        func.date(Pedido.data) <= data_fim
    )

    if usuario.tipo != "admin":
        query = query.filter_by(loja_id=usuario.loja_id)
    elif loja_id:
        query = query.filter_by(loja_id=int(loja_id))

    pedidos = query.order_by(Pedido.data.desc()).all()

    # 📊 Corrigido: resumo financeiro
    resumo = {
        "Dinheiro": 0,
        "Cartão": 0,
        "PIX": 0,
        "Fiado": 0,
        "Cancelado": 0,
        "Total geral": 0
    }

    for p in pedidos:
        valor = p.total or 0
        forma = (p.forma_pagamento or "").strip()

        if p.status == "cancelado":
            resumo["Cancelado"] += valor
        else:
            # ✅ Evita duplicidade: Fiado entra só uma vez
            if forma == "Fiado":
                resumo["Fiado"] += valor
            elif forma in resumo:
                resumo[forma] += valor

            resumo["Total geral"] += valor

    loja_nome = ""
    if loja_id:
        loja_obj = Loja.query.get(int(loja_id))
        loja_nome = loja_obj.nome if loja_obj else ""

    return render_template("relatorio_vendas.html",
        usuario=usuario,
        lojas=lojas,
        loja_id=loja_id,
        loja_nome=loja_nome,
        pedidos=pedidos,
        resumo=resumo,
        data_inicio=data_inicio,
        data_fim=data_fim
    )

@app.route("/adicionar_produto", methods=["POST"])
def adicionar_produto():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    nome = request.form["nome"]
    preco = float(request.form["preco"])
    estoque = int(request.form["estoque"])

    if usuario.tipo == "admin":
        loja_id = int(request.form.get("loja_id"))
    else:
        loja_id = session["loja_id"]

    produto_existente = Produto.query.filter_by(nome=nome, loja_id=loja_id).first()
    if produto_existente:
        produto_existente.estoque += estoque
    else:
        novo_produto = Produto(nome=nome, preco=preco, estoque=estoque, loja_id=loja_id)
        db.session.add(novo_produto)

    db.session.commit()
    return redirect(url_for("estoque"))

@app.route("/ver_produto/<int:id>")
def ver_produto(id):
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    produto = Produto.query.get_or_404(id)

    if usuario.tipo != "admin" and produto.loja_id != usuario.loja_id:
        flash("Produto não pertence à sua loja", "danger")
        return redirect(url_for("estoque"))

    return render_template("ver_produto.html", produto=produto)

@app.route("/salvar_e_ir_alertas/<int:id>", methods=["POST"])
def salvar_e_ir_alertas(id):
    produto = Produto.query.get_or_404(id)

    # Aqui você pode atualizar alguma coisa do produto se quiser
    # Ex: produto.estoque += 1, etc.

    db.session.commit()
    flash("Produto atualizado com sucesso!", "success")
    return redirect(url_for("alertas_estoque"))

@app.route("/editar_produto/<int:id>", methods=["GET", "POST"])
def editar_produto(id):
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    produto = Produto.query.get_or_404(id)

    if usuario.tipo != "admin" and produto.loja_id != usuario.loja_id:
        flash("Produto não pertence à sua loja", "danger")
        return redirect(url_for("estoque"))

    if request.method == "POST":
        produto.nome = request.form["nome"]
        produto.preco = float(request.form["preco"])
        produto.estoque = int(request.form["estoque"])
        db.session.commit()
        return redirect(url_for("estoque"))

    return render_template("editar_produto.html", produto=produto)

@app.route("/excluir_produto/<int:id>", methods=["POST"])
def excluir_produto(id):
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    produto = Produto.query.get_or_404(id)

    if usuario.tipo != "admin" and produto.loja_id != usuario.loja_id:
        flash("Produto não pertence à sua loja", "danger")
        return redirect(url_for("estoque"))

    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for("estoque"))

@app.route("/estoque", methods=["GET", "POST"])
def estoque():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    lojas = Loja.query.order_by(Loja.nome.asc()).all()
    loja_id = None

    if request.method == "POST" and usuario.tipo == "admin":
        loja_id = request.form.get("loja_id", type=int)
        produtos = Produto.query.filter_by(loja_id=loja_id).order_by(Produto.nome.asc()).all()
    elif usuario.tipo == "admin":
        produtos = Produto.query.order_by(Produto.nome.asc()).all()
    else:
        produtos = Produto.query.filter_by(loja_id=usuario.loja_id).order_by(Produto.nome.asc()).all()

    return render_template("estoque.html",
        produtos=produtos,
        usuario=usuario,
        lojas=lojas,
        loja_id=loja_id
    )

@app.route("/estoque_por_loja", methods=["GET", "POST"])
def estoque_por_loja():
    if session.get("usuario_tipo") != "admin":
        flash("Acesso restrito aos administradores", "danger")
        return redirect(url_for("home"))

    lojas = Loja.query.order_by(Loja.nome.asc()).all()
    produtos = []
    loja_selecionada = None

    if request.method == "POST":
        loja_id = request.form.get("loja_id")
        loja_selecionada = Loja.query.get(loja_id)
        produtos = Produto.query.filter_by(loja_id=loja_id).order_by(Produto.nome.asc()).all()

    return render_template("estoque_por_loja.html", lojas=lojas, produtos=produtos, loja=loja_selecionada)

from datetime import datetime

@app.route("/relatorio_produtos_loja", methods=["POST"])
def relatorio_produtos_loja():
    loja_id = request.form.get("loja_id")
    loja = Loja.query.get_or_404(loja_id)
    produtos = Produto.query.filter_by(loja_id=loja.id).order_by(Produto.nome.asc()).all()
    now = datetime.now()
    return render_template("relatorio_produtos_loja.html", loja=loja, produtos=produtos, now=now)

@app.route("/controle_caixa", methods=["GET", "POST"])
def controle_caixa():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    lojas = Loja.query.order_by(Loja.nome.asc()).all()
    hoje = datetime.utcnow().date()

    loja_id = session.get("loja_id") if usuario.tipo != "admin" else None

    if request.method == "POST" and usuario.tipo == "admin":
        loja_id = request.form.get("loja_id") or None

    caixa_aberto = None
    if loja_id:
        caixa_aberto = Caixa.query.filter_by(loja_id=loja_id, status="aberto").first()

    pedidos_do_dia = []
    if loja_id:
        pedidos_do_dia = Pedido.query.filter(
            Pedido.loja_id == loja_id,
            func.date(Pedido.data) == hoje,
            Pedido.status == "finalizado"
        ).all()

    saldo_vendas = sum(p.total or 0 for p in pedidos_do_dia)
    saldo_total = (caixa_aberto.saldo_inicial if caixa_aberto else 0) + saldo_vendas

    caixas = Caixa.query.filter_by(loja_id=loja_id).order_by(Caixa.data_abertura.desc()).all() if loja_id \
        else Caixa.query.order_by(Caixa.data_abertura.desc()).all()

    return render_template("caixa.html",
        caixas=caixas,
        caixa_aberto=caixa_aberto,
        saldo_vendas=saldo_vendas,
        saldo_total_caixa=saldo_total,
        lojas=lojas,
        loja_id=loja_id,
        usuario=usuario)

@app.route("/controle_caixa/<int:loja_id>")
def controle_caixa_loja(loja_id):
    # lógica da função aqui...
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    hoje = datetime.utcnow().date()

    caixa_aberto = Caixa.query.filter_by(loja_id=loja_id, status="aberto").first()

    pedidos_do_dia = Pedido.query.filter(
        Pedido.loja_id == loja_id,
        func.date(Pedido.data) == hoje,
        Pedido.status == "finalizado"
    ).all()

    saldo_vendas = sum(p.total or 0 for p in pedidos_do_dia)
    saldo_total = (caixa_aberto.saldo_inicial if caixa_aberto else 0) + saldo_vendas

    caixas = Caixa.query.filter_by(loja_id=loja_id).order_by(Caixa.data_abertura.desc()).all()
    loja = Loja.query.get(loja_id)

    return render_template("caixa.html",
        caixas=caixas,
        caixa_aberto=caixa_aberto,
        saldo_vendas=saldo_vendas,
        saldo_total_caixa=saldo_total,
        loja=loja,
        usuario=usuario,
        lojas=Loja.query.all(),
        loja_id=loja_id)

@app.route("/abrir_caixa", methods=["POST"])
def abrir_caixa():
    saldo_inicial = request.form.get("saldo_inicial", type=float)
    if saldo_inicial is None or saldo_inicial < 0:
        flash("Valor inválido", "danger")
        return redirect(url_for("controle_caixa"))

    if Caixa.query.filter_by(loja_id=session["loja_id"], status="aberto").first():
        flash("Já existe um caixa aberto. Feche primeiro.", "warning")
        return redirect(url_for("controle_caixa"))

    caixa = Caixa(saldo_inicial=saldo_inicial, saldo_atual=saldo_inicial,
                  status="aberto", loja_id=session["loja_id"])
    db.session.add(caixa)
    db.session.commit()
    flash("Caixa aberto com sucesso", "success")
    return redirect(url_for("controle_caixa"))

@app.route("/fechar_caixa/<int:id>", methods=["POST"])
def fechar_caixa(id):
    caixa = Caixa.query.get_or_404(id)
    if caixa.loja_id != session["loja_id"]:
        flash("Esse caixa não pertence à sua loja", "danger")
        return redirect(url_for("controle_caixa"))

    valor_gaveta = request.form.get("valor_gaveta", type=float)
    if valor_gaveta is None or valor_gaveta < 0:
        flash("Valor inválido", "danger")
        return redirect(url_for("controle_caixa"))

    caixa.saldo_final = valor_gaveta
    caixa.status = "fechado"
    caixa.data_fechamento = datetime.utcnow()
    caixa.diferenca = valor_gaveta - caixa.saldo_atual
    db.session.commit()
    flash("Caixa fechado com sucesso", "success")
    return redirect(url_for("controle_caixa"))

@app.route("/excluir_caixas", methods=["POST"])
def excluir_todos_caixas():
    try:
        caixas = Caixa.query.filter_by(loja_id=session["loja_id"]).all()
        for c in caixas:
            db.session.delete(c)
        db.session.commit()
        flash("Todos os registros de caixa foram excluídos!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro: {e}", "danger")
    return redirect(url_for("controle_caixa"))

from datetime import date
from flask import render_template, session, redirect, url_for, flash
from models import Pedido, Produto, Usuario, Loja
from sqlalchemy import func

from datetime import date
from sqlalchemy import func

from datetime import date
from flask import render_template, session, redirect, url_for, flash
from models import Pedido, Produto, Usuario, Loja
from sqlalchemy import func

from datetime import date
from flask import render_template, session, redirect, url_for, flash
from sqlalchemy import func

@app.route("/dashboard_admin")
def dashboard_admin():
    if session.get("usuario_tipo") != "admin":
        flash("Acesso negado", "danger")
        return redirect(url_for("home"))

    hoje = date.today()
    loja_id = session.get("loja_id")

    # 👥 Usuários da loja atual
    usuarios = Usuario.query.filter_by(loja_id=loja_id).order_by(Usuario.nome.asc()).all()

    # 📦 Produtos e pedidos da loja atual
    total_produtos = Produto.query.filter_by(loja_id=loja_id).count()
    total_pedidos = Pedido.query.filter_by(loja_id=loja_id).count()

    pedidos_loja_hoje = Pedido.query.filter(
        Pedido.loja_id == loja_id,
        func.date(Pedido.data) == hoje
    ).all()

    pedidos_finalizados = sum(1 for p in pedidos_loja_hoje if p.status == "finalizado")
    pedidos_cancelados = sum(1 for p in pedidos_loja_hoje if p.status == "cancelado")
    faturamento_total = sum(p.total or 0 for p in pedidos_loja_hoje if p.status == "finalizado")

    # 🌍 Pedidos globais (todas as lojas)
    pedidos_global = Pedido.query.filter(
        Pedido.status == "finalizado",
        func.date(Pedido.data) == hoje
    ).count()

    faturamento_global = db.session.query(func.sum(Pedido.total)).filter(
        Pedido.status == "finalizado",
        func.date(Pedido.data) == hoje
    ).scalar() or 0

    # ⚠️ Estoque baixo por loja
    alertas_por_loja = {}
    lojas = Loja.query.order_by(Loja.nome.asc()).all()
    for loja in lojas:
        produtos_baixos = Produto.query.filter(
            Produto.loja_id == loja.id,
            Produto.estoque <= Produto.estoque_minimo  # ✅ Corrigido aqui
        ).order_by(Produto.nome.asc()).all()

        if produtos_baixos:
            alertas_por_loja[loja.nome] = produtos_baixos

    return render_template("dashboard_admin.html",
        usuarios=usuarios,
        total_produtos=total_produtos,
        total_pedidos=total_pedidos,
        pedidos_finalizados=pedidos_finalizados,
        pedidos_cancelados=pedidos_cancelados,
        faturamento_total=faturamento_total,
        pedidos_global=pedidos_global,
        faturamento_global=faturamento_global,
        alertas_por_loja=alertas_por_loja,
        lojas=lojas
    )

@app.route("/alertas_estoque")
def alertas_estoque():
    alertas_por_loja = {}
    lojas_dict = {}

    lojas = Loja.query.order_by(Loja.nome.asc()).all()

    for loja in lojas:
        produtos_criticos = Produto.query.filter(
            Produto.loja_id == loja.id,
            Produto.estoque <= Produto.estoque_minimo
        ).order_by(Produto.nome.asc()).all()

        if produtos_criticos:
            alertas_por_loja[loja.nome] = produtos_criticos
            lojas_dict[loja.nome] = loja.id  # para gerar link da loja no HTML

    return render_template("alertas_estoque.html",
        alertas_por_loja=alertas_por_loja,
        lojas_dict=lojas_dict
    )

@app.route("/pedir_senha")
def pedir_senha():
    return render_template("pedir_senha.html")

@app.route("/verificar_senha", methods=["POST"])
def verificar_senha():
    senha_digitada = request.form.get("senha_master")
    if senha_digitada == SENHA_MASTER:
        session["autorizado_estoque"] = True
        return redirect(url_for("dashboard_admin"))
    flash("Senha incorreta", "danger")
    return redirect(url_for("pedir_senha"))


# ---------------------- CLIENTES ---------------------- #
@app.route("/cadastrar_cliente", methods=["GET", "POST"])
def cadastrar_cliente():
    if request.method == "POST":
        nome = request.form.get("nome")
        if not nome:
            flash("Nome é obrigatório", "warning")
        else:
            novo_cliente = Cliente(nome=nome, loja_id=session["loja_id"])
            db.session.add(novo_cliente)
            db.session.commit()
            flash(f"Cliente '{nome}' cadastrado com sucesso!", "success")
            return redirect(url_for("cadastrar_cliente"))
    return render_template("clientes/cadastrar.html")

@app.route("/editar_cliente/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if cliente.loja_id != session["loja_id"]:
        flash("Cliente não pertence à sua loja", "danger")
        return redirect(url_for("listar_clientes"))

    if request.method == "POST":
        novo_nome = request.form.get("nome")
        if not novo_nome:
            flash("Nome não pode ficar vazio", "warning")
            return redirect(url_for("editar_cliente", id=id))

        cliente.nome = novo_nome
        db.session.commit()
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for("listar_clientes"))

    return render_template("clientes/editar.html", cliente=cliente)

@app.route("/excluir_cliente/<int:id>", methods=["POST"])
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if cliente.loja_id != session["loja_id"]:
        flash("Cliente não pertence à sua loja", "danger")
        return redirect(url_for("listar_clientes"))

    if cliente.pedidos.count() > 0:
        flash("Não é possível excluir cliente com pedidos vinculados.", "danger")
        return redirect(url_for("listar_clientes"))

    db.session.delete(cliente)
    db.session.commit()
    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for("listar_clientes"))


## atualizando daki##

@app.route("/clientes", methods=["GET", "POST"])
def listar_clientes():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    usuario = Usuario.query.get(session["usuario_id"])
    lojas = Loja.query.order_by(Loja.nome.asc()).all()

    if request.method == "POST":
        nome = request.form.get("nome")
        telefone = request.form.get("telefone")
        email = request.form.get("email")
        loja_id = request.form.get("loja_id") if usuario.tipo == "admin" else usuario.loja_id

        novo_cliente = Cliente(nome=nome, telefone=telefone, email=email, loja_id=loja_id)
        db.session.add(novo_cliente)
        db.session.commit()
        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for("listar_clientes"))

    clientes = Cliente.query.filter_by(loja_id=usuario.loja_id).all() if usuario.tipo != "admin" else Cliente.query.all()

    return render_template("clientes.html",
        clientes=clientes,
        lojas=lojas,
        usuario=usuario
    )

@app.route("/pedidos_cliente/<int:id>")
def pedidos_cliente(id):
    if not session.get("usuario_id"):
        flash("Você precisa estar logado", "warning")
        return redirect(url_for("login"))

    cliente = Cliente.query.get_or_404(id)
    pedidos = Pedido.query.filter_by(cliente_id=id).order_by(Pedido.data.desc()).all()

    return render_template("pedidos_cliente.html",
        cliente=cliente,
        pedidos=pedidos
    )


# ---------------------- PEDIDOS DO CLIENTE ---------------------- #
@app.route("/clientes/<int:cliente_id>/pedidos", methods=["GET", "POST"])
def pedidos_do_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if cliente.loja_id != session["loja_id"]:
        flash("Cliente não pertence à sua loja", "danger")
        return redirect(url_for("listar_clientes"))

    if request.method == "POST":
        senha = request.form.get("senha_master")
        if senha != SENHA_MASTER:
            flash("Senha incorreta!", "danger")
            return redirect(url_for("pedidos_do_cliente", cliente_id=cliente_id))

        pedidos = Pedido.query.filter_by(cliente_id=cliente_id, loja_id=session["loja_id"]).all()
        for pedido in pedidos:
            db.session.delete(pedido)
        db.session.commit()
        flash(f"{len(pedidos)} pedidos excluídos do cliente!", "success")
        return redirect(url_for("pedidos_do_cliente", cliente_id=cliente_id))

    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    imprimir = request.args.get("imprimir") == "1"

    query = Pedido.query.filter_by(cliente_id=cliente_id, loja_id=session["loja_id"])

    if status:
        query = query.filter(Pedido.status == status)

    try:
        if data_inicio:
            query = query.filter(Pedido.data >= datetime.strptime(data_inicio, "%Y-%m-%d"))
        if data_fim:
            query = query.filter(Pedido.data <= datetime.strptime(data_fim, "%Y-%m-%d"))
    except ValueError:
        flash("Formato de data inválido", "danger")

    pedidos = query.order_by(Pedido.data.desc()).all()

    if imprimir:
        from collections import defaultdict
        from decimal import Decimal

        resumo = {
            "total_geral": Decimal("0.00"),
            "total_fiado": Decimal("0.00"),
            "por_status": defaultdict(Decimal),
            "por_forma_pagamento": defaultdict(Decimal)
        }

        for pedido in pedidos:
            valor = Decimal(str(pedido.total))
            resumo["por_status"][pedido.status] += valor
            resumo["por_forma_pagamento"][pedido.forma_pagamento] += valor
            if pedido.status != "cancelado":
                resumo["total_geral"] += valor
                if pedido.fiado:
                    resumo["total_fiado"] += valor

        return render_template("clientes/imprimir_pedidos.html",
            cliente=cliente,
            pedidos=pedidos,
            status=status,
            data_inicio=data_inicio,
            data_fim=data_fim,
            agora=datetime.now(),
            resumo=resumo
        )

    return render_template("clientes/pedidos_cliente.html",
        cliente=cliente,
        pedidos=pedidos,
        status=status,
        data_inicio=data_inicio,
        data_fim=data_fim
    )

# ---------------------- FIADOS ---------------------- #
@app.route("/marcar_pago/<int:pedido_id>", methods=["POST"])
def marcar_pago(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.loja_id != session["loja_id"]:
        return jsonify({"success": False, "message": "Pedido não pertence à sua loja"}), 403
    if not pedido.fiado:
        return jsonify({"success": False, "message": "Pedido já está pago"}), 400
    pedido.fiado = False
    db.session.commit()
    return jsonify({"success": True, "message": "Pedido marcado como pago"})

@app.route("/reverter_pago/<int:pedido_id>", methods=["POST"])
def reverter_pago(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.loja_id != session["loja_id"]:
        return jsonify({"success": False, "message": "Pedido não pertence à sua loja"}), 403
    if pedido.fiado:
        return jsonify({"success": False, "message": "Pedido já está fiado"}), 400
    pedido.fiado = True
    db.session.commit()
    return jsonify({"success": True, "message": "Pedido revertido para fiado"})

@app.route("/excluir_vendas", methods=["POST"])
def excluir_vendas():
    senha = request.form.get("senha_master")
    if senha != SENHA_MASTER:
        flash("Senha incorreta!", "danger")
        return redirect(url_for("dashboard_admin"))

    fiados = Pedido.query.filter_by(fiado=True, loja_id=session["loja_id"]).all()
    for pedido in fiados:
        db.session.delete(pedido)

    db.session.commit()
    flash(f"{len(fiados)} pedidos fiado foram excluídos!", "success")
    return redirect(url_for("dashboard_admin"))


# ---------------------- ROTA DE LOJAS (EXEMPLO) ---------------------- #
@app.route("/lojas")
def lojas():
    todas_lojas = Loja.query.order_by(Loja.nome.asc()).all()

# ---------------------- INICIAR APP ---------------------- #
# No final do app.py
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Popular lojas se necessário
        if Loja.query.count() == 0:
            lojas = [
                Loja(nome="Loja A", endereco="Grupo Vix"),
                Loja(nome="Loja B", endereco="Grupo Vix"),
                Loja(nome="Loja C", endereco="Grupo Vix"),
                Loja(nome="Loja D", endereco="Grupo Vix")
            ]
            db.session.add_all(lojas)
            db.session.commit()

    app.run(debug=True)
