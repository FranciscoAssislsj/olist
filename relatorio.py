"""Olist · visão da operação, em um HTML só. A spec está em painel.py.

Mesmas quatro faixas do app.py, sem filtro: o faturamento mostra o período
padrão da página, jan/2017 a ago/2018.

Execução:
    uv run python relatorio.py
"""

import sys
from datetime import date, datetime
from html import escape
from pathlib import Path

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
ARQUIVO = Path(__file__).resolve().parent / "relatorio.html"
INICIO, FIM = date(2017, 1, 1), date(2018, 8, 1)

ESTILO = """
body {font-family: system-ui, sans-serif; margin: 24px; color: #1a1a1a; background: #fff;}
h1 {margin: 0 0 4px;}
.periodo {color: #555; margin: 0 0 20px;}
.cartoes {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin-bottom: 20px;}
.cartao {border: 1px solid #ddd; border-radius: 8px; padding: 12px;}
.rotulo {font-size: 13px; color: #555;}
.valor {font-size: 28px; margin-top: 6px;}
.faixa {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px;
  margin-bottom: 20px;}
footer {color: #555; font-size: 13px; margin-top: 12px;}
"""


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    # Checar antes de conectar: em read_only, o connect falharia sem dizer o que fazer.
    if not painel.ARQUIVO_BANCO.is_file():
        print(f"Banco não encontrado: olist.duckdb. Rode: {COMANDO}")
        return 1
    dados = painel.ler(MARTS)
    faltando = [nome for nome in MARTS if nome not in dados]
    if faltando:
        lista = ", ".join(f"marts.{nome}" for nome in faltando)
        print(f"Marts não encontrados: {lista}. Rode: {COMANDO}")
        return 1

    kpis = dados["kpis"].iloc[0]
    recompra = dados["recompra"]
    um_pedido = recompra[recompra["pedidos_por_cliente"] == 1]["pct_clientes"].iloc[0]

    # ------------------------------------------------------------ faixa 1

    cartoes = [
        ("Ticket médio · receita por pedido", painel.reais(kpis["ticket_medio"])),
        ("Cancelados · % de todos os pedidos", painel.pct(kpis["pct_cancelados"], 2)),
        ("Peso do frete · % do frete no valor pago", painel.pct(kpis["pct_frete"], 1)),
        # A única conta do relatório: o mart 05 guarda quem comprou uma vez só.
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
    html_cartoes = "".join(
        f'<div class="cartao"><div class="rotulo">{escape(rotulo)}</div>'
        f'<div class="valor">{escape(valor)}</div></div>'
        for rotulo, valor in cartoes
    )

    # ------------------------------------------------------------ faixas 2 a 4

    vendas = dados["vendas_mensais"].sort_values("mes")
    no_periodo = vendas[
        (vendas["mes"].dt.date >= INICIO) & (vendas["mes"].dt.date <= FIM)
    ]
    periodo = f"{painel.mes(INICIO)} a {painel.mes(FIM)}"
    faturamento = painel.faturamento_mensal(no_periodo)
    faturamento.update_layout(title=f"01 · Faturamento mensal · {periodo}")

    faixas = [
        [faturamento],
        [
            painel.receita_por_categoria(dados["top_categorias"]),
            painel.mix_pagamento(dados["mix_pagamento"]),
            painel.ticket_por_uf(dados["ticket_medio_por_estado"]),
        ],
        [
            painel.clientes_por_uf(dados["clientes_por_uf"]),
            painel.nota_por_categoria(dados["nota_por_categoria"]),
            painel.concentracao_vendedores(dados["vendedores_pareto"]),
        ],
    ]
    # div_id fixo: sem ele o plotly sorteia um id a cada execução, e o arquivo
    # muda sem o dado mudar. A biblioteca vem do CDN uma vez só, no primeiro.
    html_faixas = []
    n = 0
    for faixa in faixas:
        divs = []
        for figura in faixa:
            n += 1
            divs.append(
                figura.to_html(
                    full_html=False,
                    include_plotlyjs="cdn" if n == 1 else False,
                    div_id=f"g{n:02d}",
                )
            )
        classe = "faixa" if len(faixa) > 1 else "faixa-inteira"
        html_faixas.append(f'<div class="{classe}">{"".join(divs)}</div>')

    # O arquivo não fala com o banco: quem lê precisa saber de quando é o número.
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Olist · visão da operação</title>
<style>{ESTILO}</style>
</head>
<body>
<h1>Olist · visão da operação</h1>
<p class="periodo">Faturamento de {periodo}; os cartões valem para o período inteiro.</p>
<div class="cartoes">{html_cartoes}</div>
{"".join(html_faixas)}
<footer>Dados de {gerado}</footer>
</body>
</html>
"""
    ARQUIVO.write_text(html, encoding="utf-8")
    print(f"{ARQUIVO} · {ARQUIVO.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
