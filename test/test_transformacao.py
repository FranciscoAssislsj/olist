"""pipeline/transformacao.py: raw inventado em tmp_path vira refined tipado."""

import io
import sys
from datetime import date, datetime
from decimal import Decimal

import duckdb
import pytest

from pipeline import db, transformacao

# Uma linha válida por tabela, em texto como chega em raw, na ordem do MAPA.
# É o pedido p1, entregue, com um item, um pagamento e uma avaliação.
LINHAS_PADRAO = {
    "pedidos": [
        ("p1", "c1", "delivered", "2018-01-10 10:00:00", "2018-01-10 11:00:00",
         "2018-01-11 09:00:00", "2018-01-15 15:00:00", "2018-01-20 00:00:00"),
    ],
    "itens_pedido": [("p1", "1", "prod1", "v1", "2018-01-12 00:00:00", "10.50", "2.25")],
    "pagamentos": [("p1", "1", "credit_card", "1", "12.75")],
    "clientes": [("c1", "u1", "01310", "sao paulo", "SP")],
    "vendedores": [("v1", "04567", "sao paulo", "SP")],
    "produtos": [("prod1", "beleza_saude", "40", "300", "2", "500", "20", "10", "15")],
    "traducao_categorias": [("beleza_saude", "health_beauty")],
    "avaliacoes": [
        ("r1", "p1", "5", None, None, "2018-01-16 00:00:00", "2018-01-17 10:00:00"),
    ],
}


def criar_raw(con, trocas=None, sem=()):
    """raw com as oito tabelas; trocas substitui as linhas de uma tabela."""
    linhas = {**LINHAS_PADRAO, **(trocas or {})}
    con.execute("CREATE SCHEMA raw")
    for tabela, colunas in transformacao.MAPA.items():
        if tabela in sem:
            continue
        definicao = ", ".join(f'"{origem}" VARCHAR' for origem, _ in colunas)
        con.execute(f'CREATE TABLE raw."{tabela}" ({definicao})')
        marcas = ", ".join("?" for _ in colunas)
        con.executemany(f'INSERT INTO raw."{tabela}" VALUES ({marcas})', linhas[tabela])


def preparar(tmp_path, monkeypatch, trocas=None, sem=()):
    banco = tmp_path / "t.duckdb"
    monkeypatch.setattr(db, "ARQUIVO_BANCO", banco)
    with duckdb.connect(str(banco)) as con:
        criar_raw(con, trocas, sem)
    return banco


def capturar(monkeypatch):
    # Um TextIOWrapper de verdade: main() chama sys.stdout.reconfigure.
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", saida)
    return saida


def lido(saida):
    saida.flush()
    return saida.buffer.getvalue().decode("utf-8")


def tipos(con, tabela):
    return dict(
        con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'refined' AND table_name = ?",
            [tabela],
        ).fetchall()
    )


def tabelas_refined(con):
    return {
        t
        for (t,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'refined'"
        ).fetchall()
    }


# ---------------------------------------------------------------- duplicatas


def test_duplicata_exata_sai_e_fica_uma(tmp_path, monkeypatch):
    linha = LINHAS_PADRAO["pagamentos"][0]
    banco = preparar(
        tmp_path,
        monkeypatch,
        # A mesma linha três vezes: entram 3, sai 1.
        {"pagamentos": [linha, linha, linha]},
    )
    capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        n = con.execute("SELECT count(*) FROM refined.pagamentos").fetchone()[0]
    assert n == 1


def test_saida_conta_as_duplicatas_removidas(tmp_path, monkeypatch):
    linha = LINHAS_PADRAO["pagamentos"][0]
    preparar(tmp_path, monkeypatch, {"pagamentos": [linha, linha, linha]})
    saida = capturar(monkeypatch)

    transformacao.main()

    linhas = [linha.split() for linha in lido(saida).splitlines()]
    assert ["refined.pagamentos", "3", "->", "1", "linhas", "(2", "duplicatas)"] in linhas
    # Oito tabelas de uma linha mais as duas repetidas: 10 entram, 8 saem.
    assert linhas[-1] == ["total", "10", "->", "8", "linhas", "(2", "duplicatas)"]


def test_chave_repetida_com_conteudo_diferente_encerra(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            "pagamentos": [
                ("p1", "1", "credit_card", "1", "12.75"),
                # Mesma chave (p1, 1), valor diferente: escolher uma seria decidir.
                ("p1", "1", "credit_card", "1", "99.00"),
            ]
        },
    )
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit) as fim:
        transformacao.main()

    assert fim.value.code == 1
    assert "Chave repetida com conteúdo diferente em raw.pagamentos" in lido(saida)
    with duckdb.connect(str(banco)) as con:
        assert tabelas_refined(con) == set()  # rollback: nenhuma das oito ficou


def test_avaliacao_com_mesmo_id_em_dois_pedidos_nao_e_conflito(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            "avaliacoes": [
                ("r1", "p1", "5", None, None, "2018-01-16 00:00:00", "2018-01-17 10:00:00"),
                # r1 de novo, outro pedido: a chave é (avaliacao_id, pedido_id).
                ("r1", "p2", "4", None, None, "2018-01-16 00:00:00", "2018-01-17 10:00:00"),
            ]
        },
    )
    capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        n = con.execute("SELECT count(*) FROM refined.avaliacoes").fetchone()[0]
    assert n == 2


# ---------------------------------------------------------------- tipos


def test_datas_com_hora_viram_timestamp(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        t = tipos(con, "pedidos")
        data_entrega = con.execute("SELECT data_entrega FROM refined.pedidos").fetchone()[0]
    assert t["data_compra"] == "TIMESTAMP"
    assert t["data_entrega"] == "TIMESTAMP"
    assert data_entrega == datetime(2018, 1, 15, 15, 0, 0)


def test_data_prevista_e_data_criacao_viram_date(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            "avaliacoes": [
                # 01:00:00 é efeito de horário de verão: a hora é descartada.
                ("r1", "p1", "5", None, None, "2018-01-16 01:00:00", "2018-01-17 10:00:00"),
            ]
        },
    )
    capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        prevista = con.execute("SELECT data_entrega_prevista FROM refined.pedidos").fetchone()[0]
        criacao = con.execute("SELECT data_criacao FROM refined.avaliacoes").fetchone()[0]
        assert tipos(con, "pedidos")["data_entrega_prevista"] == "DATE"
        assert tipos(con, "avaliacoes")["data_criacao"] == "DATE"
    assert prevista == date(2018, 1, 20)
    assert criacao == date(2018, 1, 16)


def test_dinheiro_vira_decimal_com_centavos_exatos(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            "itens_pedido": [
                # 0.10 + 0.20 em DOUBLE dá 0.30000000000000004; em DECIMAL, 0.30.
                ("p1", "1", "prod1", "v1", "2018-01-12 00:00:00", "0.10", "1.00"),
                ("p1", "2", "prod1", "v1", "2018-01-12 00:00:00", "0.20", "1.00"),
            ]
        },
    )
    capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        t = tipos(con, "itens_pedido")
        soma = con.execute("SELECT sum(preco) FROM refined.itens_pedido").fetchone()[0]
        valor = con.execute("SELECT valor FROM refined.pagamentos").fetchone()[0]
    assert t["preco"] == "DECIMAL(10,2)"
    assert t["frete"] == "DECIMAL(10,2)"
    assert soma == Decimal("0.30")
    assert valor == Decimal("12.75")


def test_contagens_viram_integer_e_cep_continua_texto_com_zero(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        t_produtos = tipos(con, "produtos")
        t_clientes = tipos(con, "clientes")
        cep = con.execute("SELECT cep_prefixo FROM refined.clientes").fetchone()[0]
        nota = con.execute("SELECT nota FROM refined.avaliacoes").fetchone()[0]
    assert t_produtos["peso_g"] == "INTEGER"
    assert t_produtos["categoria"] == "VARCHAR"
    assert t_clientes["cep_prefixo"] == "VARCHAR"
    assert cep == "01310"
    assert nota == 5


def test_colunas_saem_com_os_nomes_do_mapa(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        for tabela, colunas in transformacao.MAPA.items():
            nomes = [
                n
                for (n,) in con.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'refined' AND table_name = ? ORDER BY ordinal_position",
                    [tabela],
                ).fetchall()
            ]
            assert nomes == [destino for _, destino in colunas]


# ---------------------------------------------------------------- conversão que falha


def test_dinheiro_que_nao_converte_encerra_sem_virar_nulo(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        # Vírgula decimal: CAST estoura; TRY_CAST daria nulo em silêncio.
        {"itens_pedido": [("p1", "1", "prod1", "v1", "2018-01-12 00:00:00", "12,50", "2.25")]},
    )
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit) as fim:
        transformacao.main()

    assert fim.value.code == 1
    texto = lido(saida)
    assert "raw.itens_pedido, coluna price -> preco" in texto
    assert "'12,50'" in texto
    with duckdb.connect(str(banco)) as con:
        assert tabelas_refined(con) == set()  # nem itens_pedido nem as anteriores


def test_data_fora_do_formato_encerra_e_cita_o_valor(tmp_path, monkeypatch):
    preparar(
        tmp_path,
        monkeypatch,
        {
            "pedidos": [
                # data_compra em formato brasileiro: não casa com %Y-%m-%d %H:%M:%S.
                ("p1", "c1", "delivered", "10/01/2018 10:00", "2018-01-10 11:00:00",
                 "2018-01-11 09:00:00", "2018-01-15 15:00:00", "2018-01-20 00:00:00"),
            ]
        },
    )
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit):
        transformacao.main()

    texto = lido(saida)
    assert "coluna order_purchase_timestamp -> data_compra" in texto
    assert "'10/01/2018 10:00'" in texto


def test_data_impossivel_encerra_e_cita_a_data(tmp_path, monkeypatch):
    preparar(
        tmp_path,
        monkeypatch,
        {
            "pedidos": [
                # 30 de fevereiro: o formato casa, a data não existe.
                ("p1", "c1", "delivered", "2018-02-30 10:00:00", "2018-01-10 11:00:00",
                 "2018-01-11 09:00:00", "2018-01-15 15:00:00", "2018-01-20 00:00:00"),
            ]
        },
    )
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit):
        transformacao.main()

    texto = lido(saida)
    assert "coluna order_purchase_timestamp -> data_compra" in texto
    assert "'2018-2-30'" in texto  # o DuckDB cita a data já reformatada


# ---------------------------------------------------------------- nulos


def test_nulo_nao_apaga_a_linha_nem_e_preenchido(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            "pedidos": [
                LINHAS_PADRAO["pedidos"][0],
                # Cancelado: sem aprovação, envio nem entrega.
                ("p2", "c1", "canceled", "2018-01-11 08:00:00", None, None, None,
                 "2018-01-25 00:00:00"),
            ]
        },
    )
    saida = capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        linha = con.execute(
            "SELECT data_aprovacao, data_envio, data_entrega FROM refined.pedidos "
            "WHERE pedido_id = 'p2'"
        ).fetchone()
        com_nulo = transformacao.nulos(con, "pedidos")
    assert linha == (None, None, None)
    assert com_nulo == [("data_aprovacao", 1), ("data_envio", 1), ("data_entrega", 1)]
    assert "nulos mantidos: data_aprovacao 1, data_envio 1, data_entrega 1" in lido(saida)


# ---------------------------------------------------------------- escopo e erro


def test_raw_nao_muda_e_geolocalizacao_fica_fora(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE TABLE raw.geolocalizacao (cep VARCHAR)")
    capturar(monkeypatch)

    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        preco_raw = con.execute('SELECT "price" FROM raw.itens_pedido').fetchone()[0]
        refined = tabelas_refined(con)
    assert preco_raw == "10.50"  # continua texto em raw
    assert refined == set(transformacao.MAPA)
    assert "geolocalizacao" not in refined


def test_tabela_faltando_em_raw_encerra_sem_gravar(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch, sem=("vendedores",))
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit) as fim:
        transformacao.main()

    assert fim.value.code == 1
    texto = lido(saida)
    assert "raw.vendedores" in texto
    assert "uv run python -m pipeline.ingestao" in texto
    with duckdb.connect(str(banco)) as con:
        esquemas = con.execute(
            "SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'refined'"
        ).fetchone()[0]
    assert esquemas == 0


def test_rodar_duas_vezes_da_o_mesmo_resultado_que_rodar_uma(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)
    primeira = capturar(monkeypatch)
    transformacao.main()
    segunda = capturar(monkeypatch)
    transformacao.main()

    with duckdb.connect(str(banco)) as con:
        n = con.execute("SELECT count(*) FROM refined.pedidos").fetchone()[0]
    assert n == 1
    assert lido(primeira) == lido(segunda)


def test_coluna_ausente_em_raw_para_e_aponta_a_coluna(tmp_path):
    # Tabela raw sem as colunas do MAPA: a conversão inteira falha e a sonda,
    # coluna a coluna, para na primeira que não existe.
    with duckdb.connect(str(tmp_path / "t.duckdb")) as con:
        con.execute("CREATE SCHEMA raw")
        con.execute("CREATE TABLE raw.traducao_categorias (outra VARCHAR)")
        with pytest.raises(transformacao.Parada) as parada:
            transformacao.transformar(con, "traducao_categorias")
    assert "coluna product_category_name -> categoria" in str(parada.value)


def test_milhar_usa_ponto():
    assert transformacao.milhar(23995) == "23.995"
