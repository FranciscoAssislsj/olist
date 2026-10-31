"""Olist · visão da operação. A spec está em painel.py.

Execução:
    uv run streamlit run app.py
"""

from datetime import date

import streamlit as st

import painel

MARTS = [
    "kpis",
    "recompra",
    "entrega_no_prazo",
    "vendas_mensais",
    "top_categorias",
    "mix_pagamento",
    "ticket_medio_por_estado",
    "clientes_por_uf",
    "nota_por_categoria",
    "vendedores_pareto",
]
COMANDO = "uv run python -m pipeline.marts"


@st.cache_data
def ler() -> dict:
    return painel.ler(MARTS)


st.set_page_config(page_title="Olist · visão da operação", layout="wide")

# Checar antes de conectar: em read_only, o connect falharia sem dizer o que fazer.
if not painel.ARQUIVO_BANCO.is_file():
    st.error(f"Banco não encontrado: olist.duckdb. Rode: `{COMANDO}`")
    st.stop()

dados = ler()
faltando = [nome for nome in MARTS if nome not in dados]
if faltando:
    lista = ", ".join(f"marts.{nome}" for nome in faltando)
    st.error(f"Marts não encontrados: {lista}. Rode: `{COMANDO}`")
    st.stop()

kpis = dados["kpis"].iloc[0]
vendas = dados["vendas_mensais"].sort_values("mes")

# ---------------------------------------------------------------- cabeçalho

esquerda, direita = st.columns([2, 1])
esquerda.title("Olist · visão da operação")
with direita:
    meses = [m.date() for m in vendas["mes"]]
    inicio, fim = st.select_slider(
        "Período",
        options=meses,
        value=(date(2017, 1, 1), date(2018, 8, 1)),
        format_func=painel.mes,
    )
    st.caption("os cartões valem para o período inteiro")
    if st.button("Recarregar dados"):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------------- faixa 1

recompra = dados["recompra"]
um_pedido = recompra[recompra["pedidos_por_cliente"] == 1]["pct_clientes"].iloc[0]

cartoes = [
    ("Ticket médio · receita por pedido", painel.reais(kpis["ticket_medio"])),
    ("Cancelados · % de todos os pedidos", painel.pct(kpis["pct_cancelados"], 2)),
    ("Peso do frete · % do frete no valor pago", painel.pct(kpis["pct_frete"], 1)),
    # A única conta da página: o mart 05 guarda quem comprou uma vez só.
    ("Recompra · % de clientes com 2+ pedidos", painel.pct(100 - um_pedido, 2)),
    (
        "No prazo · % dos entregues",
        painel.pct(dados["entrega_no_prazo"]["pct_no_prazo"].iloc[0], 1),
    ),
    (
        "Dias até entregar · média, da compra à entrega",
        painel.numero(kpis["dias_entrega"], 1),
    ),
    ("Nota média · avaliações de 1 a 5", painel.numero(kpis["nota_media"], 2)),
]
# Sete cartões numa linha cortam o rótulo com reticências, e a definição
# sumiria; o st.metric não tem opção para quebrar a linha.
st.html(
    "<style>[data-testid='stMetricLabel'], [data-testid='stMetricLabel'] * "
    "{white-space: normal !important; overflow: visible !important;}</style>"
)
for coluna, (rotulo, valor) in zip(st.columns(len(cartoes)), cartoes):
    coluna.metric(rotulo, valor, border=True, height="stretch")

# ---------------------------------------------------------------- faixa 2

no_periodo = vendas[(vendas["mes"].dt.date >= inicio) & (vendas["mes"].dt.date <= fim)]
st.plotly_chart(painel.faturamento_mensal(no_periodo), width="stretch")

# ---------------------------------------------------------------- faixas 3 e 4

faixa_3 = [
    painel.receita_por_categoria(dados["top_categorias"]),
    painel.mix_pagamento(dados["mix_pagamento"]),
    painel.ticket_por_uf(dados["ticket_medio_por_estado"]),
]
faixa_4 = [
    painel.clientes_por_uf(dados["clientes_por_uf"]),
    painel.nota_por_categoria(dados["nota_por_categoria"]),
    painel.concentracao_vendedores(dados["vendedores_pareto"]),
]
for faixa in (faixa_3, faixa_4):
    for coluna, figura in zip(st.columns(3), faixa):
        coluna.plotly_chart(figura, width="stretch")
