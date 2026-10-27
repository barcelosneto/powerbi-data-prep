# Antes do painel: preparar fatos e dimensões

Exemplo original em Python, somente biblioteca padrão, com duas aplicações demonstradas: preparar tabelas para um modelo em estrela e percorrer a origem incrementalmente com generators.

```console
python prepare_model.py amostra.csv saida-modelo
python -m unittest discover -s . -p "test_*.py" -v
```

Escolha uma pasta de saída que ainda não exista. O programa preserva a entrada, rejeita contratos inválidos e só entrega a pasta final depois da geração. `summary.json` traz contagem, soma em centavos e hash da origem.

## Dados e contrato

- Origem fictícia UTF-8, delimitada por `;`, cabeçalho na ordem `movement_id;date;product;category;amount`.
- Um movimento por linha; ID Int64 positivo e único; datas ISO `AAAA-MM-DD`.
- Valor finito, não negativo, ponto decimal, no máximo duas casas. Saída monetária em centavos inteiros evita arredondamento de float.
- Nomes de produto/categoria não podem começar por prefixos de fórmula de planilha; máximo de 120 caracteres.
- A amostra contém 6 movimentos, 3 produtos, 2 categorias, cinco datas contínuas e soma de 25.100 centavos.

## Arquivos e relacionamentos sugeridos no Power BI

Importe `fact_movement.csv`, `dim_date.csv`, `dim_product.csv` e `dim_category.csv` com codificação UTF-8 e delimitador vírgula. As chaves e `amount_cents` são números inteiros. Em `dim_date`, a coluna `date` deve ter tipo Data.

Crie relações 1:* das dimensões para a tabela de fatos, por `date_key`, `product_key` e `category_key`, com filtro em direção única. Não conecte dimensões entre si. O grão da fato é um movimento. Produto e categoria são dimensões separadas nesta demonstração; o mesmo nome de produto em categorias diferentes recebe chaves diferentes.

Medida DAX sugerida para estudo:

```dax
Valor Total = DIVIDE(SUM(fact_movement[amount_cents]), 100)
```

Formate como moeda conforme o contexto. Resultado esperado para toda a amostra: 251,00. Este repositório entrega preparação de dados e instruções: **não contém PBIX nem painel validado no Power BI Desktop**. A medida e os relacionamentos são propostas de importação, não execução comprovada de DAX.

## Como os generators são usados

`read_movements()` entrega registros sob demanda. Há duas passagens: uma para as chaves das dimensões e outra para escrever a fato. O programa mantém IDs e dimensões em memória, portanto não é uma solução de memória constante. Não foram medidos ganhos de desempenho. O hash detecta alterações comuns da origem entre as passagens; não é um bloqueio transacional contra escritores concorrentes.

Testes verificam soma, grão, chaves válidas, datas contínuas, erro tardio no generator, entradas inválidas e preservação da origem/saída existente.

Referências: [Microsoft — Star schema](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema), [Python — generators](https://docs.python.org/3/howto/functional.html#generators) e [Real Python — generators](https://realpython.com/introduction-to-python-generators/). Implementação própria; licença MIT em `LICENSE` nesta pasta.


## Projeto independente

Este código foi separado do ExcelFlow para manter um escopo próprio. O histórico da pasta foi preservado na extração com Git. O projeto usa somente a biblioteca padrão do Python; os comandos acima devem ser executados na raiz deste repositório.
