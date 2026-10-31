# Como rodar

## Requisitos

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Instalação

```bash
uv sync
```

## Pipeline

As três etapas rodam em ordem. Leem os `.csv.gz` de `data/raw/` e gravam tudo em `data/olist.duckdb`, que não vai para o repositório.

```bash
uv run python -m olist.pipeline.ingestao
uv run python -m olist.pipeline.transformacao
uv run python -m olist.pipeline.marts
```

Cada etapa confere se a anterior rodou e, se não rodou, diz qual comando rodar.

## Painel

=== "Streamlit"

    ```bash
    uv run streamlit run app.py
    ```

    Abre a página com filtro de período e o botão *Recarregar dados*. Se o `data/olist.duckdb` não existir, o app roda as três etapas do pipeline na primeira abertura.

=== "Relatório HTML"

    ```bash
    uv run python -m olist.relatorio
    ```

    Gera o `reports/relatorio.html`, um arquivo só, que abre em qualquer navegador sem servidor.

## Explorar o banco

```bash
uv run python -m olist.ui
```

Abre o `data/olist.duckdb` em `http://localhost:4213` pela extensão `ui` do DuckDB. `Ctrl+C` encerra o servidor e libera o banco.

!!! warning "Um processo gravando por vez"
    O DuckDB aceita um único processo com o arquivo aberto para escrita. Com o `olist.ui` de pé, a ingestão falha com `Could not set lock on file`. O painel abre o banco em modo somente leitura e fecha a conexão logo depois, então o `olist.pipeline.marts` roda com ele aberto.
