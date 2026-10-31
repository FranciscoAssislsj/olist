"""Painel: leitura dos marts, formatação e gráficos. Não importa streamlit.

Usado por app.py (a página) e pelo relatório HTML.

SPEC (e por que cada regra existe)

1. LEITURA
   ler(marts) -> dict nome -> DataFrame. Para cada nome, só
   SELECT * FROM marts.<nome>. Nenhuma outra SQL.
   Conexão com duckdb.connect("olist.duckdb", read_only=True), aberta e
   fechada dentro de ler().
   Por quê: conexão aberta segura o arquivo, e o pipeline.marts não
   consegue gravar com o painel de pé.

2. NENHUM CÁLCULO
   Proibido em painel.py e app.py: agrupar, somar, tirar média, contar,
   juntar tabelas, pivotar, e qualquer conta entre colunas. Permitido: ordenar, filtrar linhas,
   head(n), renomear coluna e formatar texto.
   Por quê: número novo na tela exige um .sql novo em marts. Se faltar
   algum número, o que falta é um mart, não uma linha de pandas.
   Exceção única: Recompra = 100 - recompra.pct_clientes da linha
   pedidos_por_cliente = 1, porque o mart 05 guarda o complemento.

3. LAYOUT (app.py) — de cima para baixo, layout="wide"
   Cabeçalho: título "Olist · visão da operação" à esquerda; à direita,
     filtro de período (seção 5).
   Faixa 1: sete cartões (st.metric), nesta ordem, cada rótulo com a
     definição curta: Ticket médio (kpis.ticket_medio, reais) ·
     Cancelados (kpis.pct_cancelados, 2 casas) · Peso do frete
     (kpis.pct_frete, 1 casa) · Recompra (2 casas) · No prazo
     (entrega_no_prazo.pct_no_prazo, 1 casa) · Dias até entregar
     (kpis.dias_entrega, 1 casa) · Nota média (kpis.nota_media, 2 casas).
   Faixa 2, largura inteira: faturamento mensal, linha com marcadores.
   Faixa 3, três colunas iguais: receita por categoria (top 10, barras
     horizontais, maior em cima); mix de pagamento (barras por pct_valor);
     ticket médio por UF (barras horizontais, maior em cima).
   Faixa 4, três colunas iguais: clientes por UF (barras horizontais,
     maior em cima); nota por categoria (as 10 primeiras por posicao_pior,
     pontos, pior em cima); concentração de vendedores (linha de
     pct_acumulado por posicao, com linha horizontal tracejada em 80).
   Cada gráfico: título com o número do mart ("01 · Faturamento mensal"),
   uma cor só, eixo com unidade. width="stretch".
   Por quê: o número do mart no título leva direto ao .sql que gerou o
   gráfico; use_container_width está descontinuado.

4. FORMATO, funções puras, sem streamlit e sem banco
   reais(valor, casas=2)  -> "R$ 1.003.862,14"
   pct(valor, casas=1)    -> "93,2%"
   numero(valor, casas=0) -> "96.470"
   Milhar com ponto, decimal com vírgula, sempre. Sem locale do sistema.
   Por quê: o resultado não pode depender da máquina de quem roda.
   Uma função por gráfico, recebendo o DataFrame e devolvendo a figura
   plotly.
   Por quê: o relatório HTML reaproveita as mesmas funções.

5. FILTRO DE PERÍODO (app.py)
   st.select_slider com os meses de vendas_mensais, padrão de jan/2017 a
   ago/2018. Recorta só as linhas do gráfico de faturamento. Os cartões e
   os outros gráficos não mudam, e a página diz isso embaixo do filtro:
   "os cartões valem para o período inteiro".
   Por quê: recortar linha é SELECT; recalcular cartão por período seria
   regra de negócio fora do SQL.

6. CACHE E ERRO (app.py)
   Leitura com st.cache_data. Um botão "Recarregar dados" limpa o cache.
   Sem olist.duckdb, ou faltando qualquer mart da lista do item 3: st.error
   dizendo quais e o comando "uv run python -m pipeline.marts", e st.stop().
   Por quê: o cache evita reler o banco a cada clique; o botão traz os
   marts novos depois de rodar o pipeline sem reiniciar a página.

CRITÉRIOS DE ACEITE
   - Os sete cartões mostram: R$ 137,42 · 0,63% · 14,2% · 3,04% · 93,2% ·
     12,5 · 4,09.
   - O faturamento abre com 20 meses (jan/2017 a ago/2018) e, com o filtro
     aberto até as pontas, mostra os 24.
   - Top 10 de categorias com health_beauty em cima; nota com
     office_furniture em cima; ticket por UF com PB em cima e SP embaixo.
   - Uma busca pelos métodos de agrupar, somar, tirar média e juntar do
     pandas em painel.py e app.py não encontra nada. (Os nomes não aparecem
     aqui de propósito: senão a busca acharia esta própria docstring.)
   - Com o painel de pé, uv run python -m pipeline.marts roda sem erro de lock.
"""

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ARQUIVO_BANCO = Path(__file__).resolve().parent / "olist.duckdb"

COR = "#1f6f50"
ALTURA_LINHA = 300
ALTURA_GRADE = 560  # cabe as 27 UFs sem encavalar os rótulos

# Fixo no código, e não via strftime("%b"): o nome do mês sairia do locale.
MESES = (
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)


def ler(marts: list[str]) -> dict[str, pd.DataFrame]:
    """Lê cada mart que existir. Um mart ausente fica fora do dict."""
    dados = {}
    con = duckdb.connect(str(ARQUIVO_BANCO), read_only=True)
    try:
        for nome in marts:
            try:
                dados[nome] = con.execute(f'SELECT * FROM marts."{nome}"').df()
            except duckdb.CatalogException:
                pass
    finally:
        con.close()
    return dados


# ---------------------------------------------------------------- formato


def _br(valor: float, casas: int) -> str:
    # Formata no padrão do Python (1,234.5) e troca os separadores.
    return f"{valor:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def reais(valor: float, casas: int = 2) -> str:
    return f"R$ {_br(valor, casas)}"


def pct(valor: float, casas: int = 1) -> str:
    return f"{_br(valor, casas)}%"


def numero(valor: float, casas: int = 0) -> str:
    return _br(valor, casas)


def mes(dia: date) -> str:
    """2017-11-01 -> "nov/2017"."""
    return f"{MESES[dia.month - 1]}/{dia.year}"


# ---------------------------------------------------------------- gráficos


def _estilo(fig: go.Figure, titulo: str, altura: int) -> go.Figure:
    fig.update_traces(marker_color=COR)
    fig.update_layout(
        title=titulo,
        height=altura,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        # Separadores do plotly em eixos e hover: decimal vírgula, milhar ponto.
        separators=",.",
        showlegend=False,
    )
    return fig


def _barras_deitadas(
    df: pd.DataFrame, x: str, y: str, titulo: str, rotulo_x: str, rotulo_y: str
) -> go.Figure:
    """Barras horizontais com a maior em cima."""
    df = df.sort_values(x, ascending=False)
    fig = px.bar(df, x=x, y=y, orientation="h", labels={x: rotulo_x, y: rotulo_y})
    # O plotly desenha a primeira linha embaixo; invertido, a maior fica em cima.
    fig.update_yaxes(autorange="reversed")
    return _estilo(fig, titulo, ALTURA_GRADE)


def faturamento_mensal(df: pd.DataFrame) -> go.Figure:
    df = df.sort_values("mes")
    fig = px.line(
        df,
        x=[mes(m) for m in df["mes"]],
        y="receita",
        markers=True,
        labels={"x": "Mês", "receita": "Receita (R$)"},
    )
    fig.update_traces(line_color=COR)
    return _estilo(fig, "01 · Faturamento mensal", ALTURA_LINHA)


def receita_por_categoria(df: pd.DataFrame) -> go.Figure:
    df = df.sort_values("receita", ascending=False).head(10)
    return _barras_deitadas(
        df,
        "receita",
        "categoria",
        "02 · Receita por categoria · top 10",
        "Receita (R$)",
        "Categoria",
    )


def mix_pagamento(df: pd.DataFrame) -> go.Figure:
    return _barras_deitadas(
        df,
        "pct_valor",
        "tipo",
        "07 · Mix de pagamento",
        "% do valor pago",
        "Tipo de pagamento",
    )


def ticket_por_uf(df: pd.DataFrame) -> go.Figure:
    return _barras_deitadas(
        df,
        "ticket_medio",
        "uf",
        "06 · Ticket médio por UF",
        "Ticket médio (R$)",
        "UF do cliente",
    )


def clientes_por_uf(df: pd.DataFrame) -> go.Figure:
    return _barras_deitadas(
        df, "clientes", "uf", "12 · Clientes por UF", "Clientes (pessoas)", "UF"
    )


def nota_por_categoria(df: pd.DataFrame) -> go.Figure:
    # Ordena por posicao_pior e categoria: com empate no rank, a ordem não muda
    # entre execuções.
    df = df.sort_values(["posicao_pior", "categoria"]).head(10)
    fig = px.scatter(
        df,
        x="nota_media",
        y="categoria",
        labels={"nota_media": "Nota média (1 a 5)", "categoria": "Categoria"},
    )
    fig.update_traces(marker_size=11)
    fig.update_yaxes(autorange="reversed")
    return _estilo(fig, "04 · Nota por categoria · 10 piores", ALTURA_GRADE)


def concentracao_vendedores(df: pd.DataFrame) -> go.Figure:
    df = df.sort_values("posicao")
    fig = px.line(
        df,
        x="posicao",
        y="pct_acumulado",
        labels={
            "posicao": "Vendedores, do maior para o menor (posição)",
            "pct_acumulado": "% acumulado da receita",
        },
    )
    fig.update_traces(line_color=COR)
    fig.add_hline(y=80, line_dash="dash", line_color=COR, annotation_text="80%")
    return _estilo(fig, "09 · Concentração de vendedores", ALTURA_GRADE)
