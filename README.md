# Olist · visão da operação

Pipeline de dados em Python + DuckDB sobre o [dataset público de e-commerce da Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), terminando em um painel Streamlit e em um relatório HTML estático.

- **Painel:** https://olist-dash.streamlit.app/
- **Documentação:** https://franciscoassislsj.github.io/olist/

```
data/raw/*.csv.gz ──► raw ──► refined ──► marts ──► painel (Streamlit) / reports/relatorio.html
                  ingestão  transformação  sql/marts/*.sql
```

Tudo fica num arquivo só, `data/olist.duckdb`, em três schemas: `raw` (o dado como chegou), `refined` (nomes em português e tipos declarados) e `marts` (uma tabela por pergunta de negócio).

## Estrutura

```text
olist/
├── app.py                  # painel Streamlit (entrada, fica na raiz para o deploy)
├── data/
│   ├── raw/                # os nove .csv.gz da Olist, versionados
│   └── olist.duckdb        # banco gerado pelo pipeline, fora do git
├── olist/                  # pacote Python
│   ├── config.py           # todos os caminhos do projeto
│   ├── pipeline/
│   │   ├── db.py           # conexão e gravação no DuckDB
│   │   ├── ingestao.py     # data/raw -> schema raw
│   │   ├── transformacao.py  # raw -> refined
│   │   └── marts.py        # sql/marts/*.sql -> schema marts
│   ├── painel.py           # leitura dos marts, formatação e gráficos Plotly
│   ├── relatorio.py        # gera reports/relatorio.html
│   └── ui.py               # DuckDB UI no navegador
├── sql/marts/              # os 12 marts, um .sql cada
├── reports/                # relatorio.html gerado
├── tests/                  # pytest
├── docs/                   # documentação (MkDocs Material)
└── .github/workflows/      # CI: lint, testes, docs e deploy no Pages
```

| Caminho | O que faz |
|---|---|
| `olist/pipeline/ingestao.py` | Carrega os nove `.csv.gz` no schema `raw`, tudo como texto, sem nenhuma correção. |
| `olist/pipeline/transformacao.py` | Leva oito tabelas de `raw` para `refined`: nomes em português, tipos declarados (datas, `DECIMAL` para dinheiro), conversão que falha para tudo em vez de virar nulo. |
| `olist/pipeline/marts.py` | Executa cada `sql/marts/NN_nome.sql` como `CREATE TABLE marts.nome AS ...`. A regra de negócio mora inteira no `.sql`. |
| `sql/marts/` | Os 12 marts: vendas mensais, top categorias, entrega no prazo, nota por categoria, recompra, ticket médio por UF, mix de pagamento, nota por prazo, Pareto de vendedores, tempo de entrega por UF, KPIs e clientes por UF. |
| `olist/painel.py` | Leitura dos marts, formatação e gráficos Plotly. Não faz cálculo: número novo exige mart novo. |
| `app.py` | Painel Streamlit com KPIs, faturamento mensal com filtro de período e seis gráficos. Sem o banco, gera-o na primeira abertura. |
| `olist/relatorio.py` | Gera `reports/relatorio.html`, o mesmo painel num arquivo HTML único, sem servidor. |
| `olist/ui.py` | Abre o `data/olist.duckdb` no navegador pela extensão `ui` do DuckDB. |

Cada módulo traz no docstring a sua **SPEC**: as regras que segue e por que cada uma existe.

## Requisitos

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Como rodar

```bash
# 1. Dependências
uv sync

# 2. Pipeline (cria o data/olist.duckdb, que não vai para o repositório)
uv run python -m olist.pipeline.ingestao
uv run python -m olist.pipeline.transformacao
uv run python -m olist.pipeline.marts

# 3. Painel
uv run streamlit run app.py

# ou o relatório estático (reports/relatorio.html)
uv run python -m olist.relatorio
```

Para explorar o banco no navegador (`http://localhost:4213`):

```bash
uv run python -m olist.ui
```

> O DuckDB aceita um único processo gravando. Feche o `olist.ui` antes de rodar o pipeline de novo. O painel abre o banco só para leitura e não bloqueia.

## Testes e lint

```bash
uv run pytest --cov
uv run ruff check .
```

A cobertura mínima é de 60% (configurada em `pyproject.toml`), medida sobre o pacote `olist/`.

Hooks de pre-commit (ruff, `uv lock --check` e verificações de arquivo):

```bash
uv run pre-commit install
```

## Documentação

Publicada em https://franciscoassislsj.github.io/olist/ a cada push na `main`. Para editar as páginas em `docs/` com pré-visualização local:

```bash
uv run --group docs mkdocs serve   # http://127.0.0.1:8000
```

## Dados

Os arquivos em `data/raw/` são o *Brazilian E-Commerce Public Dataset by Olist*, publicado no Kaggle sob a licença [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). São cerca de 100 mil pedidos feitos entre 2016 e 2018.
