# 2. Transformação

```bash
uv run python -m olist.pipeline.transformacao
```

Oito tabelas saem de `raw` para `refined`: `pedidos`, `itens_pedido`, `pagamentos`, `clientes`, `vendedores`, `produtos`, `traducao_categorias` e `avaliacoes`. A `geolocalizacao` fica de fora, porque nenhum mart a lê.

## Nomes

As colunas são renomeadas para português em `snake_case` por um mapa fechado (`MAPA`): nenhuma coluna fora dele, nenhuma descartada.

## Tipos

| Colunas | Tipo | Por quê |
|---|---|---|
| `data_compra`, `data_aprovacao`, `data_envio`, `data_entrega`, `data_limite_envio`, `data_resposta` | `TIMESTAMP` | Formato declarado `'%Y-%m-%d %H:%M:%S'`, para o parser não adivinhar. |
| `data_entrega_prevista` | `DATE` | A hora é `00:00:00` nas 99.441 linhas; guardá-la seria inventar precisão. |
| `data_criacao` | `DATE` | A hora é `00:00:00` em 99.139 das 99.224 avaliações; nas outras 85 é `01:00:00`, efeito de horário de verão. |
| `preco`, `frete`, `valor` | `DECIMAL(10,2)` | `DOUBLE` não representa centavos com exatidão, e soma de dinheiro tem que fechar. |
| contagens e medidas (`item_seq`, `parcelas`, `peso_g`, `nota`...) | `INTEGER` | |
| todo o resto, inclusive `cep_prefixo` | `VARCHAR` | 23.995 clientes têm CEP começando com zero, e CEP nunca é somado. |

A conversão roda em SQL dentro do DuckDB (`strptime`, `CAST`): o dado já está no banco, e trazê-lo para a memória só para converter é custo sem ganho.

!!! danger "Conversão que falha para tudo"
    Só `strptime` e `CAST`, que estouram. Nunca `try_strptime`, `TRY_CAST` ou `errors="coerce"`. Ao falhar, a etapa mostra tabela, coluna e um exemplo do valor, e encerra.

    Um nulo fabricado pela conversão fica indistinguível, para sempre, de um nulo verdadeiro do dado.

## Duplicatas

Cada tabela tem sua chave em `CHAVES`. Em `avaliacoes` a chave é `(avaliacao_id, pedido_id)`, porque o mesmo `avaliacao_id` aparece em mais de um pedido.

- **Linha inteira repetida:** mantém uma e conta quantas saíram. Não carrega informação nova, então removê-la não decide nada.
- **Chave repetida com conteúdo diferente:** para, mostra a chave e as linhas conflitantes. Escolher uma seria decidir em silêncio.

## Nulos e anomalias

Nenhuma linha é apagada por ter nulo e nenhum nulo é preenchido. Anomalias de negócio também ficam: pedido `delivered` sem `data_entrega`, `data_envio` antes da `data_compra`, pedido com mais de uma avaliação.

O nulo é informação: pedido cancelado não tem data de entrega porque não foi entregue. `refined` não corrige fato; quem decide o que fazer com ele é o mart.

## Saída na tela

Uma linha por tabela (linhas que entram → linhas que saem, duplicatas removidas), as colunas com nulo e a contagem, e uma linha final com o total. Mostrar os nulos permite conferir que nenhum foi criado nem apagado.
