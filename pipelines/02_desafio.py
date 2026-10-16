"""Roda os passos do desafio e grava data/resultados/desafio.json (o painel lê daqui).

    python pipelines/02_desafio.py            # completo, cerca de 5 minutos
    python pipelines/02_desafio.py --rapido   # 1000 shots, sem estabilidade
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from qiskit_addon_cutting import generate_cutting_experiments  # noqa: E402

from qrisk import desafio as D  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args()
    shots = 1000 if a.rapido else 4000

    qc = D.circuito()
    arestas = D.grafo_interacao(qc)
    part, plano = D.planejar_corte(qc)
    sub, _ = generate_cutting_experiments(part.subcircuits, part.subobservables, num_samples=np.inf)
    layouts = D.avaliar_layouts(sub[0][0], D.hardware())

    out = {
        "circuito": D.contagem(qc),
        "grafo": [{"a": a_, "b": b_, "portas": w} for (a_, b_), w in sorted(arestas.items())],
        "corte_mais_barato": D.corte_mais_barato(arestas),
        "reuso_pares": D.reuso_possivel(qc),
        "plano": plano,
        "otimizacao_metade": D.otimizacao_por_metade(),
        "layouts": {"total": len(layouts), "melhores": layouts[:5], "pior": layouts[-1]},
        "baseline_10q": D.baseline_10q(),
        "execucao": D.executar(shots=shots),
        "ideal": D.executar(shots=shots, ruido=False),
        "perdas": D.analisar_perdas(),
        "observaveis": D.NOMES_OBS,
    }
    print("[ok] passos 1 a 5, execução e perdas")
    if not a.rapido:
        out["estabilidade"] = [D.executar(seed_hw=s, seed_sampler=s, shots=shots) for s in (42, 7, 2024)]
        print("[ok] estabilidade em 3 calibrações")

    destino = RAIZ / "data" / "resultados"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "desafio.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    e = out["execucao"]
    print(f"exato {np.round(e['exato'], 3)} reconstruído {np.round(e['reconstruido'], 3)} em {e['tempo_s']} s")


if __name__ == "__main__":
    main()
