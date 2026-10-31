"""Explorador do data/olist.duckdb no navegador, pela extensão ui do DuckDB.

Execução:
    uv run python -m olist.ui

SPEC (e por que cada regra existe)

U1. O QUE FAZ
    Abre o data/olist.duckdb (olist.config), roda INSTALL ui; LOAD ui; e
    CALL start_ui(), que sobe o servidor em http://localhost:4213 e abre o
    navegador.
    Por quê: explorar tabela no navegador é mais rápido que ler no terminal.

U2. FICA DE PÉ ATÉ CTRL+C
    A extensão só serve enquanto a conexão estiver viva, então o processo
    fica rodando, mostra a URL e "Ctrl+C para encerrar", e no Ctrl+C fecha a
    conexão e sai limpo, sem traceback.
    Por quê: o .duckdb aceita um único processo escrevendo. Com este script
    de pé, a ingestão falha com "Could not set lock on file". Saber
    exatamente como desligar o servidor faz parte da ferramenta.

U3. NÃO CRIA BANCO
    Se data/olist.duckdb não existir, avisa que é preciso rodar a ingestão antes e
    encerra com sys.exit(1). Por isso não usa olist.pipeline.db.conectar(), que
    cria o arquivo quando ele falta.
    Por quê: um banco vazio aberto no navegador parece ingestão quebrada.

U4. SEPARAÇÃO
    Não importa olist.pipeline.ingestao, e a ingestão não importa este arquivo.
    Por quê: a ingestão não pode depender de servidor, navegador ou da
    extensão ui para rodar.

U5. SAÍDA NA TELA
    stdout reconfigurado para utf-8.
    Por quê: o Prompt de Comando do Windows embaralha acento por padrão.
"""

import sys
import time

import duckdb

from olist.config import ARQUIVO_BANCO

URL = "http://localhost:4213"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    # Checar antes de conectar: duckdb.connect criaria um banco vazio.
    if not ARQUIVO_BANCO.is_file():
        print(f"Banco não encontrado: {ARQUIVO_BANCO}")
        print("Rode a ingestão antes: uv run python -m olist.pipeline.ingestao")
        sys.exit(1)

    con = duckdb.connect(str(ARQUIVO_BANCO))
    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        con.execute("CALL start_ui()")
        print(f"DuckDB UI em {URL}")
        print("Ctrl+C para encerrar")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        con.close()
    print("Servidor encerrado, banco liberado.")


if __name__ == "__main__":
    main()
