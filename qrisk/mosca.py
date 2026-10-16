"""Desigualdade de Mosca e curva de probabilidade de CRQC.

Notação de Mosca (GRI Quantum Threat Timeline):
    x = shelf-life (anos que o dado precisa ficar sigiloso)
    y = tempo de migração para criptografia pós-quântica
    z = tempo até existir um CRQC
Há problema se x + y > z.

Aqui usamos anos absolutos: risco se ano_base + y + x > ano_crqc.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoMosca:
    ano_base: int
    shelf_life: int
    migracao: int
    ano_crqc: int
    ano_limite: int  # até quando o último dado cifrado com algoritmo clássico precisa ficar seguro
    folga: int       # ano_crqc - ano_limite; negativo = atrasado

    @property
    def em_risco(self) -> bool:
        return self.folga < 0


def avaliar(ano_base: int, shelf_life: int, migracao: int, ano_crqc: int) -> ResultadoMosca:
    limite = ano_base + migracao + shelf_life
    return ResultadoMosca(ano_base, shelf_life, migracao, ano_crqc, limite, ano_crqc - limite)


def interpolar_cdf(pontos: list[tuple[float, float]], ano: float, ano_zero: float) -> float:
    """CDF linear por partes. Assume P=0 em ano_zero e mantém o último valor após o último ponto.

    pontos: [(ano, probabilidade acumulada)], ordenáveis por ano.
    """
    pts = sorted([(float(ano_zero), 0.0)] + [(float(a), float(p)) for a, p in pontos if a > ano_zero])
    if ano <= pts[0][0]:
        return 0.0
    for (a0, p0), (a1, p1) in zip(pts, pts[1:]):
        if a0 <= ano <= a1:
            if a1 == a0:
                return p1
            return p0 + (p1 - p0) * (ano - a0) / (a1 - a0)
    return pts[-1][1]


def prob_risco(pontos: list[tuple[float, float]], ano_zero: float, ano_limite: float) -> float:
    """P(CRQC chegar até ano_limite), pela curva informada."""
    return min(1.0, max(0.0, interpolar_cdf(pontos, ano_limite, ano_zero)))
