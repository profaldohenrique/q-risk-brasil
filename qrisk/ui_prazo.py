"""Aba Prazo de vulnerabilidade: desigualdade de Mosca com a curva do GRI e calculadora de tempo de Shor."""
from __future__ import annotations

from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from . import mosca, shor

ANO = date.today().year


def render(REFS: dict) -> None:
    st.subheader("Prazo de vulnerabilidade")
    st.markdown(
        "A pergunta do projeto, em termos de decisão: um dado protegido por ECC hoje continua seguro pelo tempo "
        "que precisa? A resposta combina três tempos (desigualdade de Mosca) com a opinião de especialistas sobre "
        "quando surge um computador quântico capaz de quebrar ECC."
    )
    st.latex(r"\text{risco se}\quad x + y > z")
    st.markdown(
        "x = tempo que o dado precisa ficar sigiloso (shelf-life). "
        "y = tempo de migração para criptografia pós-quântica. "
        "z = tempo até existir um computador quântico criptograficamente relevante (CRQC). "
        "O último dado cifrado com RSA/ECC sai no fim da migração e precisa ficar seguro por mais x anos."
    )

    c1, c2, c3 = st.columns(3)
    ano_base = c1.number_input("Ano de início da migração", 2020, 2040, ANO)
    x = c2.slider("x: shelf-life do dado (anos)", 0, 30, 10)
    y = c3.slider("y: tempo de migração (anos)", 0, 15, 5)

    modo = st.radio("Modelo para z", ["Curva de especialistas (GRI)", "Ano fixo"], horizontal=True)

    gri_opts = {g["relatorio"]: g for g in REFS["gri_timeline"]}
    pts_baixa: list[tuple[float, float]] = []
    pts_alta: list[tuple[float, float]] = []
    ano_crqc = None

    if modo == "Ano fixo":
        ano_crqc = st.slider("Ano do CRQC (z)", ANO, 2060, 2035)
        res = mosca.avaliar(ano_base, x, y, ano_crqc)
    else:
        g = gri_opts[st.selectbox("Relatório", list(gri_opts))]
        df_g = pd.DataFrame(
            [{"ano": g["ano_survey"] + p["horizonte_anos"], "p_baixa": p["p_baixa"], "p_alta": p["p_alta"]} for p in g["pontos"]]
        )
        st.caption(f"Fonte: {g['relatorio']} ({g['respondentes']} especialistas), {g['url']}. Status: {g['status']}. Edite se quiser outro cenário.")
        df_g = st.data_editor(df_g, num_rows="dynamic", width="stretch", key="gri_edit")
        df_g = df_g.dropna(subset=["ano"])
        pts_baixa = [(r.ano, r.p_baixa if pd.notna(r.p_baixa) else r.p_alta) for r in df_g.itertuples() if pd.notna(r.p_alta) or pd.notna(r.p_baixa)]
        pts_alta = [(r.ano, r.p_alta if pd.notna(r.p_alta) else r.p_baixa) for r in df_g.itertuples() if pd.notna(r.p_alta) or pd.notna(r.p_baixa)]
        res = mosca.avaliar(ano_base, x, y, 0)

    limite = res.ano_limite
    m1, m2, m3 = st.columns(3)
    m1.metric("Dados precisam estar seguros até", limite)
    if modo == "Ano fixo":
        m2.metric("Folga (z - x - y)", f"{res.folga:+d} anos")
        if res.em_risco:
            m3.error(f"Atrasado em {-res.folga} anos. Dados capturados hoje (harvest now, decrypt later) ficam expostos.")
        else:
            m3.success(f"Dentro do prazo com {res.folga} anos de folga.")
    else:
        pb = mosca.prob_risco(pts_baixa, g["ano_survey"], limite)
        pa = mosca.prob_risco(pts_alta, g["ano_survey"], limite)
        m2.metric("P(CRQC até esse ano)", f"{pb:.0%} a {pa:.0%}")
        m3.metric("Captura hoje, dado sigiloso até", ano_base + x, help="Tráfego gravado hoje e decifrado depois")
        if not pts_alta:
            st.error("Curva vazia. Preencha ao menos um ponto.")
        elif limite > max(a for a, _ in pts_alta):
            st.warning("O ano-limite está além do último ponto da curva. A probabilidade foi mantida constante e é um piso.")

    nist = next(n for n in REFS["normas"] if n["id"].startswith("NIST IR 8547"))
    fim_mig = ano_base + y
    if fim_mig > nist["marcos"]["proibido_apos"]:
        st.error(f"Migração termina em {fim_mig}, depois de {nist['marcos']['proibido_apos']} (NIST IR 8547: algoritmos vulneráveis proibidos).")
    elif fim_mig > nist["marcos"]["deprecado_apos"]:
        st.warning(f"Migração termina em {fim_mig}, depois de {nist['marcos']['deprecado_apos']} (NIST IR 8547: RSA/ECC 112 bits deprecados).")

    # Gráfico
    anos = list(range(min(ANO, ano_base), max(2050, limite + 2) + 1))
    camadas = []
    if modo != "Ano fixo":
        curva = pd.DataFrame({
            "ano": anos,
            "baixa": [mosca.interpolar_cdf(pts_baixa, a, g["ano_survey"]) for a in anos],
            "alta": [mosca.interpolar_cdf(pts_alta, a, g["ano_survey"]) for a in anos],
        })
        base = alt.Chart(curva).encode(x=alt.X("ano:Q", axis=alt.Axis(format="d"), title="Ano"))
        camadas += [
            base.mark_area(opacity=0.25).encode(y=alt.Y("baixa:Q", title="P(CRQC até o ano)", axis=alt.Axis(format="%")), y2="alta:Q"),
            base.mark_line().encode(y="alta:Q"),
            base.mark_line(strokeDash=[4, 3]).encode(y="baixa:Q"),
        ]
    marcos = pd.DataFrame([
        {"ano": limite, "rotulo": "x + y"},
        {"ano": nist["marcos"]["deprecado_apos"], "rotulo": "NIST deprecado"},
        {"ano": nist["marcos"]["proibido_apos"], "rotulo": "NIST proibido"},
    ] + ([{"ano": ano_crqc, "rotulo": "CRQC (z)"}] if ano_crqc else []))
    regras = alt.Chart(marcos).mark_rule(strokeDash=[2, 2]).encode(x="ano:Q", tooltip=["rotulo", "ano"])
    textos = alt.Chart(marcos).mark_text(align="left", dx=4, dy=-6, angle=0).encode(x="ano:Q", y=alt.value(12), text="rotulo")
    if not camadas:
        camadas = [alt.Chart(pd.DataFrame({"ano": [anos[0], anos[-1]]})).mark_point(opacity=0).encode(x=alt.X("ano:Q", axis=alt.Axis(format="d")))]
    st.altair_chart(alt.layer(*camadas, regras, textos).properties(height=320), width="stretch")

    st.markdown("##### Normas de referência")
    st.dataframe(pd.DataFrame(REFS["normas"]).drop(columns=["marcos"], errors="ignore"), width="stretch", hide_index=True)

    st.markdown("##### Calculadora ECDLP (Roetteler et al. 2017, limite superior)")
    s1, s2, s3 = st.columns(3)
    nbits = s1.select_slider("Curva (bits do corpo primo)", [192, 224, 256, 384, 521], 256)
    r = shor.roetteler_2017(nbits)
    s1.metric("Qubits lógicos", f"{r['qubits_logicos']:,}".replace(",", "."))
    s1.metric("Toffoli", f"{r['toffoli']:.3e}")
    toff_alvo = s2.number_input("Toffoli a usar no cálculo de tempo", 1e6, 1e15, float(r["toffoli"]), format="%.3e",
                                help="Troque por 9e7 para comparar com arXiv:2603.28846")
    t_toff = s2.number_input("Tempo por Toffoli (µs)", 0.1, 10_000.0, 10.0, help="10 µs = tempo de reação típico assumido para supercondutores")
    fab = s2.number_input("Fábricas de estados mágicos em paralelo", 1, 1000, 1)
    dur = shor.tempo_execucao(toff_alvo, t_toff * 1e-6, fab)
    s3.metric("Tempo de parede estimado", shor.formatar_duracao(dur))
    s3.caption("Modelo de primeira ordem: Toffolis sequenciais limitados pelo tempo de reação. Não inclui overhead de roteamento nem destilação.")
