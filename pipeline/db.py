"""Acesso ao banco DuckDB do projeto.

Contrato usado pelas etapas do pipeline:
  PASTA_RAW                          Path da pasta com os nove .csv.gz
  conectar()                         abre o olist.duckdb, criando se faltar
  criar_schema(con, nome)            CREATE SCHEMA IF NOT EXISTS
  gravar(con, df, schema, tabela)    grava e devolve a contagem lida do banco
"""

from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PASTA_RAW = RAIZ / "raw"
ARQUIVO_BANCO = RAIZ / "olist.duckdb"


def conectar() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(ARQUIVO_BANCO))


def criar_schema(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{nome}"')


def gravar(
    con: duckdb.DuckDBPyConnection, df: pd.DataFrame, schema: str, tabela: str
) -> int:
    # CREATE OR REPLACE: reexecutar recria a tabela, nunca acrescenta linhas.
    con.register("_df_gravar", df)
    try:
        con.execute(
            f'CREATE OR REPLACE TABLE "{schema}"."{tabela}" AS SELECT * FROM _df_gravar'
        )
    finally:
        con.unregister("_df_gravar")
    return con.execute(f'SELECT count(*) FROM "{schema}"."{tabela}"').fetchone()[0]
