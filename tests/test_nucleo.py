import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from qrisk import cache, mosca, shor  # noqa: E402


def test_mosca_desigualdade():
    r = mosca.avaliar(2026, shelf_life=10, migracao=7, ano_crqc=2035)
    assert r.ano_limite == 2043
    assert r.folga == -8 and r.em_risco
    assert not mosca.avaliar(2026, 2, 2, 2035).em_risco


def test_cdf_interpolacao():
    pts = [(2035, 0.28), (2040, 0.51)]
    assert mosca.interpolar_cdf(pts, 2025, 2025) == 0
    assert mosca.interpolar_cdf(pts, 2030, 2025) == pytest.approx(0.14)
    assert mosca.interpolar_cdf(pts, 2037.5, 2025) == pytest.approx(0.395)
    assert mosca.interpolar_cdf(pts, 2060, 2025) == pytest.approx(0.51)










def test_roetteler_p256():
    r = shor.roetteler_2017(256)
    assert r["qubits_logicos"] == 2330
    assert 1.2e11 < r["toffoli"] < 1.3e11






def test_cache_nao_recalcula(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE", tmp_path)
    chamadas = []

    def f():
        chamadas.append(1)
        return {"v": 1}

    _, hit1 = cache.obter_ou_calcular("t", "k", f)
    reg, hit2 = cache.obter_ou_calcular("t", "k", f)
    assert (hit1, hit2) == (False, True) and len(chamadas) == 1 and reg["v"] == 1




ATOM_EXEMPLO = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2302.03366v3</id>
    <published>2023-02-07T10:00:00Z</published>
    <title>Optimal wire cutting with
      classical communication</title>
    <summary>We study wire cutting.</summary>
    <author><name>Lukas Brenner</name></author>
    <author><name>Christophe Piveteau</name></author>
    <arxiv:primary_category term="quant-ph"/>
  </entry>
</feed>"""


def test_parser_arxiv(monkeypatch):
    from qrisk import fontes

    class Resp:
        text = ATOM_EXEMPLO

        def raise_for_status(self):
            pass

    monkeypatch.setattr(fontes.requests, "get", lambda *a, **k: Resp())
    r = fontes.buscar_arxiv("x")
    a = r["artigos"][0]
    assert a["id"] == "2302.03366v3" and a["titulo"] == "Optimal wire cutting with classical communication"
    assert a["autores"] == ["Lukas Brenner", "Christophe Piveteau"] and a["categoria"] == "quant-ph"
