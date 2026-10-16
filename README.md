# Q-Risk Brasil

Resposta ao desafio técnico do Programa Inova Talentos (ICT Itaú, PROJ 1423710919), executada e reproduzível, mais duas ferramentas ligadas ao tema do projeto: revisão do estado da arte em estimativas de recursos para Shor e cálculo do prazo de vulnerabilidade de ECC.

Autor: Aldo Henrique Dias Mendes, doutor em Ciência da Computação (UnB, 2024).

## O painel

| aba | o que mostra |
|---|---|
| Desafio: 10 qubits em 5 | os 7 passos da resposta enviada, com os números gerados pelo código |
| Estado da arte | tabela curada de estimativas para ECDLP e RSA, tendência ao longo dos anos e triagem automática de artigos do arXiv |
| Prazo de vulnerabilidade | desigualdade de Mosca com a curva de especialistas do GRI, marcos do NIST e calculadora de tempo de Shor |

## O desafio

> Otimizar um circuito de 10 qubits e profundidade 20, em Qiskit, para um hardware ruidoso de 5 qubits com conectividade linear. Quais métricas avaliam o sucesso e como lidar com a perda de qubits?

O problema é tratado como alocação de recursos: os qubits do circuito são cargas, os qubits do chip são máquinas com capacidade, vizinhança e confiabilidade. O circuito não cabe (10 lógicos para 5 físicos), então a resposta é reduzir a largura e pagar o custo de forma controlada.

| passo | o que o código faz | resultado |
|---|---|---|
| 1. Grafo de interação | arestas = pares de qubits com portas de 2 qubits | escada em linha, 3 portas por vizinho; a divisão mais barata corta 3 portas |
| 2. Reuso de qubits | procura qubits que terminam antes de outros começarem | nenhum: reuso não resolve |
| 3. Circuit cutting | `find_cuts` com 5 qubits por pedaço | 3 cortes, custo 729× em repetições, 432 circuitos |
| 4. Otimizar cada metade | `optimization_level` 0 contra 3 | profundidade 52 → 40; portas de 2 qubits iguais (12) |
| 5. Layout pela calibração | avalia as 60 ordens possíveis na linha | melhor ordem sem SWAP; a pior custa 30 portas de 2 qubits a mais |
| 6. Mitigação | planejado, não executado | leitura, desacoplamento dinâmico, ruído zero; sem PEC |
| 7. Validar em camadas | simulação ideal, depois com ruído, contra o valor exato | com ruído: Z0Z9 0,003 contra 0,004; Z4Z5 0,043 contra 0,031 |

Perda de qubits: perder uma ponta deixa uma linha de 4 e o custo sobe de 729 para 531 mil vezes; perder o qubit do meio parte a linha em dois pedaços de 2. O código refaz o plano com o que sobra e reporta quando fica inviável.

## Rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python pipelines/script_original.py   # o script enviado com a resposta, cerca de 1 minuto
python pipelines/02_desafio.py        # gera data/resultados/desafio.json para o painel, cerca de 5 minutos
python pipelines/01_fetch.py          # busca no arXiv para a aba Estado da arte (opcional)
streamlit run app.py
pytest -q
```

A triagem do arXiv usa regex por padrão. Com [Ollama](https://ollama.com) rodando localmente, um modelo pequeno (por exemplo `ollama pull qwen2.5:3b`) complementa a extração.

## Limites

- **Correção após o envio.** No script original, o ruído era atribuído ao `SamplerV2` depois de criado, e o Aer ignora essa atribuição: os valores do PDF (0,003 e 0,041) são de simulação sem ruído. `qrisk/desafio.py` passa o ruído na criação e `tests/test_desafio_revisao.py::test_ruido_e_aplicado` protege contra a regressão. O script enviado fica em `pipelines/script_original.py` sem alterações.
- Os dois observáveis têm valor exato perto de zero, para onde o ruído empurra; o erro medido vem mais da estatística do corte do que do hardware.
- Tudo é simulação (`GenericBackendV2` com ruído). O próximo passo é rodar o mesmo código em hardware IBM, restringindo o layout a 5 qubits vizinhos.
- O circuito escolhido é favorável ao corte. Um circuito denso exigiria dezenas de cortes e seria inviável.
- A mitigação de erro está planejada, não implementada.
- A triagem automática do arXiv serve para encontrar artigos; os números que valem são os da tabela curada, conferidos no artigo.

## Estrutura

```
app.py                       painel (3 abas)
qrisk/desafio.py             os 7 passos do desafio
qrisk/revisao.py             busca no arXiv e extração de recursos dos resumos
qrisk/mosca.py, shor.py      prazo de vulnerabilidade e calculadora de Shor
qrisk/ui_*.py                interface de cada aba
pipelines/script_original.py script enviado com a resposta
pipelines/02_desafio.py      gera os resultados do painel
data/seed/referencias.json   referências curadas com links
data/resultados/             resultados gerados
tests/                       pytest
```
