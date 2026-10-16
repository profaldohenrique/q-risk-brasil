import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from qrisk import desafio as D  # noqa: E402
from qrisk import revisao as R  # noqa: E402


# ---------------------------------------------------------------- desafio: números do PDF

def test_circuito_do_pdf():
    assert D.contagem(D.circuito()) == {"qubits": 10, "profundidade": 17, "portas_2q": 27}


def test_grafo_e_corte_mais_barato():
    g = D.grafo_interacao(D.circuito())
    assert len(g) == 9 and set(g.values()) == {3}
    assert D.corte_mais_barato(g)["portas_cortadas"] == 3


def test_reuso_impossivel():
    assert D.reuso_possivel(D.circuito()) == []


def test_plano_de_corte_do_pdf():
    _, p = D.planejar_corte(D.circuito())
    assert p["n_cortes"] == 3 and p["overhead"] == pytest.approx(729) and p["subcircuitos"] == {0: 5, 1: 5}


def test_otimizacao_por_metade_do_pdf():
    o = D.otimizacao_por_metade()
    assert o["opt0"]["profundidade"] == 52 and o["opt3"]["profundidade"] == 40
    assert o["opt0"]["portas_2q"] == o["opt3"]["portas_2q"] == 12


def test_sessenta_ordens_na_linha():
    assert len(D.ordens_na_linha(5)) == 60


def test_perdas():
    assert D.maior_trecho(5, [2]) in ([0, 1], [3, 4])
    linhas = {l["qubit_perdido"]: l for l in D.analisar_perdas()}
    assert linhas["nenhum"]["overhead"] == pytest.approx(729)
    assert linhas[0]["largura"] == 4 and linhas[0]["overhead"] > 729


# ---------------------------------------------------------------- revisão

RESUMO = ("We estimate that a 256-bit elliptic curve discrete logarithm can be computed with 1,200 logical qubits "
          "and 90 million Toffoli gates, or in less than a week with fewer than 500 thousand physical qubits.")


def test_extracao_de_resumo():
    x = R.extrair_regex(RESUMO)
    assert x["alvo"] == "ECDLP-256"
    assert x["qubits_logicos"][0]["valor"] == 1200
    assert x["toffoli"][0]["valor"] == pytest.approx(9e7)
    assert x["qubits_fisicos"][0]["valor"] == pytest.approx(5e5)
    assert "logical qubits" in x["qubits_logicos"][0]["evidencia"]


def test_alvo_rsa():
    assert R.alvo("How to factor 2048 bit RSA integers") == "RSA-2048"


def test_tabela_deduplica_e_usa_cache(tmp_path, monkeypatch):
    from qrisk import cache

    monkeypatch.setattr(cache, "CACHE", tmp_path)
    art = {"id": "2603.28846v1", "titulo": "ECDLP", "resumo": RESUMO, "publicado": "2026-03-30", "url": "u"}
    linhas = R.tabela([{"artigos": [art]}, {"artigos": [dict(art, id="2603.28846v2")]}])
    assert len(linhas) == 1 and linhas[0]["qubits_logicos"] == 1200 and linhas[0]["ano"] == 2026


def test_ruido_e_aplicado():
    """Regressão: o script original atribuía o ruído depois de criar o SamplerV2, e ele era ignorado."""
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer.noise import NoiseModel
    from qiskit_aer.primitives import SamplerV2

    b = D.hardware()
    qc = QuantumCircuit(2)
    qc.h(0)
    for _ in range(20):
        qc.cx(0, 1)
    qc.measure_all()
    isa = transpile(qc, b, optimization_level=0)
    sem = SamplerV2(seed=1).run([isa], shots=4000).result()[0].data.meas.get_counts()
    tardio = SamplerV2(seed=1)
    tardio.options.backend_options = {"noise_model": NoiseModel.from_backend(b)}
    tardio = tardio.run([isa], shots=4000).result()[0].data.meas.get_counts()
    com = SamplerV2(seed=1, options={"backend_options": {"noise_model": NoiseModel.from_backend(b)}}).run([isa], shots=4000).result()[0].data.meas.get_counts()
    assert tardio == sem
    assert com.get("10", 0) + com.get("11", 0) > 0
