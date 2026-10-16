"""Aba Desafio: a resposta enviada ao ICT Itaú, executada passo a passo."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "data" / "resultados" / "desafio.json"
SCRIPT = RAIZ / "pipelines" / "script_original.py"


def _f(v, casas=3) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def _int(v) -> str:
    return f"{int(v):,}".replace(",", ".")


def render() -> None:
    st.subheader("Otimizando um circuito de 10 qubits para um hardware de 5 qubits em linha")
    st.markdown(
        "Mapear qubits lógicos em qubits físicos com conectividade restrita é um problema de **alocação de recursos**: "
        "as cargas são os qubits do circuito, as máquinas são os qubits do chip, com capacidade, vizinhança e "
        "confiabilidade. Dividir um circuito que não cabe é particionar uma carga que não cabe num único host. "
        "Lidar com a perda de qubits é tolerância a falhas."
    )

    if not RES.exists():
        st.info("Resultados ainda não gerados. Rode `python pipelines/02_desafio.py`.")
        return
    r = json.loads(RES.read_text(encoding="utf-8"))
    e, ideal, b10 = r["execucao"], r["ideal"], r["baseline_10q"]

    st.markdown("#### O que o enunciado esconde: o circuito não cabe")
    c1, c2, c3 = st.columns(3)
    c1.metric("Largura", f"{r['circuito']['qubits']} lógicos", "5 físicos", delta_color="off")
    c2.metric("Topologia", "linha 0-1-2-3-4", "cada SWAP = 3 CNOTs", delta_color="off")
    c3.metric("Ruído", f"profundidade {r['circuito']['profundidade']}",
              f"vira {b10['profundidade']} nas portas nativas", delta_color="off")
    st.caption(f"Circuito testado: escada de CNOTs (RealAmplitudes linear, 3 repetições), "
               f"{r['circuito']['portas_2q']} CNOTs, profundidade {r['circuito']['profundidade']}.")

    # ------------------------------------------------------------------ passo 1
    st.markdown("#### 1. Entender o circuito: grafo de interação")
    st.markdown("Um vértice por qubit, uma aresta por par que recebe portas de 2 qubits, com o número de portas.")
    from qrisk.desafio import grafo_dot

    st.graphviz_chart(grafo_dot({(g["a"], g["b"]): g["portas"] for g in r["grafo"]}))
    cb = r["corte_mais_barato"]
    st.caption(f"A escada é uma linha: cada vizinho troca 3 portas. A divisão mais barata separa os qubits "
               f"{cb['bloco'][0]} a {cb['bloco'][-1]} dos demais e corta {cb['portas_cortadas']} portas (aresta em vermelho).")

    # ------------------------------------------------------------------ passo 2
    st.markdown("#### 2. Reduzir a largura sem dividir, se possível")
    n_reuso = len(r["reuso_pares"])
    st.markdown(
        f"Reaproveitar um qubit exige que ele termine antes de outro começar. Neste circuito há **{n_reuso} pares** "
        "assim: todos os qubits trabalham do início ao fim. Reuso não resolve, é preciso dividir."
        if n_reuso == 0 else f"{n_reuso} pares de qubits permitem reuso."
    )

    # ------------------------------------------------------------------ passo 3
    st.markdown("#### 3. Dividir o circuito (circuit cutting)")
    p = r["plano"]
    d1, d2, d3 = st.columns(3)
    d1.metric("Cortes", p["n_cortes"], "todos de porta", delta_color="off")
    d2.metric("Custo em repetições", f"{_int(p['overhead'])}×", "9 × 9 × 9", delta_color="off")
    d3.metric("Circuitos pequenos", _int(e["n_experimentos"]), "2 metades × 6³", delta_color="off")
    st.markdown(
        "Cada CNOT entre as metades é reescrita como combinação de operações locais com pesos positivos e negativos. "
        "Cada termo roda separado e os resultados são recombinados. **Cortar não é de graça:** cada CNOT cortado "
        "multiplica por 9 as repetições, e os cortes se multiplicam entre si."
    )

    # ------------------------------------------------------------------ passo 4
    st.markdown("#### 4. Otimizar cada metade")
    o = r["otimizacao_metade"]
    st.dataframe(pd.DataFrame([
        {"compilação": "optimization_level=0", "profundidade": o["opt0"]["profundidade"], "portas de 2 qubits": o["opt0"]["portas_2q"]},
        {"compilação": "optimization_level=3", "profundidade": o["opt3"]["profundidade"], "portas de 2 qubits": o["opt3"]["portas_2q"]},
    ]), hide_index=True, width="stretch")
    st.caption("A contagem de portas de 2 qubits não caiu porque a escada já é compatível com a linha e não precisa "
               "de SWAP. O ganho de profundidade veio da fusão de rotações.")

    # ------------------------------------------------------------------ passo 5
    st.markdown("#### 5. Escolher o layout usando a calibração")
    lay = r["layouts"]
    melhor, pior = lay["melhores"][0], lay["pior"]
    st.markdown(
        f"Na linha de 5 existem **{lay['total']} ordens** possíveis dos qubits lógicos (5!/2, porque ler a linha ao "
        "contrário dá o mesmo). Todas foram avaliadas: portas de 2 qubits depois do roteamento e probabilidade "
        "estimada de sucesso (ESP), calculada pelos erros de calibração de cada porta."
    )
    l1, l2 = st.columns(2)
    l1.metric("Melhor ordem", melhor["ordem"], f"{melhor['portas_2q']} portas 2q, ESP {_f(melhor['esp'])}", delta_color="off")
    l2.metric("Pior ordem", pior["ordem"], f"{pior['portas_2q']} portas 2q, ESP {_f(pior['esp'])}", delta_color="off")
    st.caption(f"A ordem errada custa {pior['portas_2q'] - melhor['portas_2q']} portas de 2 qubits a mais "
               f"({(pior['portas_2q'] - melhor['portas_2q']) // 3} SWAPs). Com outra calibração, a melhor ordem pode mudar.")
    with st.expander("As 5 melhores ordens"):
        st.dataframe(pd.DataFrame(lay["melhores"]), hide_index=True, width="stretch")

    # ------------------------------------------------------------------ passo 6
    st.markdown("#### 6. Mitigar o ruído que sobra")
    st.markdown(
        "Planejado, não executado neste experimento: correção de erro de leitura, desacoplamento dinâmico nos "
        "qubits ociosos e extrapolação para ruído zero. PEC fica de fora: o custo amostral dele se multiplicaria "
        "ao custo do corte."
    )

    # ------------------------------------------------------------------ passo 7
    st.markdown("#### 7. Validar em camadas")
    st.markdown("Simulação ideal, depois com ruído, sempre contra o valor exato.")
    tab = pd.DataFrame({
        "observável": r["observaveis"],
        "exato": [_f(v) for v in e["exato"]],
        "corte sem ruído (valores do PDF)": [_f(v) for v in ideal["reconstruido"]],
        "corte com ruído": [_f(v) for v in e["reconstruido"]],
        "erro com ruído": [_f(v) for v in e["erro"]],
    })
    st.dataframe(tab, hide_index=True, width="stretch")
    st.caption(f"{_int(e['shots_totais'])} execuções no total ({_int(e['n_experimentos'])} circuitos × 4.000). "
               "Ruído do hardware simulado (GenericBackendV2, 5 qubits em linha, seeds fixas).")
    st.warning(
        "**Correção após o envio.** No script original, o modelo de ruído era atribuído ao SamplerV2 depois de "
        "criado (`sampler.options.backend_options = ...`), e o Aer ignora essa atribuição. Os valores do PDF "
        "vieram, portanto, de simulação sem ruído. Aqui o ruído é passado na criação do sampler, e um teste "
        "automatizado garante que ele está sendo aplicado. O resultado com ruído ficou próximo porque os dois "
        "observáveis têm valor exato perto de zero, justamente para onde o ruído empurra: o erro medido (cerca "
        "de 0,01) vem mais da estatística do corte do que do hardware. O próximo experimento usa observáveis "
        "com valor exato grande, em que o efeito do ruído aparece."
    )

    # ------------------------------------------------------------------ métricas
    st.markdown("#### Métricas de sucesso")
    st.markdown("Duas perguntas: o circuito ficou mais barato de executar, e o resultado continuou correto?")
    estab = r.get("estabilidade") or []
    linha_estab = "-"
    if estab:
        erros = [max(x["erro"]) for x in estab]
        linha_estab = f"erro máximo entre {_f(min(erros))} e {_f(max(erros))} em {len(estab)} calibrações"
    met = pd.DataFrame([
        ("Portas de 2 qubits", f"{e['portas_2q_media']:.0f} por circuito pequeno, contra {b10['portas_2q']} do circuito inteiro", "São as que mais erram."),
        ("Profundidade", f"{e['profundidade_media']:.0f} por circuito pequeno, contra {b10['profundidade']} do circuito inteiro", "Mais tempo, mais perda de coerência."),
        ("SWAPs inseridos", f"0 no melhor layout; {(pior['portas_2q'] - melhor['portas_2q']) // 3} no pior", "Quanto a linha está custando."),
        ("Erro em relação ao ideal", f"{_f(max(e['erro']))} no pior observável", "Prova de que a otimização não quebrou o circuito."),
        ("Shots e tempo de QPU", f"{_int(e['shots_totais'])} execuções", "O preço do corte."),
        ("Estabilidade entre execuções", linha_estab, "Ganho que não se repete não é ganho."),
    ], columns=["métrica", "resultado", "por que importa"])
    st.dataframe(met, hide_index=True, width="stretch")

    # ------------------------------------------------------------------ perdas
    st.markdown("#### Perda de qubits")
    st.markdown(
        "- **Faltam qubits desde o início.** É o que os passos 2 e 3 resolvem; o número de qubits disponíveis é "
        "parâmetro do pipeline, nunca valor fixo.\n"
        "- **Um qubit degrada ou sai do ar.** Consulto a calibração antes de cada execução, excluo o que passou do "
        "limite e refaço a divisão com o que sobrou. Na linha, a posição importa:\n"
        "- **O qubit se perde durante a execução.** Quando é detectável, descarto as repetições afetadas; o custo é a "
        "fração descartada."
    )
    dfp = pd.DataFrame(r["perdas"])
    dfp["qubits_restantes"] = dfp["qubits_restantes"].apply(lambda xs: "-".join(map(str, xs)))
    dfp["overhead"] = dfp["overhead"].apply(lambda v: f"{v:.3g}×" if v >= 1e5 else f"{int(v)}×")
    st.dataframe(dfp.rename(columns={"qubit_perdido": "qubit perdido", "qubits_restantes": "maior trecho que sobra",
                                     "largura": "largura", "cortes": "cortes", "overhead": "custo em repetições"}),
                 hide_index=True, width="stretch")
    st.caption("Perder uma ponta deixa uma linha de 4 e o custo sobe de 729 para 531 mil vezes. Perder o qubit do meio "
               "parte a linha em dois pedaços de 2. Quando o custo fica inviável, reporto o limite em vez de entregar "
               "um número sem confiança.")

    # ------------------------------------------------------------------ código
    with st.expander("Código enviado com a resposta"):
        st.code(SCRIPT.read_text(encoding="utf-8"), language="python")

    with st.expander("Rodar de novo (cerca de 1 minuto)"):
        a1, a2 = st.columns(2)
        seed_hw = a1.selectbox("Calibração do hardware simulado (seed)", [42, 7, 2024])
        shots = a2.select_slider("Shots por circuito", [1000, 2000, 4000], 1000)
        if st.button("Rodar", key="rodar_desafio"):
            from qrisk.desafio import executar

            with st.spinner("Cortando, compilando e simulando 432 circuitos"):
                x = executar(seed_hw=seed_hw, seed_sampler=seed_hw, shots=shots)
            st.dataframe(pd.DataFrame({"observável": r["observaveis"], "exato": x["exato"],
                                       "reconstruído": x["reconstruido"], "erro": x["erro"]}), hide_index=True)
            st.caption(f"{x['tempo_s']} s")
