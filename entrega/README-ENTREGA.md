# Entrega — Consolidador de reservas de hotel

## Resumo

Foram identificados e corrigidos **5 defeitos** no CLI (4 cobertos pelos testes fornecidos e 1
detectável apenas com os dados reais). Além das correções, foram adicionadas validações de
robustez na fronteira de entrada e **49 testes novos** em `tests/test_additional.py`, derivados
por particionamento de equivalência e análise de valor limite. Resultado final: **54 testes
passando** (os 5 fornecidos permanecem inalterados) e o relatório da amostra de validação
reproduz exatamente as tabelas do README.

## Defeitos corrigidos

| # | Arquivo | Defeito | Correção |
|---|---------|---------|----------|
| 1 | `src/onfly_report/services/stay_calculator.py` | Noites calculadas com `checkout.day - checkin.day` | `(checkout - checkin).days * rooms` |
| 2 | `src/onfly_report/services/currency_converter.py` | Valor **dividido** pela taxa, com a conta feita em `float` | `amount * rate` em `Decimal` puro |
| 3 | `src/onfly_report/services/status_policy.py` | Faturável definido como `status != "CANCELLED"` | `status == "CONFIRMED"` |
| 4 | `src/onfly_report/services/report_builder.py` | Ranking ordenado de forma **crescente** por valor | Chave `(-amount, hotel_id)`: valor desc., id asc. |
| 5 | `src/onfly_report/repositories/csv_reservation_repository.py` | Leitura interrompida silenciosamente na linha 200 | Limite removido; o arquivo é lido por inteiro |

### Causa raiz, em uma frase por defeito

1. **Noites:** a subtração usava apenas o componente "dia do mês" (`.day`) de cada data, o que
   coincide com a resposta certa dentro do mesmo mês mas produz valores errados (até negativos,
   ex.: 30/01→02/02 = −28) em qualquer virada de mês ou ano.
2. **Câmbio:** a operação estava invertida (divisão em vez de multiplicação por `rate_to_brl`) e
   passava por `float`, violando a regra de exatidão com `Decimal`.
3. **Status:** a política era uma *blocklist* ("tudo que não é CANCELLED fatura"), deixando
   `NO_SHOW` entrar nos totais; a regra é uma *allowlist* ("só CONFIRMED fatura").
4. **Ranking:** o `sorted` do Python é ascendente por padrão e a chave não invertia o valor,
   então o corte `[:top]` selecionava os hotéis de **menor** faturamento; a correção nega a chave
   numérica para obter valor descendente mantendo o desempate por `hotel_id` ascendente
   (um simples `reverse=True` inverteria também o desempate).
5. **Truncamento:** um `break` ao atingir 200 linhas descartava o restante do arquivo sem erro
   nem log — com os dados reais (300 reservas), o relatório sairia plausível porém errado.

## Como investiguei

1. **Leitura do README** e levantamento das regras de negócio e critérios de aceite.
2. **Leitura do código por camada** (CLI → serviços → repositórios), marcando pontos suspeitos
   por inspeção antes de rodar qualquer teste — os cinco defeitos foram localizados nessa etapa.
3. **Leitura da suíte fornecida**, mapeando cada teste ao defeito que ele mira (os cenários são
   cirúrgicos: virada de mês no teste de noites, taxa ≠ 1 no de câmbio, etc.).
4. **Execução do pytest** para confirmar cada hipótese contra os valores observados
   (ex.: −28 noites bate com `2 − 30`; total 118.45 bate com `100/1 + 100/5.42`).
5. **Correção incremental**: um defeito por vez, sempre com o menor diff que implementa a regra
   literal do README, rodando a suíte completa após cada correção para detectar regressões.
6. **Validação com dados reais**: a contagem de linhas do CSV real (300 reservas) expôs o
   defeito 5, que nenhum teste fornecido exercita (nenhum cria mais de 4 linhas).

## Melhorias de robustez (além das correções)

O README garante que os dados fornecidos são consistentes, portanto estas validações não
disparam no caminho feliz — elas trocam o modo de falha de "número errado silencioso" para
"erro explícito com código de saída 2":

- **`RowParser`**: rejeita status fora de `{CONFIRMED, CANCELLED, NO_SHOW}`, check-out anterior
  ao check-in e `rooms < 1`, sempre com o número da linha na mensagem.
- **`currency_converter`**: moeda sem taxa na tabela vira `InputFileError` nomeando a moeda
  (antes era `KeyError`, que saía com código 1 — "erro inesperado" — em vez de 2).

**Decisão sobre arquitetura**

A estrutura original já apresentava separação de responsabilidades entre repositórios, serviços, modelos e interface CLI. Por isso, optei por preservar a arquitetura existente e concentrar as alterações na correção dos defeitos e nas validações necessárias, evitando uma refatoração estrutural sem necessidade identificada.

## Testes adicionais (`tests/test_additional.py`)

49 testes derivados por **particionamento de equivalência** e **análise de valor limite**,
sem alterar nenhum arquivo fornecido (os cenários de erro usam um runner próprio, pois o
`run_cli` de `tests/helpers.py` afirma código de saída 0):

- **Comportamento por campo de saída**: `by_month` completo (ordenação ascendente com CSV fora
  de ordem, `reservations`, `room_nights` e `total_brl` agregados por mês), `top_hotels`
  completo (agregação de várias reservas por hotel, moedas mistas, `hotel_name`), envelope
  (`report_version`, `generated_at` com offset −03:00), dinheiro sem separador de milhar e a
  regra "demais colunas não afetam os totais".
- **Valores limite**: 201 linhas (limite exato do defeito 5), arquivo vazio, 0.125 no
  arredondamento (half-up dá 0.13; o half-even padrão daria 0.12), virada de ano, fevereiro
  bissexto, `checkout == checkin`, `--top` 0/1/maior que o nº de hotéis, `rooms` 0/−1,
  taxa de câmbio 0/negativa.
- **Partições inválidas** (todas → código de saída 2 com mensagem): 17 variações de linha
  inválida (status/moeda/datas/quartos/valor, incluindo campos vazios, data com barras, dia
  inexistente no calendário e valor com símbolo de moeda), 6 de tabela de câmbio inválida,
  4 de argumentos do CLI e 3 de arquivos/colunas ausentes.

## Como validar

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Suíte completa (fornecidos + adicionais)
pytest -q

# Relatório dos dados reais
PYTHONPATH=src python -m onfly_report \
  --input data/reservas_hoteis.csv \
  --rates data/taxas_cambio.csv \
  --output output/report.json
# Resumo esperado: Reservas: 300 | Confirmadas: 235 | Noites: 1347 | Total BRL: 396170.00

# Amostra de validação (comparar com as tabelas do README do desafio)
PYTHONPATH=src python -m onfly_report \
  --input data/exemplo-validacao.csv \
  --rates data/taxas_cambio.csv \
  --output output/exemplo.json
# Resumo esperado: Reservas: 12 | Confirmadas: 9 | Noites: 28 | Total BRL: 7566.00
```

A saída da amostra foi conferida campo a campo contra as tabelas do README (summary, by_month
e top_hotels): todos os valores e a ordenação coincidem.

## Resultado do pytest

```
$ pytest -q
......................................................                   [100%]
54 passed in 7.81s
```

## Decisões e limitações documentadas

- **`checkout == checkin` (day use)**: aceito, com 0 noites — o README só define a diferença
  não inclusiva; rejeitar a igualdade poderia recusar dado legítimo. Travado em teste.
- **`amount` negativo**: não validado — o README não define a semântica (poderia ser reembolso);
  sem resposta segura, a decisão foi não inventar regra.
- **BOM UTF-8**: CSVs com BOM (como o Excel grava) são rejeitados com "colunas obrigatórias
  ausentes", pois a leitura usa `utf-8` estrito; os dados do desafio não têm BOM. A melhoria
  seria `encoding="utf-8-sig"` nos dois repositórios — decidi não aplicar para manter o diff
  mínimo.
- **Memória**: o arquivo é materializado em lista (O(n) de espaço), adequado à escala do desafio
  (centenas de linhas, < 1 MB). Para milhões de linhas, a evolução seria transformar o
  repositório em gerador e agregar em streaming — não aplicado por ser otimização sem requisito.

## Uso de IA

Esta entrega seguiu o caminho **com IA** (Claude Code). A exportação da sessão e a declaração de
uso estão em `entrega/uso-de-ia/`.
