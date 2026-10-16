"""Aba Estado da arte: estimativas de recursos para Shor, curadas e extraídas do arXiv com IA."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from . import cache, revisao


def render(REFS: dict) -> None:
    st.subheader("Estado da arte: quanto custa quebrar ECC com Shor")
    st.markdown(
        "Primeira atividade da vaga: revisar o estado da arte em estimativa de recursos para Shor aplicado ao ECDLP. "
        "A tabela curada traz os números conferidos no artigo, com link. Abaixo dela, uma busca no arXiv com "
        "extração automática dos números dos resumos, para triagem: nada extraído entra na tabela curada sem revisão."
    )

    df = pd.DataFrame(REFS["estimativas_shor"]).sort_values(["alvo", "ano"])
    st.markdown("#### Tabela curada")
    st.dataframe(
        df[["ano", "alvo", "trabalho", "qubits_logicos", "qubits_fisicos", "toffoli", "tempo", "premissas", "url"]],
        hide_index=True, width="stretch",
        column_config={
            "url": st.column_config.LinkColumn("fonte", display_text="abrir"),
            "qubits_logicos": st.column_config.NumberColumn("qubits lógicos", format="%d"),
            "qubits_fisicos": st.column_config.NumberColumn("qubits físicos", format="%d"),
            "toffoli": st.column_config.NumberColumn("Toffoli", format="%.2e"),
        },
    )

    ecc = df[df["alvo"].str.startswith("ECDLP")]
    q = ecc.dropna(subset=["qubits_logicos"])
    t = ecc.dropna(subset=["toffoli"])
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**ECDLP-256: qubits lógicos caíram de 2330 para 1200 em 9 anos**")
        st.altair_chart(alt.Chart(q).mark_line(point=True).encode(
            x=alt.X("ano:O", title=None), y=alt.Y("qubits_logicos:Q", title="qubits lógicos", scale=alt.Scale(zero=True)),
            tooltip=["trabalho", "qubits_logicos"]).properties(height=220), width="stretch")
    with g2:
        st.markdown("**ECDLP-256: portas Toffoli caíram mais de mil vezes**")
        st.altair_chart(alt.Chart(t).mark_line(point=True).encode(
            x=alt.X("ano:O", title=None), y=alt.Y("toffoli:Q", title="Toffoli (escala log)", scale=alt.Scale(type="log")),
            tooltip=["trabalho", alt.Tooltip("toffoli:Q", format=".2e")]).properties(height=220), width="stretch")
    st.caption("Litinski 2023: 5 × 10⁷ Toffoli é o custo por chave amortizado em execuções paralelas; numa execução "
               "única são cerca de 2 × 10⁸. Por isso a queda vem de algoritmo, não de hardware: cada ganho antecipa o prazo.")

    st.markdown("#### Triagem automática no arXiv")
    modelos = revisao.modelos_ollama()
    c1, c2 = st.columns([2, 1])
    modelo = c2.selectbox("Extração", ["regex"] + modelos, help="Com Ollama rodando localmente, um LLM pequeno complementa a regex.")
    modelo = None if modelo == "regex" else modelo
    if c1.button("Buscar artigos (usa o cache; só consulta o que falta)"):
        with st.spinner("Consultando o arXiv"):
            try:
                revisao.buscar()
            except Exception as ex:  # noqa: BLE001
                st.error(f"arXiv indisponível: {ex}")
    regs = cache.listar("arxiv")
    if not regs:
        st.info("Nenhuma busca no cache ainda.")
        return
    linhas = revisao.tabela(regs, modelo)
    tab = pd.DataFrame(linhas)
    tab.insert(0, "revisado", False)
    st.caption(f"{len(tab)} artigos distintos. Cada número traz o trecho do resumo de onde saiu (coluna evidência). "
               "Marque 'revisado' depois de conferir no artigo e exporte.")
    editado = st.data_editor(
        tab, hide_index=True, width="stretch", disabled=[c for c in tab.columns if c != "revisado"],
        column_config={"url": st.column_config.LinkColumn("arXiv", display_text="abrir"),
                       "toffoli": st.column_config.NumberColumn("Toffoli", format="%.2e"),
                       "evidencia": st.column_config.TextColumn("evidência", width="large")},
    )
    st.download_button("Exportar CSV", editado.to_csv(index=False).encode("utf-8"), "triagem_arxiv.csv", "text/csv")
