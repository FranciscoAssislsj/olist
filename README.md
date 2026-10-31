# Olist · visão da operação

Pipeline de dados em Python + DuckDB sobre o [dataset público de e-commerce da Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), terminando em um painel Streamlit e em um relatório HTML estático.

```
raw/*.csv.gz ──► raw ──► refined ──► marts ──► painel (Streamlit) / relatorio.html
             ingestão  transformação  marts.py
```

## O que tem aqui

| Caminho | O que faz |
|---|---|
| `pipeline/ingestao.py` | Carrega os nove `.csv.gz` no schema `raw` do `olist.duckdb`, tudo como texto, sem nenhuma correção. |
| `pipeline/transformacao.py` | Leva oito tabelas de `raw` para `refined`: nomes em português, tipos declarados (datas, `DECIMAL` para dinheiro), conversão que falha para tudo em vez de virar nulo. |
| `pipeline/marts.py` | Executa cada `sql/marts/NN_nome.sql` como `CREATE TABLE marts.nome AS ...`. A regra de negócio mora inteira no `.sql`. |
| `pipeline/db.py` | Conexão e gravação no DuckDB. |
| `sql/marts/` | Os 12 marts: vendas mensais, top categorias, entrega no prazo, nota por categoria, recompra, ticket médio por UF, mix de pagamento, nota por prazo, Pareto de vendedores, tempo de entrega por UF, KPIs e clientes por UF. |
| `painel.py` | Leitura dos marts, formatação e gráficos Plotly. Não faz cálculo: número novo exige mart novo. |
| `app.py` | Painel Streamlit com KPIs, faturamento mensal com filtro de período e seis gráficos. |
| `relatorio.py` | Gera `relatorio.html`, o mesmo painel num arquivo HTML único, sem servidor. |
| `ui.py` | Abre o `olist.duckdb` no navegador pela extensão `ui` do DuckDB. |
| `test/` | Testes com pytest. |
| `design/rascunho.png` | Rascunho do layout do painel. |

Cada módulo traz no docstring a sua **SPEC**: as regras que segue e por que cada uma existe.

## Requisitos

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Como rodar

```bash
# 1. Dependências
uv sync

# 2. Pipeline (cria o olist.duckdb, que não vai para o repositório)
uv run python -m pipeline.ingestao
uv run python -m pipeline.transformacao
uv run python -m pipeline.marts

# 3. Painel
uv run streamlit run app.py

# ou o relatório estático
uv run python relatorio.py
```

Para explorar o banco no navegador (`http://localhost:4213`):

```bash
uv run python ui.py
```

> O DuckDB aceita um único processo gravando. Feche o `ui.py` e o painel antes de rodar o pipeline de novo.

## Testes e lint

```bash
uv run pytest --cov
uv run ruff check .
```

A cobertura mínima é de 60% (configurada em `pyproject.toml`).

## Dados

Os arquivos em `raw/` são o *Brazilian E-Commerce Public Dataset by Olist*, publicado no Kaggle sob a licença [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). São cerca de 100 mil pedidos feitos entre 2016 e 2018.
