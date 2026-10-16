"""Busca no arXiv para a revisão do estado da arte, com cache: o que já foi baixado não é baixado de novo.

    python pipelines/01_fetch.py           # consultas que faltam
    python pipelines/01_fetch.py --force   # refaz todas
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from qrisk import revisao  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    for nome, reg in revisao.buscar(forcar=ap.parse_args().force).items():
        print(f"[ok] {nome}: {len(reg['artigos'])} artigos")
