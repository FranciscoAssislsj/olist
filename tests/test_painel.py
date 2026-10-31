"""painel.py: formato, leitura dos marts e gráficos, com DataFrames inventados."""

from datetime import date

import duckdb
import pandas as pd

from olist import painel

# ---------------------------------------------------------------- formato


def test_reais_usa_ponto_no_milhar_e_virgula_no_decimal():
    assert painel.reais(1234567.891) == "R$ 1.234.567,89"


def test_reais_completa_os_centavos():
    assert painel.reais(5) == "R$ 5,00"


def test_reais_aceita_outra_quantidade_de_casas():
    assert painel.reais(1999.6, 0) == "R$ 2.000"


def test_pct_tem_uma_casa_por_padrao():
    assert painel.pct(12.34) == "12,3%"


def test_pct_aceita_duas_casas():
    assert painel.pct(3.14159, 2) == "3,14%"


def test_pct_acima_de_mil_tambem_leva_ponto():
    assert painel.pct(1500) == "1.500,0%"


def test_numero_sem_casas_por_padrao():
    assert painel.numero(1234567) == "1.234.567"


def test_numero_com_uma_casa():
    assert painel.numero(12.34, 1) == "12,3"


def test_numero_negativo_mantem_o_sinal():
    assert painel.numero(-1234.5, 1) == "-1.234,5"


def test_mes_sai_abreviado_em_portugues():
    assert painel.mes(date(2017, 11, 1)) == "nov/2017"
    assert painel.mes(date(2018, 2, 1)) == "fev/2018"


# ---------------------------------------------------------------- leitura


def test_ler_devolve_os_marts_que_existem_e_ignora_os_ausentes(tmp_path, monkeypatch):
    banco = tmp_path / "t.duckdb"
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        # Duas linhas inventadas; o mart "nao_existe" não é criado.
        con.execute("CREATE TABLE marts.kpis AS SELECT * FROM (VALUES (1, 'a'), (2, 'b')) t(n, s)")
    monkeypatch.setattr(painel, "ARQUIVO_BANCO", banco)

    dados = painel.ler(["kpis", "nao_existe"])

    assert list(dados) == ["kpis"]
    assert dados["kpis"].to_dict("list") == {"n": [1, 2], "s": ["a", "b"]}


def test_ler_fecha_a_conexao_e_libera_o_banco_para_escrita(tmp_path, monkeypatch):
    banco = tmp_path / "t.duckdb"
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute("CREATE TABLE marts.kpis AS SELECT 1 AS n")
    monkeypatch.setattr(painel, "ARQUIVO_BANCO", banco)

    painel.ler(["kpis"])

    # Com a conexão read_only ainda aberta, abrir para escrita no mesmo
    # processo estouraria por configuração diferente.
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE TABLE marts.nova AS SELECT 2 AS n")
        assert con.execute("SELECT n FROM marts.nova").fetchone() == (2,)


# ---------------------------------------------------------------- gráficos


def pontos(fig):
    return len(fig.data[0].x)


def test_faturamento_mensal_tem_um_ponto_por_mes_em_ordem():
    df = pd.DataFrame(
        {
            # Fora de ordem de propósito: o gráfico ordena por mês.
            "mes": pd.to_datetime(["2017-03-01", "2017-01-01", "2017-02-01"]),
            "pedidos": [3, 1, 2],
            "receita": [30.0, 10.0, 20.0],
        }
    )
    fig = painel.faturamento_mensal(df)

    assert pontos(fig) == 3
    assert list(fig.data[0].x) == ["jan/2017", "fev/2017", "mar/2017"]
    assert list(fig.data[0].y) == [10.0, 20.0, 30.0]
    assert fig.layout.title.text == "01 · Faturamento mensal"


def test_receita_por_categoria_tem_um_ponto_por_linha_e_a_maior_em_cima():
    df = pd.DataFrame({"categoria": ["a", "b", "c"], "receita": [5.0, 50.0, 20.0]})
    fig = painel.receita_por_categoria(df)

    assert pontos(fig) == 3
    assert fig.data[0].y[0] == "b"  # primeira linha, desenhada em cima pelo eixo invertido
    assert fig.layout.yaxis.autorange == "reversed"
    assert fig.layout.title.text.startswith("02 · ")


def test_receita_por_categoria_mostra_so_as_dez_maiores():
    # Doze categorias: k00 tem a menor receita e k01 a segunda menor; ficam fora.
    df = pd.DataFrame(
        {"categoria": [f"k{i:02d}" for i in range(12)], "receita": [float(i) for i in range(12)]}
    )
    fig = painel.receita_por_categoria(df)

    assert pontos(fig) == 10
    assert "k00" not in fig.data[0].y
    assert "k01" not in fig.data[0].y


def test_mix_pagamento_tem_um_ponto_por_tipo():
    df = pd.DataFrame({"tipo": ["boleto", "credit_card"], "pct_valor": [20.0, 80.0]})
    fig = painel.mix_pagamento(df)

    assert pontos(fig) == 2
    assert fig.data[0].y[0] == "credit_card"
    assert fig.layout.title.text.startswith("07 · ")


def test_ticket_por_uf_tem_um_ponto_por_uf():
    df = pd.DataFrame({"uf": ["SP", "PB", "RJ"], "ticket_medio": [100.0, 200.0, 150.0]})
    fig = painel.ticket_por_uf(df)

    assert pontos(fig) == 3
    assert list(fig.data[0].y) == ["PB", "RJ", "SP"]
    assert fig.layout.title.text.startswith("06 · ")


def test_clientes_por_uf_tem_um_ponto_por_uf():
    df = pd.DataFrame({"uf": ["AC", "SP"], "clientes": [3, 40]})
    fig = painel.clientes_por_uf(df)

    assert pontos(fig) == 2
    assert fig.data[0].y[0] == "SP"
    assert fig.layout.title.text.startswith("12 · ")


def test_nota_por_categoria_tem_um_ponto_por_linha_e_a_pior_em_cima():
    df = pd.DataFrame(
        {
            "categoria": ["boa", "ruim", "media"],
            "pedidos_avaliados": [100, 100, 100],
            "nota_media": [4.5, 3.0, 4.0],
            "posicao_pior": [3, 1, 2],
        }
    )
    fig = painel.nota_por_categoria(df)

    assert pontos(fig) == 3
    assert list(fig.data[0].y) == ["ruim", "media", "boa"]
    assert fig.layout.yaxis.autorange == "reversed"
    assert fig.layout.title.text.startswith("04 · ")


def test_nota_por_categoria_desempata_a_posicao_pela_categoria():
    df = pd.DataFrame(
        {
            # Duas empatadas em 1º: a ordem sai pelo nome, não pela linha.
            "categoria": ["zeta", "alfa"],
            "pedidos_avaliados": [100, 100],
            "nota_media": [3.0, 3.0],
            "posicao_pior": [1, 1],
        }
    )
    fig = painel.nota_por_categoria(df)

    assert list(fig.data[0].y) == ["alfa", "zeta"]


def test_nota_por_categoria_mostra_so_as_dez_piores():
    df = pd.DataFrame(
        {
            "categoria": [f"k{i:02d}" for i in range(11)],
            "pedidos_avaliados": [100] * 11,
            "nota_media": [3.0 + i / 10 for i in range(11)],
            "posicao_pior": list(range(1, 12)),
        }
    )
    fig = painel.nota_por_categoria(df)

    assert pontos(fig) == 10
    assert "k10" not in fig.data[0].y  # a 11ª pior fica fora


def test_concentracao_vendedores_tem_um_ponto_por_vendedor_e_linha_em_80():
    df = pd.DataFrame(
        {
            "vendedor_id": ["v2", "v1", "v3"],
            "posicao": [2, 1, 3],
            "pct_acumulado": [90.0, 60.0, 100.0],
        }
    )
    fig = painel.concentracao_vendedores(df)

    assert pontos(fig) == 3
    assert list(fig.data[0].x) == [1, 2, 3]
    assert [s.y0 for s in fig.layout.shapes] == [80]
    assert fig.layout.shapes[0].line.dash == "dash"
    assert fig.layout.title.text.startswith("09 · ")


def test_graficos_usam_uma_cor_so_e_separadores_brasileiros():
    df = pd.DataFrame({"uf": ["AC", "SP"], "clientes": [3, 40]})
    fig = painel.clientes_por_uf(df)

    assert fig.data[0].marker.color == painel.COR
    assert fig.layout.separators == ",."
    assert fig.layout.showlegend is False
