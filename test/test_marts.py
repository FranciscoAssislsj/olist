"""pipeline/marts.py e sql/marts/01 e 03, sobre refined inventado em tmp_path."""

import io
import sys
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from pipeline import db, marts
from pipeline.transformacao import MAPA


def preparar(tmp_path, monkeypatch, arquivos):
    """Banco com as oito tabelas de refined e uma pasta sql/marts em tmp_path."""
    banco = tmp_path / "t.duckdb"
    pasta = tmp_path / "sql" / "marts"
    pasta.mkdir(parents=True)
    for nome, sql in arquivos.items():
        (pasta / nome).write_text(sql, encoding="utf-8")
    monkeypatch.setattr(db, "ARQUIVO_BANCO", banco)
    monkeypatch.setattr(marts, "RAIZ", tmp_path)
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta)
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA refined")
        for tabela in MAPA:
            # Basta existir: os .sql destes testes não leem refined.
            con.execute(f'CREATE TABLE refined."{tabela}" AS SELECT 1 AS x')
    return banco, pasta


def capturar(monkeypatch):
    # Um TextIOWrapper de verdade: main() chama sys.stdout.reconfigure.
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", saida)
    return saida


def lido(saida):
    saida.flush()
    return saida.buffer.getvalue().decode("utf-8")


def tabelas_marts(banco):
    with duckdb.connect(str(banco)) as con:
        return {
            t
            for (t,) in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts'"
            ).fetchall()
        }


# ---------------------------------------------------------------- main


def test_arquivo_00_teste_cria_marts_teste_com_uma_linha(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {"00_teste.sql": "SELECT 1 AS x"})
    capturar(monkeypatch)

    marts.main()

    with duckdb.connect(str(banco)) as con:
        linhas = con.execute("SELECT * FROM marts.teste").fetchall()
    assert linhas == [(1,)]


def test_arquivo_apagado_faz_o_mart_sumir_na_execucao_seguinte(tmp_path, monkeypatch):
    banco, pasta = preparar(
        tmp_path,
        monkeypatch,
        {"00_teste.sql": "SELECT 1 AS x", "01_fica.sql": "SELECT 2 AS y"},
    )
    capturar(monkeypatch)
    marts.main()
    assert tabelas_marts(banco) == {"teste", "fica"}

    (pasta / "00_teste.sql").unlink()
    marts.main()

    assert tabelas_marts(banco) == {"fica"}


def test_arquivo_sem_prefixo_para_antes_de_executar_qualquer_sql(tmp_path, monkeypatch):
    banco, pasta = preparar(tmp_path, monkeypatch, {"01_antigo.sql": "SELECT 1 AS x"})
    capturar(monkeypatch)
    marts.main()  # execução que deu certo: marts.antigo existe

    (pasta / "01_antigo.sql").unlink()
    (pasta / "02_novo.sql").write_text("SELECT 2 AS x", encoding="utf-8")
    (pasta / "teste.sql").write_text("SELECT 3 AS x", encoding="utf-8")  # sem NN_
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit) as fim:
        marts.main()

    assert fim.value.code == 1
    assert "teste.sql: sem prefixo NN_" in lido(saida)
    # Nem o DROP SCHEMA rodou: antigo continua, novo não foi criado.
    assert tabelas_marts(banco) == {"antigo"}


def test_dois_arquivos_com_o_mesmo_nome_de_tabela_param(tmp_path, monkeypatch):
    banco, _ = preparar(
        tmp_path,
        monkeypatch,
        # Vendas e vendas são a mesma tabela para o DuckDB.
        {"01_vendas.sql": "SELECT 1 AS x", "02_Vendas.sql": "SELECT 2 AS x"},
    )
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit):
        marts.main()

    assert "01_vendas.sql, 02_Vendas.sql: mesmo nome de tabela" in lido(saida)
    assert tabelas_marts(banco) == set()


def test_mart_vazio_encerra_e_deixa_o_schema_marts_como_estava(tmp_path, monkeypatch):
    banco, pasta = preparar(tmp_path, monkeypatch, {"01_um.sql": "SELECT 1 AS x"})
    capturar(monkeypatch)
    marts.main()

    (pasta / "01_um.sql").write_text("SELECT 10 AS x UNION ALL SELECT 20", encoding="utf-8")
    # JOIN que não casou, na forma mais curta: nenhuma linha.
    (pasta / "02_vazio.sql").write_text("SELECT 1 AS x WHERE false", encoding="utf-8")
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit) as fim:
        marts.main()

    assert fim.value.code == 1
    assert "Mart vazio: marts.vazio (sql/marts/02_vazio.sql)" in lido(saida)
    assert tabelas_marts(banco) == {"um"}
    with duckdb.connect(str(banco)) as con:
        # O 01 desta execução foi desfeito: continua a linha da execução anterior.
        assert con.execute("SELECT * FROM marts.um").fetchall() == [(1,)]


def test_sql_com_erro_para_mostra_o_arquivo_e_mantem_marts(tmp_path, monkeypatch):
    banco, pasta = preparar(tmp_path, monkeypatch, {"01_um.sql": "SELECT 1 AS x"})
    capturar(monkeypatch)
    marts.main()

    (pasta / "02_quebrado.sql").write_text("SELEC 1", encoding="utf-8")  # erro de sintaxe
    (pasta / "03_depois.sql").write_text("SELECT 3 AS x", encoding="utf-8")
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit):
        marts.main()

    assert "Falhou: sql/marts/02_quebrado.sql" in lido(saida)
    assert tabelas_marts(banco) == {"um"}  # 03 não rodou e nada ficou pela metade


def test_pasta_sem_arquivo_sql_encerra(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch, {})
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit) as fim:
        marts.main()

    assert fim.value.code == 1
    assert "Nenhum arquivo .sql em sql/marts/." in lido(saida)


def test_tabela_faltando_em_refined_encerra(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {"01_um.sql": "SELECT 1 AS x"})
    with duckdb.connect(str(banco)) as con:
        con.execute("DROP TABLE refined.avaliacoes")
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit) as fim:
        marts.main()

    assert fim.value.code == 1
    texto = lido(saida)
    assert "refined.avaliacoes" in texto
    assert "uv run python -m pipeline.transformacao" in texto
    assert tabelas_marts(banco) == set()


def test_rodar_duas_vezes_imprime_exatamente_a_mesma_coisa(tmp_path, monkeypatch):
    preparar(
        tmp_path,
        monkeypatch,
        # 1.200 linhas: confere também o milhar com ponto.
        {"01_um.sql": "SELECT 1 AS x", "02_muitas.sql": "SELECT * FROM range(1200)"},
    )
    primeira = capturar(monkeypatch)
    marts.main()
    segunda = capturar(monkeypatch)
    marts.main()

    assert lido(primeira) == lido(segunda)
    # Nome alinhado à esquerda e contagem à direita, cada um na largura do maior.
    assert lido(primeira).splitlines() == [
        "✓ marts.um          1 linhas",
        "✓ marts.muitas  1.200 linhas",
        "2 marts, 1.201 linhas",
    ]


def test_ler_sql_tira_espacos_e_um_ponto_e_virgula_do_final(tmp_path):
    arquivo = tmp_path / "01_x.sql"
    arquivo.write_text("SELECT 1 AS x ;  \n\n", encoding="utf-8")
    assert marts.ler_sql(arquivo) == "SELECT 1 AS x"


def test_nome_da_tabela_e_o_arquivo_sem_prefixo_e_sem_extensao(tmp_path):
    plano, problemas = marts.planejar([tmp_path / "01_vendas_mensais.sql"])
    assert plano == [(tmp_path / "01_vendas_mensais.sql", "vendas_mensais")]
    assert problemas == []


def test_prefixo_precisa_de_exatamente_dois_digitos(tmp_path):
    # 1_ e 001_ não são NN_.
    _, problemas = marts.planejar([tmp_path / "1_a.sql", tmp_path / "001_b.sql"])
    assert problemas == ["  1_a.sql: sem prefixo NN_", "  001_b.sql: sem prefixo NN_"]


# ---------------------------------------------------------------- sql/marts/01 e 03

PEDIDOS = (
    "CREATE TABLE refined.pedidos (pedido_id VARCHAR, cliente_id VARCHAR, status VARCHAR, "
    "data_compra TIMESTAMP, data_aprovacao TIMESTAMP, data_envio TIMESTAMP, "
    "data_entrega TIMESTAMP, data_entrega_prevista DATE)"
)
ITENS = (
    "CREATE TABLE refined.itens_pedido (pedido_id VARCHAR, item_seq INTEGER, "
    "produto_id VARCHAR, vendedor_id VARCHAR, data_limite_envio TIMESTAMP, "
    "preco DECIMAL(10,2), frete DECIMAL(10,2))"
)


def rodar_mart(tmp_path, arquivo, tabela, pedidos, itens=()):
    """Roda um .sql real do projeto sobre refined inventado; devolve as linhas."""
    with duckdb.connect(str(tmp_path / "t.duckdb")) as con:
        con.execute("CREATE SCHEMA refined")
        con.execute("CREATE SCHEMA marts")
        con.execute(PEDIDOS)
        con.execute(ITENS)
        con.executemany("INSERT INTO refined.pedidos VALUES (?, ?, ?, ?, ?, ?, ?, ?)", pedidos)
        if itens:
            con.executemany("INSERT INTO refined.itens_pedido VALUES (?, ?, ?, ?, ?, ?, ?)", itens)
        marts.construir(con, marts.PASTA_MARTS / arquivo, tabela)
        return con.execute(f"SELECT * FROM marts.{tabela} ORDER BY ALL").fetchall()


def pedido(pedido_id, status, compra, entrega=None, prevista="2018-01-30"):
    return (pedido_id, "c1", status, compra, None, None, entrega, prevista)


def item(pedido_id, seq, preco):
    return (pedido_id, seq, "prod1", "v1", "2018-01-12 00:00:00", Decimal(preco), Decimal("1.00"))


def vendas_mensais(tmp_path, pedidos, itens):
    return rodar_mart(tmp_path, "01_vendas_mensais.sql", "vendas_mensais", pedidos, itens)


def test_pedido_com_dois_itens_conta_uma_vez(tmp_path):
    linhas = vendas_mensais(
        tmp_path,
        [pedido("a", "delivered", "2018-01-10 10:00:00")],
        # Dois itens do mesmo pedido: um pedido, receita 10,00 + 5,50.
        [item("a", 1, "10.00"), item("a", 2, "5.50")],
    )
    assert linhas == [(date(2018, 1, 1), 1, Decimal("15.50"))]


def test_cancelado_fica_fora_da_receita(tmp_path):
    linhas = vendas_mensais(
        tmp_path,
        [
            pedido("a", "delivered", "2018-01-10 10:00:00"),  # entra: 10,00
            pedido("b", "canceled", "2018-01-11 10:00:00"),  # fora: 100,00
            pedido("c", "unavailable", "2018-01-12 10:00:00"),  # fora: 50,00
        ],
        [item("a", 1, "10.00"), item("b", 1, "100.00"), item("c", 1, "50.00")],
    )
    assert linhas == [(date(2018, 1, 1), 1, Decimal("10.00"))]


def test_vendas_mensais_agrupa_pelo_mes_da_compra(tmp_path):
    linhas = vendas_mensais(
        tmp_path,
        [
            pedido("a", "delivered", "2018-01-31 23:59:59"),  # último segundo de janeiro
            pedido("b", "shipped", "2018-02-01 00:00:00"),  # primeiro de fevereiro
            pedido("c", "delivered", "2018-02-15 12:00:00"),
        ],
        [item("a", 1, "1.00"), item("b", 1, "2.00"), item("c", 1, "3.00")],
    )
    assert linhas == [
        (date(2018, 1, 1), 1, Decimal("1.00")),
        (date(2018, 2, 1), 2, Decimal("5.00")),
    ]


def entrega_no_prazo(tmp_path, pedidos):
    return rodar_mart(tmp_path, "03_entrega_no_prazo.sql", "entrega_no_prazo", pedidos)


def test_entrega_no_dia_previsto_a_tarde_esta_no_prazo(tmp_path):
    linhas = entrega_no_prazo(
        tmp_path,
        # Previsto para 20/01, entregue às 15h do dia 20.
        [pedido("a", "delivered", "2018-01-10 10:00:00", "2018-01-20 15:00:00", "2018-01-20")],
    )
    assert linhas == [(1, 1, 0, 100.0)]


def test_entrega_no_dia_seguinte_ao_previsto_esta_atrasada(tmp_path):
    linhas = entrega_no_prazo(
        tmp_path,
        # Previsto para 20/01, entregue logo depois da meia-noite do dia 21.
        [pedido("a", "delivered", "2018-01-10 10:00:00", "2018-01-21 00:01:00", "2018-01-20")],
    )
    assert linhas == [(1, 0, 1, 0.0)]


def test_denominador_e_so_delivered_com_data_de_entrega(tmp_path):
    linhas = entrega_no_prazo(
        tmp_path,
        [
            # Três entregues: dois no prazo, um atrasado -> 66,7%.
            pedido("a", "delivered", "2018-01-10 10:00:00", "2018-01-15 09:00:00", "2018-01-20"),
            pedido("b", "delivered", "2018-01-10 10:00:00", "2018-01-20 23:00:00", "2018-01-20"),
            pedido("c", "delivered", "2018-01-10 10:00:00", "2018-01-25 09:00:00", "2018-01-20"),
            # delivered sem data de entrega: fora do denominador.
            pedido("d", "delivered", "2018-01-10 10:00:00", None, "2018-01-20"),
            # Cancelado e em trânsito: fora.
            pedido("e", "canceled", "2018-01-10 10:00:00", None, "2018-01-20"),
            pedido("f", "shipped", "2018-01-10 10:00:00", None, "2018-01-20"),
        ],
    )
    assert linhas == [(3, 2, 1, 66.7)]
