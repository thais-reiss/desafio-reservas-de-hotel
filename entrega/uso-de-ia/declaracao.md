# Declaração de uso de IA

## Ferramenta e modelo

- **Ferramenta:** Claude Code (extensão para VS Code, da Anthropic).
- **Modelo:** Claude Fable 5 (`claude-fable-5`).
- **Registro da utilização:** a exportação completa da sessão está disponível no arquivo `sessao.md`, nesta pasta.

## Como o trabalho foi conduzido

O desenvolvimento seguiu um processo incremental, definido por mim desde o primeiro prompt, dividido em etapas: compreensão do escopo, análise da arquitetura, análise dos testes, diagnóstico dos problemas, correção individual dos defeitos e validação final.

Cada etapa era submetida à minha análise antes de prosseguir. As alterações no código também dependiam da minha avaliação e autorização. Para cada defeito identificado, solicitei que a IA apresentasse a justificativa técnica, diferentes abordagens de solução, seus respectivos prós e contras e uma recomendação fundamentada. A escolha da abordagem a ser implementada ficou sob minha responsabilidade.

## O que a IA fez

- Analisou o README e os arquivos do projeto, produzindo resumos sobre o escopo, a arquitetura e a suíte de testes.
- Executou os testes fornecidos, auxiliando na identificação das causas dos problemas e na comparação entre os resultados observados e os comportamentos esperados.
- Identificou e apresentou o diagnóstico dos cinco defeitos: quatro apontados pelos testes fornecidos e um adicional, referente ao truncamento em 200 linhas, identificado por inspeção do código e confirmado pela contagem de linhas do CSV real.
- Apresentou alternativas de correção para cada defeito e, após minha decisão, implementou as alterações aprovadas.
- Auxiliou na implementação de validações de robustez e na criação de testes adicionais, verificando também se as novas validações afetavam os dados fornecidos por meio de uma varredura dos arquivos CSV.
- Executou a suíte completa após as alterações e realizou testes de fumaça para verificar os códigos de saída.

## O que eu fiz

- Defini a estratégia de trabalho, a sequência das etapas e os critérios de interação com a IA.
- Analisei os resultados apresentados, solicitei esclarecimentos técnicos e avaliei as alternativas propostas antes de decidir quais alterações seriam implementadas.
- Tomei as decisões de implementação dos cinco defeitos e das quatro questões de robustez, considerando os requisitos, o escopo e o comportamento esperado do projeto.
- Questionei possíveis impactos das soluções propostas, incluindo a remoção do limite de 200 linhas e a alteração de encoding para BOM, antes de definir as abordagens adotadas.
- Solicitei que as discussões sobre robustez e a ampliação dos testes fossem realizadas em etapas próprias, após a conclusão das correções dos defeitos.
- Executei os testes de forma independente na minha máquina e conferi manualmente a saída da amostra de validação com as tabelas apresentadas no README.
- Solicitei a ampliação da suíte de testes utilizando as estratégias de particionamento de equivalência e análise de valor limite. Também revisei a cobertura proposta, identificando cenários e campos de saída que precisavam ser complementados, adicionando testes tanto para valores válidos quanto para valores inválidos.
- Realizei a revisão final das alterações, verificando se as implementações estavam alinhadas às decisões tomadas e se os resultados dos testes correspondiam ao comportamento esperado.