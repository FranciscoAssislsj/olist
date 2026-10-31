# 1. Ingestão

```bash
uv run python -m pipeline.ingestao
```

Os nove `.csv.gz` da Olist entram no schema `raw`, com nomes de tabela em português.

## Regras

**Nenhuma correção.** Nenhuma conversão de tipo, nenhuma linha descartada ou deduplicada, nenhum nome de coluna alterado, nenhum valor preenchido ou normalizado. Data continua texto, nulo continua nulo.
: A fronteira entre "o dado que chegou" e "o dado que eu decidi" precisa existir em algum lugar, e esse lugar é a passagem `raw` → `refined`.

**Tudo entra como texto.** `dtype=str`, inferência desligada.
: A inferência lê CEP com zero à esquerda como número, e o zero some sem aviso.

**Encoding declarado.** UTF-8, nunca adivinhado. O `.csv.gz` é lido direto, sem descompactar. Campo vazio vira nulo, não string vazia.
: Adivinhar encoding troca acento sem avisar; nulo e string vazia significam coisas diferentes na etapa seguinte.

**Os nove arquivos ou nada.** Antes de abrir o banco, confere se todos existem. Faltando qualquer um, lista os que faltam e encerra.
: Oito de nove tabelas ingeridas em silêncio produzem um dashboard errado que parece certo.

**Separação.** Este módulo não importa o `ui.py`, não sobe servidor e não depende da extensão `ui` do DuckDB.
