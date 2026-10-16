"""Script enviado com a resposta ao desafio (PDF). Rodar: python pipelines/script_original.py"""
import numpy as np
from qiskit import transpile
from qiskit.circuit.library import real_amplitudes
from qiskit.quantum_info import SparsePauliOp, Statevector
from qiskit.transpiler import CouplingMap
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit_aer.noise import NoiseModel
from qiskit_aer.primitives import SamplerV2
from qiskit_addon_cutting import (find_cuts, OptimizationParameters, DeviceConstraints,
    cut_wires, expand_observables, partition_problem, generate_cutting_experiments,
    reconstruct_expectation_values)

# 1. Circuito de 10 qubits e observáveis
qc = real_amplitudes(10, entanglement="linear", reps=3).decompose()
rng = np.random.default_rng(7)
qc = qc.assign_parameters(rng.uniform(0, np.pi, qc.num_parameters))
print("original: width", qc.num_qubits, "depth", qc.depth(), "cx", qc.count_ops().get("cx", 0))
obs = SparsePauliOp(["ZIIIIIIIIZ", "IIIIZZIIII"])  # Z0Z9 e Z4Z5 (qubit 0 é o caractere da direita)
exato = [Statevector(qc).expectation_value(SparsePauliOp(p)).real for p in obs.paulis]

# 2. Busca de cortes
cut_circ, meta = find_cuts(qc, OptimizationParameters(seed=111),
                           DeviceConstraints(qubits_per_subcircuit=5))
print("cortes:", [c[0] for c in meta["cuts"]], "overhead:", round(meta["sampling_overhead"], 1))

# 3. Particionamento e geração dos subexperimentos
qc_w = cut_wires(cut_circ)
obs_w = expand_observables(obs.paulis, qc, qc_w)
part = partition_problem(circuit=qc_w, observables=obs_w)
subexp, coefs = generate_cutting_experiments(part.subcircuits, part.subobservables, num_samples=np.inf)
print("subcircuitos:", {k: v.num_qubits for k, v in part.subcircuits.items()},
      "subobservaveis:", {k: list(v) for k, v in part.subobservables.items()},
      "n experimentos:", sum(len(v) for v in subexp.values()))

# 4. Hardware alvo: 5 qubits em linha, base nativa, ruído
backend = GenericBackendV2(num_qubits=5, coupling_map=CouplingMap.from_line(5),
                           basis_gates=["ecr", "rz", "sx", "x"], seed=42)
for lvl in (0, 3):
    t = transpile(subexp[0][0], backend, optimization_level=lvl, seed_transpiler=1)
    print(f"subexperimento 0 opt{lvl}: depth {t.depth()}, 2q {t.count_ops().get('ecr', 0)}")

# 5. Compilação, execução com ruído e reconstrução
isa = {k: transpile(v, backend, optimization_level=3, seed_transpiler=1) for k, v in subexp.items()}
sampler = SamplerV2(seed=2026)  # seed fixa: resultado reproduzível
sampler.options.backend_options = {"noise_model": NoiseModel.from_backend(backend)}
results = {k: sampler.run(v, shots=4000).result() for k, v in isa.items()}
rec = reconstruct_expectation_values(results, coefs, part.subobservables)
print("exato:", np.round(exato, 3), "reconstruído:", np.round(rec, 3))

# 6. Baseline: o circuito inteiro num hardware linear de 10 qubits
b10 = GenericBackendV2(num_qubits=10, coupling_map=CouplingMap.from_line(10),
                       basis_gates=["ecr", "rz", "sx", "x"], seed=42)
t10 = transpile(qc, b10, optimization_level=3, seed_transpiler=1)
print("sem corte (10q em linha): depth", t10.depth(), "2q", t10.count_ops().get("ecr", 0))
