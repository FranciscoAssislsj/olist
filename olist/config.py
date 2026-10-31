"""Caminhos do projeto, num lugar só.

  RAIZ           raiz do repositório
  PASTA_RAW      data/raw, os nove .csv.gz da Olist (versionados)
  ARQUIVO_BANCO  data/olist.duckdb, gerado pelo pipeline (fora do git)
  PASTA_MARTS    sql/marts, um .sql por mart
  PASTA_REPORTS  reports, saída do relatório HTML
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DATA = RAIZ / "data"
PASTA_RAW = PASTA_DATA / "raw"
ARQUIVO_BANCO = PASTA_DATA / "olist.duckdb"
PASTA_MARTS = RAIZ / "sql" / "marts"
PASTA_REPORTS = RAIZ / "reports"
