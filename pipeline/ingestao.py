"""Ingestão: os nove .csv.gz da Olist entram no schema raw do olist.duckdb.

Execução:
    uv run python -m pipeline.ingestao

SPEC (e por que cada regra existe)

1. ESCOPO E NOMES
   Destino: schema raw. Mapa arquivo -> tabela fixo e literal (ver ARQUIVOS).
   Os nomes vão para o português porque é o vocabulário digitado de memória
   nos JOINs das próximas etapas.

2. PROIBIÇÕES
   Nenhuma conversão de tipo, nenhuma linha descartada ou deduplicada,
   nenhum nome de coluna alterado, nenhum valor corrigido, preenchido ou
   normalizado. Data continua texto, nulo continua nulo.
   Por quê: a fronteira entre "o dado que chegou" e "o dado que eu decidi"
   precisa existir em algum lugar, e esse lugar é a passagem raw -> refined
   (etapa 2). Corrigir aqui apaga a fronteira.

3. REEXECUÇÃO
   Rodar dez vezes dá o mesmo resultado que rodar uma: cada tabela é
   recriada (CREATE OR REPLACE, feito por db.gravar), nunca acrescentada.
   Por quê: é o que permite errar e rodar de novo sem medo.

4. LEITURA DO ARQUIVO
   encoding utf-8 declarado, nunca adivinhado. .csv.gz lido direto, sem
   descompactar. Campo vazio vira nulo, não string vazia.
   Por quê: adivinhar encoding troca acento sem avisar; nulo e string vazia
   significam coisas diferentes na etapa 2.

5. TIPAGEM
   Toda coluna entra como texto (dtype=str), inferência desligada.
   Por quê: a inferência lê CEP com zero à esquerda como número e o zero
   some sem aviso. Converter é decisão da etapa 2, onde fica registrada.

6. SAÍDA NA TELA
   Uma linha por tabela com nome qualificado e contagem vinda do banco (não
   do DataFrame), milhar com ponto, e uma linha final com o total. stdout
   reconfigurado para utf-8.
   Por quê: essa saída é o único instrumento de conferência desta etapa, e
   a contagem do banco prova que o dado chegou lá. O Prompt de Comando do
   Windows embaralha acento por padrão.

7. ERRO
   Antes de abrir o banco, confere se os nove arquivos existem. Faltando
   qualquer um: lista os que faltam, diz a pasta onde procurou e encerra com
   sys.exit(1), sem ingerir nada.
   Por quê: oito de nove tabelas ingeridas em silêncio produzem um dashboard
   errado que parece certo.

Separação: este módulo não importa ui.py, não sobe servidor, não abre
navegador e não depende da extensão ui do DuckDB.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

SCHEMA = "raw"

ARQUIVOS = {
    "olist_orders_dataset.csv.gz": "pedidos",
    "olist_order_items_dataset.csv.gz": "itens_pedido",
    "olist_order_payments_dataset.csv.gz": "pagamentos",
    "olist_order_reviews_dataset.csv.gz": "avaliacoes",
    "olist_customers_dataset.csv.gz": "clientes",
    "olist_sellers_dataset.csv.gz": "vendedores",
    "olist_products_dataset.csv.gz": "produtos",
    "product_category_name_translation.csv.gz": "traducao_categorias",
    "olist_geolocation_dataset.csv.gz": "geolocalizacao",
}


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def ler_csv(caminho) -> pd.DataFrame:
    return pd.read_csv(
        caminho,
        encoding="utf-8",
        compression="gzip",
        dtype=str,
        # Só campo vazio vira nulo. Os padrões do pandas também transformariam
        # textos como "NA", "null" e "nan" em nulo, o que seria corrigir valor.
        keep_default_na=False,
        na_values=[""],
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    faltando = [nome for nome in ARQUIVOS if not (PASTA_RAW / nome).is_file()]
    if faltando:
        print(f"Arquivos não encontrados em {PASTA_RAW}:")
        for nome in faltando:
            print(f"  {nome}")
        print("Nada foi gravado.")
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, SCHEMA)
        contagens = {}
        for arquivo, tabela in ARQUIVOS.items():
            df = ler_csv(PASTA_RAW / arquivo)
            contagens[f"{SCHEMA}.{tabela}"] = gravar(con, df, SCHEMA, tabela)
    finally:
        con.close()

    largura = max(len(nome) for nome in contagens)
    for nome, n in contagens.items():
        print(f"{nome:<{largura}}  {milhar(n):>9}")
    print(f"{'total':<{largura}}  {milhar(sum(contagens.values())):>9}")


if __name__ == "__main__":
    main()
