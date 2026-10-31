"""pipeline/db.py: conectar, criar_schema e gravar sobre um DuckDB em tmp_path."""

import pandas as pd

from olist.pipeline import db


def test_conectar_cria_o_banco_quando_ele_falta(tmp_path, monkeypatch):
    arquivo = tmp_path / "novo.duckdb"
    monkeypatch.setattr(db, "ARQUIVO_BANCO", arquivo)
    assert not arquivo.exists()

    con = db.conectar()
    con.close()

    assert arquivo.is_file()


def test_criar_schema_duas_vezes_nao_falha(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "ARQUIVO_BANCO", tmp_path / "t.duckdb")
    with db.conectar() as con:
        db.criar_schema(con, "raw")
        db.criar_schema(con, "raw")  # IF NOT EXISTS: a segunda chamada não estoura
        schemas = con.execute(
            "SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'raw'"
        ).fetchone()[0]
    assert schemas == 1


def test_gravar_devolve_a_contagem_lida_do_banco(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "ARQUIVO_BANCO", tmp_path / "t.duckdb")
    # Três linhas inventadas: o retorno tem que ser 3.
    df = pd.DataFrame({"id": ["a", "b", "c"]})
    with db.conectar() as con:
        db.criar_schema(con, "raw")
        n = db.gravar(con, df, "raw", "coisa")
        no_banco = con.execute('SELECT count(*) FROM "raw"."coisa"').fetchone()[0]
    assert n == 3
    assert no_banco == 3


def test_gravar_de_novo_recria_a_tabela_em_vez_de_acrescentar(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "ARQUIVO_BANCO", tmp_path / "t.duckdb")
    df = pd.DataFrame({"id": ["a", "b"]})
    with db.conectar() as con:
        db.criar_schema(con, "raw")
        db.gravar(con, df, "raw", "coisa")
        n = db.gravar(con, df, "raw", "coisa")  # segunda vez: continua 2, não 4
    assert n == 2


def test_gravar_nao_deixa_o_dataframe_registrado(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "ARQUIVO_BANCO", tmp_path / "t.duckdb")
    with db.conectar() as con:
        db.criar_schema(con, "raw")
        db.gravar(con, pd.DataFrame({"id": ["a"]}), "raw", "coisa")
        visiveis = con.execute(
            "SELECT count(*) FROM duckdb_views() WHERE view_name = '_df_gravar'"
        ).fetchone()[0]
    assert visiveis == 0
