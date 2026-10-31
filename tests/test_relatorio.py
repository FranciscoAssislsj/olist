"""relatorio.py: HTML gerado em tmp_path a partir de marts inventados."""

import io
import json
import sys
from datetime import datetime

import duckdb

from olist import painel, relatorio


def criar_marts(banco, sem=()):
    """Os dez marts que o relatório lê, com poucas linhas inventadas."""
    sqls = {
        # Uma linha só, como o mart 11.
        "kpis": "SELECT 150.5 AS ticket_medio, 1.25 AS pct_cancelados, 12.0 AS pct_frete, "
        "10.0 AS dias_entrega, 4.2 AS nota_media",
        # 97% compraram uma vez: a recompra é 100 - 97 = 3.
        "recompra": "SELECT * FROM (VALUES (1, 97, 97.0), (2, 3, 3.0)) "
        "t(pedidos_por_cliente, clientes, pct_clientes)",
        "entrega_no_prazo": "SELECT 4 AS entregues, 3 AS no_prazo, 1 AS atrasados, "
        "75.0 AS pct_no_prazo",
        # dez/2016 e set/2018 ficam fora do período padrão jan/2017 a ago/2018.
        "vendas_mensais": "SELECT * FROM (VALUES "
        "(DATE '2016-12-01', 1, 10.0), (DATE '2017-01-01', 2, 20.0), "
        "(DATE '2018-08-01', 3, 30.0), (DATE '2018-09-01', 4, 40.0)) t(mes, pedidos, receita)",
        "top_categorias": "SELECT * FROM (VALUES ('cat_a', 1, 1, 100.0)) "
        "t(categoria, pedidos, itens, receita)",
        "mix_pagamento": "SELECT * FROM (VALUES ('boleto', 1, 1, 10.0, 100.0)) "
        "t(tipo, pagamentos, pedidos, valor, pct_valor)",
        "ticket_medio_por_estado": "SELECT * FROM (VALUES ('SP', 2, 50.0)) "
        "t(uf, pedidos, ticket_medio)",
        "clientes_por_uf": "SELECT * FROM (VALUES ('SP', 2)) t(uf, clientes)",
        "nota_por_categoria": "SELECT * FROM (VALUES ('cat_a', 100, 4.0, 1)) "
        "t(categoria, pedidos_avaliados, nota_media, posicao_pior)",
        "vendedores_pareto": "SELECT * FROM (VALUES ('v1', 'SP', 100.0, 1, 100.0)) "
        "t(vendedor_id, uf, receita, posicao, pct_acumulado)",
    }
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        for nome, sql in sqls.items():
            if nome not in sem:
                con.execute(f"CREATE TABLE marts.{nome} AS {sql}")


def preparar(tmp_path, monkeypatch, sem=()):
    banco = tmp_path / "t.duckdb"
    criar_marts(banco, sem)
    saida_html = tmp_path / "relatorio.html"
    monkeypatch.setattr(painel, "ARQUIVO_BANCO", banco)
    monkeypatch.setattr(relatorio, "ARQUIVO", saida_html)
    return saida_html


def capturar(monkeypatch):
    # Um TextIOWrapper de verdade: main() chama sys.stdout.reconfigure.
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", saida)
    return saida


def lido(saida):
    saida.flush()
    return saida.buffer.getvalue().decode("utf-8")


def no_json(texto):
    """Como o plotly grava o texto no JSON do HTML: não-ASCII e "/" escapados."""
    return json.dumps(texto, ensure_ascii=True)[1:-1].replace('\\"', '"').replace(
        "/", "\\" + "u002f"
    )


def relogio(monkeypatch, momento):
    """Fixa o datetime.now() que o relatório usa no rodapé."""

    class Relogio(datetime):
        @classmethod
        def now(cls, tz=None):
            return momento

    monkeypatch.setattr(relatorio, "datetime", Relogio)


def test_gera_o_arquivo_dentro_de_tmp_path(tmp_path, monkeypatch):
    saida_html = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    codigo = relatorio.main()

    assert codigo == 0
    assert saida_html.is_file()
    assert saida_html.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_rodar_duas_vezes_muda_so_o_rodape(tmp_path, monkeypatch):
    saida_html = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    relogio(monkeypatch, datetime(2026, 1, 1, 9, 0))
    relatorio.main()
    primeira = saida_html.read_text(encoding="utf-8").splitlines()
    relogio(monkeypatch, datetime(2026, 1, 2, 18, 30))  # outro dia, outra hora
    relatorio.main()
    segunda = saida_html.read_text(encoding="utf-8").splitlines()

    diferentes = [(a, b) for a, b in zip(primeira, segunda) if a != b]
    assert len(primeira) == len(segunda)
    assert diferentes == [
        ("<footer>Dados de 01/01/2026 09:00</footer>", "<footer>Dados de 02/01/2026 18:30</footer>")
    ]


def test_cartoes_mostram_os_valores_formatados(tmp_path, monkeypatch):
    saida_html = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    relatorio.main()

    html = saida_html.read_text(encoding="utf-8")
    assert '<div class="valor">R$ 150,50</div>' in html  # ticket médio
    assert '<div class="valor">1,25%</div>' in html  # cancelados, 2 casas
    assert '<div class="valor">12,0%</div>' in html  # frete, 1 casa
    assert '<div class="valor">3,00%</div>' in html  # recompra = 100 - 97
    assert '<div class="valor">75,0%</div>' in html  # no prazo
    assert '<div class="valor">10,0</div>' in html  # dias até entregar
    assert '<div class="valor">4,20</div>' in html  # nota média


def test_faturamento_fica_no_periodo_de_jan_2017_a_ago_2018(tmp_path, monkeypatch):
    saida_html = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    relatorio.main()

    html = saida_html.read_text(encoding="utf-8")
    assert no_json("01 · Faturamento mensal · jan/2017 a ago/2018") in html
    assert no_json('"x":["jan/2017","ago/2018"]') in html  # só os dois meses do período
    assert no_json("dez/2016") not in html
    assert no_json("set/2018") not in html


def test_plotly_vem_do_cdn_uma_vez_so_e_os_ids_sao_fixos(tmp_path, monkeypatch):
    saida_html = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    relatorio.main()

    html = saida_html.read_text(encoding="utf-8")
    assert html.count('src="https://cdn.plot.ly/') == 1
    assert all(f'id="g{n:02d}"' in html for n in range(1, 8))  # sete gráficos


def test_sem_banco_avisa_e_devolve_1_sem_gerar_arquivo(tmp_path, monkeypatch):
    saida_html = tmp_path / "relatorio.html"
    monkeypatch.setattr(painel, "ARQUIVO_BANCO", tmp_path / "nao_existe.duckdb")
    monkeypatch.setattr(relatorio, "ARQUIVO", saida_html)
    saida = capturar(monkeypatch)

    codigo = relatorio.main()

    assert codigo == 1
    assert not saida_html.exists()
    assert not (tmp_path / "nao_existe.duckdb").exists()  # não criou banco vazio
    assert "uv run python -m olist.pipeline.marts" in lido(saida)


def test_mart_faltando_avisa_quais_e_devolve_1(tmp_path, monkeypatch):
    saida_html = preparar(tmp_path, monkeypatch, sem=("kpis", "recompra"))
    saida = capturar(monkeypatch)

    codigo = relatorio.main()

    assert codigo == 1
    assert not saida_html.exists()
    assert "Marts não encontrados: marts.kpis, marts.recompra." in lido(saida)
