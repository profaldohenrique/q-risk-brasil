from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_renderiza_tres_abas():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, at.exception
    assert [t.label for t in at.tabs] == ["Desafio: 10 qubits em 5", "Estado da arte", "Prazo de vulnerabilidade"]


def test_prazo_ano_fixo_sinaliza_atraso():
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.radio[0].set_value("Ano fixo").run()
    assert not at.exception
    assert any("Atrasado" in e.value for e in at.error)
