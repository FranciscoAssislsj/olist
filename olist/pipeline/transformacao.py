"""Transformação: as oito tabelas usadas pelos marts saem de raw para refined.

Execução:
    uv run python -m olist.pipeline.transformacao

SPEC (e por que cada regra existe)

1. ESCOPO
   Lê de raw, escreve em refined, nunca escreve em raw. Entram oito tabelas:
   pedidos, itens_pedido, pagamentos, clientes, vendedores, produtos,
   traducao_categorias e avaliacoes. geolocalizacao fica de fora.
   Por quê: raw é o dado como chegou e precisa continuar assim para servir
   de comparação. geolocalizacao não é lida por nenhum mart do curso, e não
   se limpa o que ninguém vai ler.

2. NOMES
   Colunas renomeadas para português em snake_case pelo mapa MAPA, completo e
   literal: nenhuma coluna fora dele, nenhuma descartada.
   Por quê: é o vocabulário digitado de memória nos JOINs da aula 3. Um mapa
   fechado garante que nenhuma coluna some nem aparece sem decisão.

3. TIPOS
   - Datas com hora (data_compra, data_aprovacao, data_envio, data_entrega,
     data_limite_envio, data_resposta): TIMESTAMP, formato declarado
     '%Y-%m-%d %H:%M:%S'. Declarar o formato impede que o parser adivinhe.
   - data_entrega_prevista: DATE. A hora é 00:00:00 nas 99.441 linhas;
     guardar a hora seria inventar precisão.
   - data_criacao: DATE. A hora é 00:00:00 em 99.139 das 99.224 avaliações;
     nas outras 85 é 01:00:00, efeito de horário de verão e não um horário
     de verdade.
   - Dinheiro (preco, frete, valor): DECIMAL(10,2). DOUBLE não representa
     centavos com exatidão, e soma de dinheiro tem que fechar.
   - Contagens e medidas (item_seq, pagamento_seq, parcelas, tamanho_nome,
     tamanho_descricao, qtd_fotos, peso_g, comprimento_cm, altura_cm,
     largura_cm, nota): INTEGER.
   - Todo o resto continua VARCHAR, inclusive cep_prefixo: 23.995 clientes
     têm CEP começando com zero; CEP é identificador, nunca é somado, e como
     número perderia o zero.
   A conversão roda em SQL no DuckDB (strptime, CAST), disparada pelo
   Python. Por quê: o dado já está no banco; trazê-lo para a memória só para
   converter tipo é custo sem ganho.

4. CONVERSÃO QUE FALHA
   Para tudo. Só strptime e CAST, que estouram; nunca try_strptime, TRY_CAST
   ou errors="coerce", que transformam falha em nulo. Ao falhar, diz
   tabela, coluna e um exemplo do valor, e encerra com sys.exit(1).
   Por quê: um nulo fabricado pela conversão fica indistinguível, para
   sempre, de um nulo verdadeiro do dado.

5. DUPLICATAS
   Chave de cada tabela em CHAVES. Em avaliacoes a chave é
   (avaliacao_id, pedido_id): o mesmo avaliacao_id aparece em mais de um
   pedido. Linha inteira repetida: mantém uma e conta quantas saíram. Chave
   repetida com conteúdo diferente: para, mostra a chave e as linhas
   conflitantes, sys.exit(1).
   Por quê: linha idêntica repetida não carrega informação nova, então
   removê-la não decide nada. Escolher uma entre linhas diferentes é decidir
   em silêncio, sem dizer que decidiu.

6. NULOS
   Nenhuma linha apagada por ter nulo; nenhum nulo preenchido. Anomalias de
   negócio também ficam (pedido delivered sem data_entrega, data_envio antes
   da data_compra, pedido com mais de uma avaliação).
   Por quê: o nulo é informação. Pedido cancelado não tem data de entrega
   porque não foi entregue; produto sem categoria continua sem categoria até
   um mart decidir o rótulo; avaliação sem texto é a regra. refined não
   corrige fato: quem decide o que fazer com ele é a pergunta que o mart
   responde.

7. SAÍDA NA TELA
   Uma linha por tabela (linhas que entram -> linhas que saem, duplicatas
   removidas), abaixo dela as colunas com nulo e a contagem, e uma linha
   final com o total. Contagens lidas do banco, milhar com ponto, stdout em
   utf-8.
   Por quê: é o instrumento de conferência desta etapa. Contar no banco
   prova que o dado chegou lá; mostrar os nulos deixa conferir que nenhum
   foi criado nem apagado. O Prompt de Comando do Windows embaralha acento
   por padrão.

REEXECUÇÃO
   CREATE OR REPLACE TABLE, nunca acrescenta. Rodar dez vezes = rodar uma.
   Por quê: é o que permite errar e rodar de novo sem medo.

ERRO
   Antes de transformar, confere se as oito tabelas existem em raw. Faltando
   qualquer uma: lista quais, manda rodar "uv run python -m olist.pipeline.ingestao"
   e encerra com sys.exit(1).
   Por quê: transformar sete de oito tabelas em silêncio produz um mart
   errado que parece certo.
"""

import re
import sys

import duckdb

from olist.pipeline.db import conectar, criar_schema

ORIGEM = "raw"
DESTINO = "refined"

FORMATO_DATA_HORA = "%Y-%m-%d %H:%M:%S"

# tabela -> [(coluna em raw, coluna em refined)], na ordem de raw.
MAPA = {
    "pedidos": [
        ("order_id", "pedido_id"),
        ("customer_id", "cliente_id"),
        ("order_status", "status"),
        ("order_purchase_timestamp", "data_compra"),
        ("order_approved_at", "data_aprovacao"),
        ("order_delivered_carrier_date", "data_envio"),
        ("order_delivered_customer_date", "data_entrega"),
        ("order_estimated_delivery_date", "data_entrega_prevista"),
    ],
    "itens_pedido": [
        ("order_id", "pedido_id"),
        ("order_item_id", "item_seq"),
        ("product_id", "produto_id"),
        ("seller_id", "vendedor_id"),
        ("shipping_limit_date", "data_limite_envio"),
        ("price", "preco"),
        ("freight_value", "frete"),
    ],
    "pagamentos": [
        ("order_id", "pedido_id"),
        ("payment_sequential", "pagamento_seq"),
        ("payment_type", "tipo"),
        ("payment_installments", "parcelas"),
        ("payment_value", "valor"),
    ],
    "clientes": [
        ("customer_id", "cliente_id"),
        ("customer_unique_id", "cliente_unico_id"),
        ("customer_zip_code_prefix", "cep_prefixo"),
        ("customer_city", "cidade"),
        ("customer_state", "uf"),
    ],
    "vendedores": [
        ("seller_id", "vendedor_id"),
        ("seller_zip_code_prefix", "cep_prefixo"),
        ("seller_city", "cidade"),
        ("seller_state", "uf"),
    ],
    "produtos": [
        ("product_id", "produto_id"),
        ("product_category_name", "categoria"),
        ("product_name_lenght", "tamanho_nome"),
        ("product_description_lenght", "tamanho_descricao"),
        ("product_photos_qty", "qtd_fotos"),
        ("product_weight_g", "peso_g"),
        ("product_length_cm", "comprimento_cm"),
        ("product_height_cm", "altura_cm"),
        ("product_width_cm", "largura_cm"),
    ],
    "traducao_categorias": [
        ("product_category_name", "categoria"),
        ("product_category_name_english", "categoria_en"),
    ],
    "avaliacoes": [
        ("review_id", "avaliacao_id"),
        ("order_id", "pedido_id"),
        ("review_score", "nota"),
        ("review_comment_title", "titulo"),
        ("review_comment_message", "comentario"),
        ("review_creation_date", "data_criacao"),
        ("review_answer_timestamp", "data_resposta"),
    ],
}

CHAVES = {
    "pedidos": ["pedido_id"],
    "itens_pedido": ["pedido_id", "item_seq"],
    "pagamentos": ["pedido_id", "pagamento_seq"],
    "clientes": ["cliente_id"],
    "vendedores": ["vendedor_id"],
    "produtos": ["produto_id"],
    "traducao_categorias": ["categoria"],
    "avaliacoes": ["avaliacao_id", "pedido_id"],
}

DATA_HORA = {
    "data_compra", "data_aprovacao", "data_envio", "data_entrega",
    "data_limite_envio", "data_resposta",
}
DATA = {"data_entrega_prevista", "data_criacao"}
DINHEIRO = {"preco", "frete", "valor"}
INTEIRO = {
    "item_seq", "pagamento_seq", "parcelas", "tamanho_nome",
    "tamanho_descricao", "qtd_fotos", "peso_g", "comprimento_cm",
    "altura_cm", "largura_cm", "nota",
}


class Parada(Exception):
    """Falha de dado: a mensagem vai para a tela e o processo sai com 1."""


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def expressao(origem: str, destino: str) -> str:
    col = f'"{origem}"'
    if destino in DATA_HORA:
        return f"strptime({col}, '{FORMATO_DATA_HORA}')"
    if destino in DATA:
        # O texto em raw traz a hora (00:00:00 ou 01:00:00); lê com o mesmo
        # formato declarado e descarta a hora, que a spec diz não ser real.
        return f"CAST(strptime({col}, '{FORMATO_DATA_HORA}') AS DATE)"
    if destino in DINHEIRO:
        return f"CAST({col} AS DECIMAL(10,2))"
    if destino in INTEIRO:
        return f"CAST({col} AS INTEGER)"
    return col


def tabelas_faltando(con: duckdb.DuckDBPyConnection) -> list[str]:
    existentes = {
        nome
        for (nome,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            [ORIGEM],
        ).fetchall()
    }
    return [t for t in MAPA if t not in existentes]


def localizar_falha(con: duckdb.DuckDBPyConnection, tabela: str) -> str:
    # A conversão da tabela inteira falhou e o erro do DuckDB não diz a coluna.
    # Repete coluna a coluna, ainda com strptime/CAST, até achar a que estoura;
    # o valor de exemplo é o que o próprio DuckDB cita na mensagem. Usa um
    # cursor próprio porque a transação principal está abortada pela falha.
    sonda = con.cursor()
    for origem, destino in MAPA[tabela]:
        try:
            sonda.execute(
                f'SELECT {expressao(origem, destino)} FROM "{ORIGEM}"."{tabela}"'
            ).fetchall()
        except duckdb.Error as erro:
            mensagem = str(erro)
            # Erro de formato cita o valor entre aspas; data impossível (ex.:
            # 30 de fevereiro) só o cita depois do último ':', já reformatado.
            achado = re.search(r"""string ["'](.*?)["']""", mensagem)
            primeira = mensagem.splitlines()[0]
            exemplo = achado.group(1) if achado else primeira.rsplit(": ", 1)[-1]
            return (
                f"Conversão falhou em {ORIGEM}.{tabela}, coluna {origem} -> {destino}\n"
                f"  valor que não converteu: {exemplo!r}\n"
                f"  DuckDB: {mensagem.splitlines()[0]}"
            )
    return f"Conversão falhou em {ORIGEM}.{tabela}, coluna não identificada."


def transformar(con: duckdb.DuckDBPyConnection, tabela: str) -> tuple[int, int]:
    """Grava refined.<tabela> e devolve (linhas que entram, linhas que saem)."""
    colunas = ",\n    ".join(f'{expressao(o, d)} AS "{d}"' for o, d in MAPA[tabela])
    try:
        con.execute(
            f'CREATE OR REPLACE TEMP TABLE _convertida AS\n'
            f'SELECT\n    {colunas}\nFROM "{ORIGEM}"."{tabela}"'
        )
    except duckdb.Error:
        raise Parada(localizar_falha(con, tabela)) from None

    con.execute("CREATE OR REPLACE TEMP TABLE _distinta AS SELECT DISTINCT * FROM _convertida")

    chave = ", ".join(f'"{c}"' for c in CHAVES[tabela])
    conflitos = con.execute(
        f"SELECT {chave}, count(*) FROM _distinta GROUP BY ALL HAVING count(*) > 1 ORDER BY ALL"
    ).fetchall()
    if conflitos:
        linhas = con.execute(
            f"SELECT * FROM _distinta SEMI JOIN "
            f"(SELECT {chave} FROM _distinta GROUP BY ALL HAVING count(*) > 1) "
            f"USING ({chave}) ORDER BY ALL"
        )
        nomes = [d[0] for d in linhas.description]
        texto = [
            (
                f"Chave repetida com conteúdo diferente em {ORIGEM}.{tabela} "
                f"({milhar(len(conflitos))} chaves; chave: {', '.join(CHAVES[tabela])})."
            ),
            "  " + " | ".join(nomes),
        ]
        texto += ["  " + " | ".join(str(v) for v in linha) for linha in linhas.fetchall()]
        raise Parada("\n".join(texto))

    con.execute(f'CREATE OR REPLACE TABLE "{DESTINO}"."{tabela}" AS SELECT * FROM _distinta')
    entrada = con.execute(f'SELECT count(*) FROM "{ORIGEM}"."{tabela}"').fetchone()[0]
    saida = con.execute(f'SELECT count(*) FROM "{DESTINO}"."{tabela}"').fetchone()[0]
    return entrada, saida


def nulos(con: duckdb.DuckDBPyConnection, tabela: str) -> list[tuple[str, int]]:
    colunas = [d for _, d in MAPA[tabela]]
    contagens = con.execute(
        "SELECT " + ", ".join(f'count(*) - count("{c}")' for c in colunas)
        + f' FROM "{DESTINO}"."{tabela}"'
    ).fetchone()
    return [(c, n) for c, n in zip(colunas, contagens) if n > 0]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        faltando = tabelas_faltando(con)
        if faltando:
            print(f"Tabelas não encontradas no schema {ORIGEM}:")
            for tabela in faltando:
                print(f"  {ORIGEM}.{tabela}")
            print('Rode antes: uv run python -m olist.pipeline.ingestao')
            print("Nada foi gravado.")
            sys.exit(1)

        # Uma transação só: se qualquer tabela parar, refined fica como estava,
        # em vez de metade nova e metade da execução anterior.
        con.begin()
        try:
            criar_schema(con, DESTINO)
            resultado = {}
            for tabela in MAPA:
                entrada, saida = transformar(con, tabela)
                resultado[tabela] = (entrada, saida, nulos(con, tabela))
            con.commit()
        except Parada as parada:
            con.rollback()
            print(parada)
            print("Nada foi gravado.")
            sys.exit(1)
    finally:
        con.close()

    nomes = {t: f"{DESTINO}.{t}" for t in resultado}
    largura = max(len(n) for n in nomes.values())
    total_entrada = total_saida = 0
    for tabela, (entrada, saida, com_nulo) in resultado.items():
        total_entrada += entrada
        total_saida += saida
        print(
            f"{nomes[tabela]:<{largura}}  {milhar(entrada):>7} -> {milhar(saida):>7} linhas"
            f"  ({milhar(entrada - saida)} duplicatas)"
        )
        if com_nulo:
            lista = ", ".join(f"{c} {milhar(n)}" for c, n in com_nulo)
            print(f"  nulos mantidos: {lista}")
    print(
        f"{'total':<{largura}}  {milhar(total_entrada):>7} -> {milhar(total_saida):>7} linhas"
        f"  ({milhar(total_entrada - total_saida)} duplicatas)"
    )


if __name__ == "__main__":
    main()
