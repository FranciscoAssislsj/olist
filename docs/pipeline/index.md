# Pipeline · visão geral

| Etapa | Comando | Lê | Escreve |
|---|---|---|---|
| [1. Ingestão](ingestao.md) | `uv run python -m pipeline.ingestao` | `raw/*.csv.gz` | schema `raw` |
| [2. Transformação](transformacao.md) | `uv run python -m pipeline.transformacao` | schema `raw` | schema `refined` |
| [3. Marts](marts.md) | `uv run python -m pipeline.marts` | schema `refined` | schema `marts` |

O acesso ao banco fica em `pipeline/db.py`:

| Função | O que faz |
|---|---|
| `PASTA_RAW` | `Path` da pasta com os nove `.csv.gz` |
| `conectar()` | abre o `olist.duckdb`, criando se faltar |
| `criar_schema(con, nome)` | `CREATE SCHEMA IF NOT EXISTS` |
| `gravar(con, df, schema, tabela)` | grava com `CREATE OR REPLACE` e devolve a contagem lida do banco |

## Regras comuns às três etapas

- **Reexecução segura.** Toda tabela é recriada, nunca acrescentada.
- **Pré-condição conferida antes de começar.** Se a entrada estiver incompleta, a etapa lista o que falta, diz o comando a rodar e encerra com `sys.exit(1)` sem gravar nada.
- **Saída na tela como conferência.** Uma linha por tabela, com a contagem lida do banco (não do DataFrame) e milhar com ponto. O `stdout` é reconfigurado para UTF-8, porque o Prompt de Comando do Windows embaralha acento.
