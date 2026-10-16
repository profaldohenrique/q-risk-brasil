"""Desafio do ICT Itaú: circuito de 10 qubits num hardware de 5 qubits em linha.

Implementa os passos da resposta enviada (PDF), na mesma ordem. O caminho principal é o script original,
com as mesmas seeds, e reproduz os números do PDF:
  27 CNOTs, profundidade 17 -> 3 cortes, overhead 729, 432 circuitos -> profundidade 52 -> 40
  exato [0.004, 0.031] x reconstruído [0.003, 0.041]

A ideia central é tratar o problema como alocação de recursos: qubits lógicos são cargas, qubits físicos são
máquinas com capacidade, vizinhança (topologia) e confiabilidade (calibração).
"""
from __future__ import annotations

import itertools
import time

import numpy as np
from qiskit import transpile
from qiskit.circuit.library import real_amplitudes
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.quantum_info import SparsePauliOp, Statevector
from qiskit.transpiler import CouplingMap
from qiskit_addon_cutting import (
    DeviceConstraints,
    OptimizationParameters,
    cut_wires,
    expand_observables,
    find_cuts,
    generate_cutting_experiments,
    partition_problem,
    reconstruct_expectation_values,
)
from qiskit_aer.noise import NoiseModel
from qiskit_aer.primitives import SamplerV2

BASE = ["ecr", "rz", "sx", "x"]
OBSERVAVEIS = ["ZIIIIIIIIZ", "IIIIZZIIII"]  # Z0Z9 e Z4Z5 (qubit 0 é o caractere da direita)
NOMES_OBS = ["Z0 Z9", "Z4 Z5"]


# ======================================================================= circuito e hardware

def circuito(seed: int = 7):
    """Escada de CNOTs: RealAmplitudes linear, 10 qubits, 3 repetições, ângulos aleatórios fixos."""
    qc = real_amplitudes(10, entanglement="linear", reps=3).decompose()
    rng = np.random.default_rng(seed)
    return qc.assign_parameters(rng.uniform(0, np.pi, qc.num_parameters))


def hardware(n: int = 5, seed: int = 42, coupling: CouplingMap | None = None) -> GenericBackendV2:
    """Hardware simulado em linha. A seed muda a 'calibração' (erros e tempos de cada qubit)."""
    return GenericBackendV2(num_qubits=n, coupling_map=coupling or CouplingMap.from_line(n), basis_gates=BASE, seed=seed)


def valores_exatos(qc) -> list[float]:
    sv = Statevector(qc)
    return [float(sv.expectation_value(SparsePauliOp(p)).real) for p in OBSERVAVEIS]


def contagem(qc) -> dict:
    ops = qc.count_ops()
    return {"qubits": qc.num_qubits, "profundidade": qc.depth(),
            "portas_2q": int(sum(v for k, v in ops.items() if k in ("cx", "ecr", "cz")))}


# ======================================================================= passo 1: grafo de interação

def grafo_interacao(qc) -> dict[tuple[int, int], int]:
    """Aresta = par de qubits que recebe porta de 2 qubits; peso = quantas portas."""
    idx = {q: i for i, q in enumerate(qc.qubits)}
    arestas: dict[tuple[int, int], int] = {}
    for ins in qc.data:
        if ins.operation.num_qubits == 2:
            a, b = sorted(idx[q] for q in ins.qubits)
            arestas[(a, b)] = arestas.get((a, b), 0) + 1
    return arestas


def corte_mais_barato(arestas: dict, n: int = 10, largura: int = 5) -> dict:
    """Entre as divisões contíguas da linha, a que corta menos portas."""
    melhor = None
    for ini in range(0, n - largura + 1):
        bloco = set(range(ini, ini + largura))
        cortadas = sum(w for (a, b), w in arestas.items() if (a in bloco) != (b in bloco))
        if melhor is None or cortadas < melhor["portas_cortadas"]:
            melhor = {"bloco": sorted(bloco), "portas_cortadas": cortadas}
    return melhor


def grafo_dot(arestas: dict, destacar: tuple[int, int] | None = (4, 5)) -> str:
    linhas = ["graph G {", "  rankdir=LR; node [shape=circle, fontsize=11];"]
    for (a, b), w in sorted(arestas.items()):
        estilo = ', color="#d62728", penwidth=2.5' if destacar and (a, b) == destacar else ""
        linhas.append(f'  q{a} -- q{b} [label="{w}"{estilo}];')
    linhas.append("}")
    return "\n".join(linhas)


# ======================================================================= passo 2: reuso de qubits

def reuso_possivel(qc) -> list[tuple[int, int]]:
    """Pares (i, j) em que o qubit i termina antes de o qubit j começar: i poderia ser medido e reaproveitado."""
    from qiskit.converters import circuit_to_dag

    dag = circuit_to_dag(qc)
    idx = {q: i for i, q in enumerate(qc.qubits)}
    inicio, fim = {}, {}
    for camada, layer in enumerate(dag.layers()):
        for node in layer["graph"].op_nodes():
            for q in node.qargs:
                i = idx[q]
                inicio.setdefault(i, camada)
                fim[i] = camada
    return [(i, j) for i in fim for j in inicio if i != j and fim[i] < inicio[j]]


# ======================================================================= passo 3: corte

def planejar_corte(qc, largura: int = 5, seed: int = 111):
    obs = SparsePauliOp(OBSERVAVEIS)
    cut_circ, meta = find_cuts(qc, OptimizationParameters(seed=seed), DeviceConstraints(qubits_per_subcircuit=largura))
    qc_w = cut_wires(cut_circ)
    obs_w = expand_observables(obs.paulis, qc, qc_w)
    part = partition_problem(circuit=qc_w, observables=obs_w)
    return part, {"cortes": [c[0] for c in meta["cuts"]], "n_cortes": len(meta["cuts"]),
                  "overhead": float(meta["sampling_overhead"]),
                  "subcircuitos": {int(k): v.num_qubits for k, v in part.subcircuits.items()}}


# ======================================================================= passo 5: layout pela calibração

def ordens_na_linha(n: int = 5) -> list[tuple[int, ...]]:
    """Ordens de n qubits lógicos numa linha de n físicos; ler a linha ao contrário dá o mesmo: n!/2."""
    vistas, out = set(), []
    for p in itertools.permutations(range(n)):
        chave = min(p, p[::-1])
        if chave not in vistas:
            vistas.add(chave)
            out.append(p)
    return out


def esp(qc, backend) -> float:
    """Probabilidade estimada de sucesso: produto de (1 - erro) de cada operação, pela calibração."""
    t = backend.target
    idx = {q: i for i, q in enumerate(qc.qubits)}
    p = 1.0
    for ins in qc.data:
        nome = ins.operation.name
        if nome in ("barrier", "delay", "reset") or nome not in t.operation_names:
            continue
        props = t[nome].get(tuple(idx[q] for q in ins.qubits))
        if props is not None and props.error is not None:
            p *= 1 - props.error
    return float(p)


def avaliar_layouts(sub, backend) -> list[dict]:
    """Avalia as 60 ordens: portas de 2 qubits (SWAPs aparecem como 2q extras) e ESP pela calibração."""
    out = []
    for ordem in ordens_na_linha(sub.num_qubits):
        t = transpile(sub, backend, initial_layout=list(ordem), routing_method="sabre", optimization_level=1, seed_transpiler=1)
        c = contagem(t)
        out.append({"ordem": "-".join(map(str, ordem)), "portas_2q": c["portas_2q"], "profundidade": c["profundidade"], "esp": esp(t, backend)})
    return sorted(out, key=lambda r: (-r["esp"], r["portas_2q"]))


# ======================================================================= execução (script original)

def executar(seed_hw: int = 42, seed_sampler: int = 2026, shots: int = 4000, ruido: bool = True,
             largura: int = 5) -> dict:
    """Caminho do script enviado: corte, compilação opt 3, execução com ruído do backend, reconstrução."""
    t0 = time.time()
    qc = circuito()
    exato = valores_exatos(qc)
    part, plano = planejar_corte(qc, largura)
    subexp, coefs = generate_cutting_experiments(part.subcircuits, part.subobservables, num_samples=np.inf)
    backend = hardware(largura, seed_hw)
    isa = {k: transpile(v, backend, optimization_level=3, seed_transpiler=1) for k, v in subexp.items()}
    # O ruído precisa ir no construtor: atribuir sampler.options.backend_options depois (como no script
    # original) não tem efeito no SamplerV2 do Aer, e a simulação roda sem ruído.
    opcoes = {"backend_options": {"noise_model": NoiseModel.from_backend(backend)}} if ruido else None
    sampler = SamplerV2(seed=seed_sampler, options=opcoes)
    results = {k: sampler.run(v, shots=shots).result() for k, v in isa.items()}
    rec = [float(x) for x in reconstruct_expectation_values(results, coefs, part.subobservables)]
    todas = [c for v in isa.values() for c in v]
    return {
        "exato": exato, "reconstruido": rec,
        "erro": [abs(a - b) for a, b in zip(rec, exato)],
        "n_experimentos": len(todas), "shots_totais": len(todas) * shots,
        "profundidade_media": float(np.mean([c.depth() for c in todas])),
        "portas_2q_media": float(np.mean([contagem(c)["portas_2q"] for c in todas])),
        "esp_medio": float(np.mean([esp(c, backend) for c in todas])),
        "plano": plano, "seed_hw": seed_hw, "seed_sampler": seed_sampler, "ruido": ruido,
        "tempo_s": round(time.time() - t0, 1),
    }


def otimizacao_por_metade(seed_hw: int = 42) -> dict:
    """Passo 4: o mesmo subexperimento compilado com optimization_level 0 e 3."""
    qc = circuito()
    part, _ = planejar_corte(qc)
    subexp, _ = generate_cutting_experiments(part.subcircuits, part.subobservables, num_samples=np.inf)
    backend = hardware(5, seed_hw)
    out = {}
    for lvl in (0, 3):
        out[f"opt{lvl}"] = contagem(transpile(subexp[0][0], backend, optimization_level=lvl, seed_transpiler=1))
    return out


def baseline_10q(seed_hw: int = 42) -> dict:
    """O circuito inteiro num hardware linear de 10 qubits (referência que não existe no desafio)."""
    qc = circuito()
    b10 = hardware(10, seed_hw)
    t = transpile(qc, b10, optimization_level=3, seed_transpiler=1)
    return {**contagem(t), "esp": esp(t, b10)}


# ======================================================================= perda de qubits

def maior_trecho(n: int, perdidos: list[int]) -> list[int]:
    trechos, atual = [], []
    for q in range(n):
        if q in perdidos:
            trechos.append(atual)
            atual = []
        else:
            atual.append(q)
    trechos.append(atual)
    return max(trechos, key=len)


def analisar_perdas(n: int = 5) -> list[dict]:
    """Para cada qubit perdido: largura que sobra, cortes e custo do novo plano (sem executar)."""
    qc = circuito()
    linhas = []
    for perdido in [None, *range(n)]:
        trecho = maior_trecho(n, [] if perdido is None else [perdido])
        largura = len(trecho)
        _, plano = planejar_corte(qc, largura)
        linhas.append({"qubit_perdido": "nenhum" if perdido is None else perdido, "qubits_restantes": trecho,
                       "largura": largura, "cortes": plano["n_cortes"], "overhead": plano["overhead"]})
    return linhas
