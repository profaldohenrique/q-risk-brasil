"""Q-Risk Brasil: a resposta ao desafio do ICT Itaú executada, revisão do estado da arte e prazo de vulnerabilidade."""
from __future__ import annotations

import streamlit as st

from qrisk import cache, ui_desafio, ui_prazo, ui_revisao

st.set_page_config(page_title="Q-Risk Brasil", layout="wide")


@st.cache_data
def referencias() -> dict:
    return cache.carregar_seed("referencias.json")


REFS = referencias()

st.title("Q-Risk Brasil")
st.caption("Aldo Henrique Dias Mendes · desafio técnico do Programa Inova Talentos, ICT Itaú (PROJ 1423710919)")

aba_desafio, aba_revisao, aba_prazo = st.tabs(["Desafio: 10 qubits em 5", "Estado da arte", "Prazo de vulnerabilidade"])

with aba_desafio:
    ui_desafio.render()

with aba_revisao:
    ui_revisao.render(REFS)

with aba_prazo:
    ui_prazo.render(REFS)

with st.sidebar:
    st.markdown(
        """
**Rodar localmente**
```
pip install -r requirements.txt
python pipelines/02_desafio.py
streamlit run app.py
```
**Reproduzir o PDF**
```
python pipelines/script_original.py
```
"""
    )
