"""pipeline/ingestao.py: .csv.gz pequenos escritos em tmp_path entram em raw."""

import gzip
import io
import sys

import duckdb
import pytest

from pipeline import db, ingestao


def escrever_csv_gz(caminho, texto):
    with gzip.open(caminho, "wt", encoding="utf-8", newline="") as f:
        f.write(texto)


def preparar(tmp_path, monkeypatch, conteudos=None):
    """Nove arquivos em tmp_path/raw e o banco em tmp_path; devolve o caminho do banco."""
    pasta = tmp_path / "raw"
    pasta.mkdir()
    conteudos = conteudos or {}
    for arquivo in ingestao.ARQUIVOS:
        # Por padrão, cada arquivo tem duas linhas: o mínimo para contar.
        escrever_csv_gz(pasta / arquivo, conteudos.get(arquivo, "id,nome\n1,um\n2,dois\n"))
    banco = tmp_path / "t.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta)
    monkeypatch.setattr(db, "ARQUIVO_BANCO", banco)
    return banco


def capturar(monkeypatch):
    # Um TextIOWrapper de verdade: main() chama sys.stdout.reconfigure.
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", saida)
    return saida


def lido(saida):
    saida.flush()
    return saida.buffer.getvalue().decode("utf-8")


def test_csv_vira_tabela_com_as_mesmas_linhas(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            # Três pedidos: a tabela tem que sair com três linhas.
            "olist_orders_dataset.csv.gz": "order_id,order_status\np1,delivered\np2,canceled\np3,shipped\n",
        },
    )
    capturar(monkeypatch)

    ingestao.main()

    with duckdb.connect(str(banco)) as con:
        linhas = con.execute("SELECT * FROM raw.pedidos ORDER BY order_id").fetchall()
    assert linhas == [("p1", "delivered"), ("p2", "canceled"), ("p3", "shipped")]


def test_cada_arquivo_vai_para_a_tabela_do_mapa(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    ingestao.main()

    with duckdb.connect(str(banco)) as con:
        tabelas = {
            t
            for (t,) in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
            ).fetchall()
        }
    assert tabelas == set(ingestao.ARQUIVOS.values())


def test_arquivo_faltando_encerra_sem_criar_o_banco(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)
    (tmp_path / "raw" / "olist_sellers_dataset.csv.gz").unlink()  # um dos nove some
    saida = capturar(monkeypatch)

    with pytest.raises(SystemExit) as fim:
        ingestao.main()

    assert fim.value.code == 1
    assert not banco.exists()  # confere antes de abrir o banco: nada foi gravado
    assert "olist_sellers_dataset.csv.gz" in lido(saida)


def test_toda_coluna_entra_como_texto_e_o_cep_mantem_o_zero(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            # CEP com zero à esquerda e um número: a inferência leria 1310 e 7.
            "olist_customers_dataset.csv.gz": "customer_zip_code_prefix,qtd\n01310,7\n",
        },
    )
    capturar(monkeypatch)

    ingestao.main()

    with duckdb.connect(str(banco)) as con:
        tipos = con.execute(
            "SELECT DISTINCT data_type FROM information_schema.columns "
            "WHERE table_schema = 'raw' AND table_name = 'clientes'"
        ).fetchall()
        linha = con.execute("SELECT * FROM raw.clientes").fetchone()
    assert tipos == [("VARCHAR",)]
    assert linha == ("01310", "7")


def test_campo_vazio_vira_nulo_e_o_texto_na_continua_texto(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            # Linha 1: campo vazio (nulo). Linha 2: o texto "NA", que não é nulo.
            "olist_products_dataset.csv.gz": "product_id,product_category_name\nx1,\nx2,NA\n",
        },
    )
    capturar(monkeypatch)

    ingestao.main()

    with duckdb.connect(str(banco)) as con:
        linhas = con.execute("SELECT * FROM raw.produtos ORDER BY product_id").fetchall()
    assert linhas == [("x1", None), ("x2", "NA")]


def test_linha_duplicada_nao_e_removida_na_ingestao(tmp_path, monkeypatch):
    banco = preparar(
        tmp_path,
        monkeypatch,
        {
            # A mesma linha duas vezes: deduplicar é decisão da etapa 2.
            "olist_order_items_dataset.csv.gz": "order_id,price\np1,10.00\np1,10.00\n",
        },
    )
    capturar(monkeypatch)

    ingestao.main()

    with duckdb.connect(str(banco)) as con:
        n = con.execute("SELECT count(*) FROM raw.itens_pedido").fetchone()[0]
    assert n == 2


def test_rodar_duas_vezes_da_o_mesmo_resultado_que_rodar_uma(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)
    capturar(monkeypatch)

    ingestao.main()
    ingestao.main()

    with duckdb.connect(str(banco)) as con:
        n = con.execute("SELECT count(*) FROM raw.pedidos").fetchone()[0]
    assert n == 2  # recriada, não acrescentada


def test_saida_mostra_a_contagem_por_tabela_e_o_total(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)  # nove arquivos de duas linhas: total 18
    saida = capturar(monkeypatch)

    ingestao.main()

    linhas = lido(saida).splitlines()
    assert len(linhas) == 10  # nove tabelas e o total
    assert linhas[0].split() == ["raw.pedidos", "2"]
    assert linhas[-1].split() == ["total", "18"]


def test_milhar_usa_ponto():
    assert ingestao.milhar(1234567) == "1.234.567"
    assert ingestao.milhar(999) == "999"
