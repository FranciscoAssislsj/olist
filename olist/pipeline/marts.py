"""Marts: cada sql/marts/NN_nome.sql vira a tabela marts.nome.

Execução:
    uv run python -m olist.pipeline.marts

SPEC (e por que cada regra existe)

1. ESCOPO
   Lê de refined, escreve no schema marts. Nunca escreve em raw nem em
   refined. O schema marts é apagado e recriado a cada execução
   (DROP SCHEMA IF EXISTS marts CASCADE).
   Por quê: um mart cujo arquivo foi apagado não pode continuar existindo
   no banco.

2. UM ARQUIVO, UMA TABELA
   Lê todos os sql/marts/*.sql em ordem alfabética. Nome da tabela = nome
   do arquivo sem a extensão e sem o prefixo numérico:
     sql/marts/01_vendas_mensais.sql -> marts.vendas_mensais
   Executa: CREATE TABLE marts.<nome> AS <conteúdo do arquivo>
   Tira espaços e um ponto e vírgula do final do conteúdo, e nada mais.
   O Python não altera, não monta e não completa a SQL.
   Por quê: a regra de negócio mora inteira no arquivo .sql.

3. SAÍDA NA TELA
   Uma linha por mart, com a contagem vinda do banco, milhar com ponto:
     ✓ marts.vendas_mensais        24 linhas
   Linha final com o número de marts e o total de linhas. stdout
   reconfigurado para utf-8.
   Por quê: contar no banco prova que a tabela foi gravada; o Prompt de
   Comando do Windows embaralha acento (e o ✓) por padrão.

4. ERRO
   - Antes de tudo: se faltar qualquer uma das oito tabelas em refined,
     lista quais, diz para rodar "uv run python -m olist.pipeline.transformacao"
     e encerra com sys.exit(1).
     Por quê: mart sobre refined incompleto sai errado parecendo certo.
   - Se sql/marts/ não tiver nenhum arquivo: avisa e sys.exit(1).
     Por quê: rodar sem arquivo apagaria todos os marts em silêncio.
   - Antes de executar qualquer SQL: arquivo sem prefixo NN_ ou dois
     arquivos que dão o mesmo nome de tabela -> lista quais e sys.exit(1).
     Por quê: o nome da tabela sai do nome do arquivo; se ele não pode ser
     derivado, ou é derivado duas vezes, uma tabela some ou é sobrescrita.
   - Se um .sql falhar: mostra o nome do arquivo e a mensagem do DuckDB,
     não executa os seguintes, sys.exit(1).
     Por quê: o erro tem que apontar o arquivo a corrigir.
   - Se um mart voltar com zero linhas: mostra o nome e sys.exit(1).
     Por quê: mart vazio é quase sempre um JOIN que não casou, e um
     dashboard vazio parece um negócio parado.
   - Tudo roda numa transação só: se qualquer passo falhar (inclusive o
     mart vazio), o schema marts volta a ser o da última execução que deu
     certo.
     Por quê: um schema pela metade quebra o dashboard sem avisar.

CRITÉRIOS DE ACEITE
   - sql/marts/00_teste.sql com "SELECT 1 AS x" cria marts.teste com 1 linha.
   - Apagar o arquivo e rodar de novo faz marts.teste desaparecer.
   - Arquivo com erro de sintaxe para tudo, com o nome do arquivo na tela,
     e marts continua exatamente como estava antes da execução.
   - Arquivo teste.sql, sem prefixo, para antes de executar qualquer SQL.
   - Rodar duas vezes seguidas imprime exatamente a mesma coisa.
"""

import re
import sys
from pathlib import Path

import duckdb

from olist.config import PASTA_MARTS, RAIZ
from olist.pipeline.db import conectar, criar_schema
from olist.pipeline.transformacao import MAPA, milhar

ORIGEM = "refined"
DESTINO = "marts"

# Exatamente dois dígitos e um sublinhado, seguidos de pelo menos um caractere.
PREFIXO = re.compile(r"^\d{2}_(.+)$")


class Parada(Exception):
    """Falha de execução: a mensagem vai para a tela e o processo sai com 1."""


def tabelas_faltando(con: duckdb.DuckDBPyConnection) -> list[str]:
    existentes = {
        nome
        for (nome,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            [ORIGEM],
        ).fetchall()
    }
    return [t for t in MAPA if t not in existentes]


def planejar(arquivos: list[Path]) -> tuple[list[tuple[Path, str]], list[str]]:
    """Devolve [(arquivo, tabela)] e a lista de problemas de nome."""
    plano, problemas = [], []
    por_nome: dict[str, list[Path]] = {}
    for arquivo in arquivos:
        achado = PREFIXO.match(arquivo.stem)
        if not achado:
            problemas.append(f"  {arquivo.name}: sem prefixo NN_")
            continue
        tabela = achado.group(1)
        plano.append((arquivo, tabela))
        # DuckDB compara identificadores sem diferenciar maiúscula, mesmo entre
        # aspas: Vendas e vendas seriam a mesma tabela.
        por_nome.setdefault(tabela.lower(), []).append(arquivo)
    for repetidos in por_nome.values():
        if len(repetidos) > 1:
            nomes = ", ".join(a.name for a in repetidos)
            problemas.append(f"  {nomes}: mesmo nome de tabela")
    return plano, problemas


def ler_sql(arquivo: Path) -> str:
    sql = arquivo.read_text(encoding="utf-8").rstrip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    return sql


def construir(con: duckdb.DuckDBPyConnection, arquivo: Path, tabela: str) -> int:
    alvo = f'"{DESTINO}"."{tabela}"'
    # Na mesma linha do AS, sem quebra: assim o "LINE n" do erro do DuckDB é a
    # linha n do arquivo. Um "--" no topo do arquivo termina na quebra de linha
    # do próprio arquivo, então não engole o resto.
    try:
        con.execute(f"CREATE TABLE {alvo} AS {ler_sql(arquivo)}")
    except duckdb.Error as erro:
        raise Parada(f"Falhou: {arquivo.relative_to(RAIZ).as_posix()}\n  DuckDB: {erro}") from None
    linhas = con.execute(f"SELECT count(*) FROM {alvo}").fetchone()[0]
    if linhas == 0:
        raise Parada(
            f"Mart vazio: {DESTINO}.{tabela} ({arquivo.relative_to(RAIZ).as_posix()}) "
            f"voltou com zero linhas."
        )
    return linhas


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        faltando = tabelas_faltando(con)
        if faltando:
            print(f"Tabelas não encontradas no schema {ORIGEM}:")
            for tabela in faltando:
                print(f"  {ORIGEM}.{tabela}")
            print("Rode antes: uv run python -m olist.pipeline.transformacao")
            print("Nada foi gravado.")
            sys.exit(1)

        arquivos = sorted(PASTA_MARTS.glob("*.sql"), key=lambda a: a.name)
        if not arquivos:
            print(f"Nenhum arquivo .sql em {PASTA_MARTS.relative_to(RAIZ).as_posix()}/.")
            print("Nada foi gravado.")
            sys.exit(1)

        plano, problemas = planejar(arquivos)
        if problemas:
            print("Nomes de arquivo inválidos em sql/marts/:")
            for problema in problemas:
                print(problema)
            print("Nenhuma SQL foi executada.")
            sys.exit(1)

        # DDL no DuckDB é transacional: o rollback desfaz também o DROP SCHEMA,
        # e marts volta inteiro ao estado da última execução que deu certo.
        con.begin()
        try:
            con.execute(f'DROP SCHEMA IF EXISTS "{DESTINO}" CASCADE')
            criar_schema(con, DESTINO)
            resultado = [(tabela, construir(con, arquivo, tabela)) for arquivo, tabela in plano]
            con.commit()
        except Parada as parada:
            con.rollback()
            print(parada)
            print(f"Nada foi gravado; {DESTINO} continua como na última execução.")
            sys.exit(1)
    finally:
        con.close()

    # Imprime só depois do commit: um ✓ antes de uma falha seria desfeito pelo
    # rollback e mentiria sobre o que está no banco.
    nomes = [f"{DESTINO}.{tabela}" for tabela, _ in resultado]
    contagens = [milhar(n) for _, n in resultado]
    largura_nome = max(len(n) for n in nomes)
    largura_num = max(len(c) for c in contagens)
    for nome, contagem in zip(nomes, contagens):
        print(f"✓ {nome:<{largura_nome}}  {contagem:>{largura_num}} linhas")
    total = sum(n for _, n in resultado)
    print(f"{len(resultado)} marts, {milhar(total)} linhas")


if __name__ == "__main__":
    main()
