"""Estimativas de recursos para Shor em ECDLP (curvas de n bits sobre corpo primo)."""
from __future__ import annotations

import math


def roetteler_2017(n: int) -> dict:
    """Limites superiores de Roetteler, Naehrig, Svore, Lauter (ASIACRYPT 2017, arXiv:1706.06752)."""
    lg = math.log2(n)
    return {
        "qubits_logicos": 9 * n + 2 * math.ceil(lg) + 10,
        "toffoli": 448 * n**3 * lg + 4090 * n**3,
    }


def tempo_execucao(toffoli: float, tempo_por_toffoli_s: float, fabricas_paralelas: int = 1) -> float:
    """Tempo de parede limitado por Toffolis sequenciais (modelo de primeira ordem)."""
    return toffoli * tempo_por_toffoli_s / max(1, fabricas_paralelas)


def formatar_duracao(seg: float) -> str:
    if seg < 60:
        return f"{seg:.1f} s"
    if seg < 3600:
        return f"{seg / 60:.1f} min"
    if seg < 86400:
        return f"{seg / 3600:.1f} h"
    if seg < 86400 * 365:
        return f"{seg / 86400:.1f} dias"
    return f"{seg / (86400 * 365):.1f} anos"
