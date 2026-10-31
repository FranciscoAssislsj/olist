# 3. Marts

```bash
uv run python -m pipeline.marts
```

Cada arquivo `sql/marts/NN_nome.sql` vira a tabela `marts.nome`:

```text
sql/marts/01_vendas_mensais.sql  ->  marts.vendas_mensais
```

O Python executa `CREATE TABLE marts.<nome> AS <conteúdo do arquivo>`. Tira espaços e um ponto e vírgula do final, e nada mais: não altera, não monta e não completa a SQL. A regra de negócio mora inteira no arquivo `.sql`.

O que cada mart responde está no [catálogo de marts](../marts.md).

## Adicionar um mart

1. Crie `sql/marts/NN_nome.sql` com um `SELECT`, com o prefixo numérico seguinte.
2. Rode `uv run python -m pipeline.marts`.
3. A tabela `marts.nome` aparece no banco.

Apagar o arquivo e rodar de novo faz a tabela sumir: o schema `marts` é apagado e recriado a cada execução, para que um mart sem arquivo não continue existindo.

## Erros

| Situação | O que acontece |
|---|---|
| Falta alguma das oito tabelas em `refined` | Lista quais e manda rodar a transformação. |
| `sql/marts/` vazio | Avisa e para; rodar sem arquivo apagaria todos os marts. |
| Arquivo sem prefixo `NN_`, ou dois arquivos com o mesmo nome de tabela | Para antes de executar qualquer SQL. |
| Um `.sql` falha | Mostra o nome do arquivo e a mensagem do DuckDB, e não executa os seguintes. |
| Um mart volta com zero linhas | Para. Mart vazio é quase sempre um `JOIN` que não casou. |

!!! success "Tudo numa transação"
    Se qualquer passo falhar, inclusive um mart vazio, o schema `marts` volta a ser o da última execução que deu certo. Um schema pela metade quebraria o dashboard sem avisar.
