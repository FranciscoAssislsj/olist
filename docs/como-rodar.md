# Como rodar

## Requisitos

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Instalação

```bash
uv sync
```

## Pipeline

As três etapas rodam em ordem. A primeira cria o `olist.duckdb`, que não vai para o repositório.

```bash
uv run python -m pipeline.ingestao
uv run python -m pipeline.transformacao
uv run python -m pipeline.marts
```

Cada etapa confere se a anterior rodou e, se não rodou, diz qual comando rodar.

## Painel

=== "Streamlit"

    ```bash
    uv run streamlit run app.py
    ```

    Abre a página com filtro de período e o botão *Recarregar dados*.

=== "Relatório HTML"

    ```bash
    uv run python relatorio.py
    ```

    Gera o `relatorio.html`, um arquivo só, que abre em qualquer navegador sem servidor.

## Explorar o banco

```bash
uv run python ui.py
```

Abre o `olist.duckdb` em `http://localhost:4213` pela extensão `ui` do DuckDB. `Ctrl+C` encerra o servidor e libera o banco.

!!! warning "Um processo gravando por vez"
    O DuckDB aceita um único processo com o arquivo aberto para escrita. Com o `ui.py` de pé, a ingestão falha com `Could not set lock on file`. O painel abre o banco em modo somente leitura e fecha a conexão logo depois, então o `pipeline.marts` roda com ele aberto.
