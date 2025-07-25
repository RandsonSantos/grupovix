// 🔹 Variáveis globais
let pedido = [];
let total = 0;

// 🔹 Lista de produtos disponíveis
const produtosDataElement = document.getElementById("produtos-data");
const produtosDisponiveis = produtosDataElement ? JSON.parse(produtosDataElement.textContent) : [];

// 🔹 Adiciona um item ao pedido
function adicionarAoPedido(id, nome, preco, quantidade) {
  quantidade = parseInt(quantidade);

  if (isNaN(quantidade) || quantidade <= 0) {
    return alert("Informe uma quantidade válida maior que zero.");
  }

  const estoqueElement = document.getElementById(`estoque_${id}`);
  const estoqueAtual = parseInt(estoqueElement.textContent);

  if (quantidade > estoqueAtual) {
    return alert("Estoque insuficiente para esse item.");
  }

  estoqueElement.textContent = estoqueAtual - quantidade;

  pedido.push({ id, nome, preco, quantidade });
  atualizarListaPedido();
}

// 🔁 Atualiza a lista de itens no carrinho
function atualizarListaPedido() {
  const lista = document.getElementById("lista-pedido");
  const totalElement = document.getElementById("total");
  lista.innerHTML = "";

  total = pedido.reduce((acc, item) => acc + item.preco * item.quantidade, 0);
  totalElement.textContent = total.toFixed(2);

  pedido.forEach((item, i) => {
    const li = document.createElement("li");
    li.className = "list-group-item";
    li.innerHTML = `${item.nome} (x${item.quantidade}) - R$ ${(item.preco * item.quantidade).toFixed(2)}
      <button class="btn btn-danger btn-sm float-end" onclick="removerItem(${i})">❌</button>`;
    lista.appendChild(li);
  });

  document.getElementById("pedido-input").value = JSON.stringify(pedido);
}

// ❌ Remove item do pedido
function removerItem(index) {
  const itemRemovido = pedido.splice(index, 1)[0];
  const estoqueElement = document.getElementById(`estoque_${itemRemovido.id}`);
  if (estoqueElement) {
    estoqueElement.textContent = parseInt(estoqueElement.textContent) + itemRemovido.quantidade;
  }
  atualizarListaPedido();
}

// ⌨️ Busca por nome com Enter
function adicionarPorNome(event) {
  if (event.key !== "Enter") return;

  event.preventDefault();
  const input = document.getElementById("produto-input");
  const nomeBusca = input.value.trim().toLowerCase();

  const produto = produtosDisponiveis.find(p => p.nome.toLowerCase().includes(nomeBusca));
  if (!produto) return alert("Produto não encontrado.");

  adicionarAoPedido(produto.id, produto.nome, produto.preco, 1);
  input.value = "";
  input.focus();
}

// 💳 Seleciona forma de pagamento
function selecionarPagamento(metodo, btnSelecionado) {
  document.getElementById("forma-pagamento").value = metodo;

  const botoes = document.querySelectorAll(".btn-group button");
  botoes.forEach(btn => btn.classList.remove("active"));
  btnSelecionado.classList.add("active");

  document.getElementById("cliente_id").required = (metodo === "Fiado");
}

// ✅ Validação final antes de enviar
function validarPagamento() {
  const forma = document.getElementById("forma-pagamento").value;
  const pedidoJSON = document.getElementById("pedido-input").value;

  if (!forma) {
    document.getElementById("erro-pagamento").style.display = "block";
    return false;
  }

  if (!pedidoJSON || pedido.length === 0) {
    alert("Adicione ao menos um produto ao pedido.");
    return false;
  }

  return true;
}

// 🔍 Filtro de produtos na tabela
function filtrarProdutos() {
  const termo = document.getElementById("produto-input").value.toLowerCase();
  const tabela = document.getElementById("tabela-produtos");
  const produtos = document.querySelectorAll(".produto-item");

  tabela.style.display = termo.length ? "block" : "none";

  produtos.forEach(produto => {
    const nome = produto.querySelector("td").textContent.toLowerCase();
    produto.style.display = nome.includes(termo) ? "" : "none";
  });
}

// 🗑️ Cancela uma venda específica (requisição POST)
function cancelarVenda(id) {
  if (confirm("❌ Deseja realmente cancelar esta venda?")) {
    fetch(`/cancelar_venda/${id}`, {
      method: "POST"
    })
    .then(response => response.json())
    .then(data => {
      alert(data.message);
      if (data.success) {
        location.reload();
      }
    })
    .catch((error) => {
      alert("Erro ao comunicar com o servidor.");
      console.error("Erro:", error);
    });
  }
}
