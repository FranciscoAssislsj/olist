# Desenvolvimento

## Testes

```bash
uv run pytest --cov
```

A cobertura mínima é de 60%, configurada em `pyproject.toml`. `app.py` e `ui.py` ficam fora da conta.

| Arquivo | Cobre |
|---|---|
| `test/test_db.py` | Conexão e gravação no DuckDB |
| `test/test_ingestao.py` | Ingestão para `raw` |
| `test/test_transformacao.py` | Tipos, duplicatas e nulos em `refined` |
| `test/test_marts.py` | Execução dos `.sql`, erros e transação |
| `test/test_painel.py` | Formatação e gráficos |
| `test/test_relatorio.py` | Geração do `relatorio.html` |

## Lint

```bash
uv run ruff check .
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
