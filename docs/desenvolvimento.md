# Desenvolvimento

## Estrutura de pastas

```text
olist/
├── app.py                  # painel Streamlit (entrada, fica na raiz para o deploy)
├── data/
│   ├── raw/                # os nove .csv.gz da Olist, versionados
│   └── olist.duckdb        # banco gerado pelo pipeline, fora do git
├── olist/                  # pacote Python
│   ├── config.py           # todos os caminhos do projeto
│   ├── pipeline/           # db, ingestao, transformacao, marts
│   ├── painel.py           # leitura dos marts, formatação e gráficos
│   ├── relatorio.py        # gera reports/relatorio.html
│   └── ui.py               # DuckDB UI no navegador
├── sql/marts/              # um .sql por mart: a regra de negócio
├── reports/                # relatorio.html gerado
├── tests/                  # pytest
├── docs/                   # páginas do MkDocs
├── mkdocs.yml
└── pyproject.toml
```

Os caminhos ficam todos em `olist/config.py`; nenhum outro módulo monta caminho a partir de `__file__`. Todo módulo roda com `python -m olist...` a partir da raiz.

## Testes

```bash
uv run pytest --cov
```

A cobertura mínima é de 60%, configurada em `pyproject.toml`. A conta mede o pacote `olist/`, menos o `olist/ui.py`; o `app.py` fica fora por estar na raiz.

| Arquivo | Cobre |
|---|---|
| `tests/test_db.py` | Conexão e gravação no DuckDB |
| `tests/test_ingestao.py` | Ingestão para `raw` |
| `tests/test_transformacao.py` | Tipos, duplicatas e nulos em `refined` |
| `tests/test_marts.py` | Execução dos `.sql`, erros e transação |
| `tests/test_painel.py` | Formatação e gráficos |
| `tests/test_relatorio.py` | Geração do `reports/relatorio.html` |

## Lint

```bash
uv run ruff check .
```

## Pre-commit

O `.pre-commit-config.yaml` roda, a cada commit, verificações de espaços, fim de arquivo, YAML/TOML, conflitos de merge e arquivos grandes, além do `ruff check --fix` e do `uv lock --check`. O ruff vem do ambiente do projeto, na mesma versão do CI.

```bash
# Instala o hook no .git (uma vez por clone)
uv run pre-commit install

# Roda todos os hooks em todos os arquivos
uv run pre-commit run --all-files
```

## Documentação

Esta documentação usa [MkDocs](https://www.mkdocs.org/) com o tema [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). As páginas ficam em `docs/` e a configuração em `mkdocs.yml`.

```bash
# Servidor local com recarga automática em http://127.0.0.1:8000
uv run --group docs mkdocs serve

# Gera o site estático em site/
uv run --group docs mkdocs build --strict
```

A cada push na `main`, o job `deploy` do workflow `.github/workflows/ci.yml` publica o site no GitHub Pages (veja [CI](#ci)).

## CI

O workflow `.github/workflows/ci.yml` roda a cada push na `main` ou na `dev` e em todo pull request. `lint`, `test` e `docs` rodam em paralelo; `deploy` só roda num push na `main` e só depois que os outros três passam:

| Job | Faz |
|---|---|
| `lint` | `ruff check .` |
| `test` | `pytest --cov`, com a cobertura mínima de 60%, e publica o `coverage.xml` como artefato |
| `docs` | `mkdocs build --strict`, para pegar link quebrado antes do merge; na `main`, empacota o `site/` para o Pages |
| `deploy` | Publica o site no GitHub Pages |

Os jobs de build usam `uv sync --locked`: se o `uv.lock` estiver desatualizado em relação ao `pyproject.toml`, o job falha.
