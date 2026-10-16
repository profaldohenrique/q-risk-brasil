"""Revisão do estado da arte assistida por IA: estimativas de recursos para Shor (ECDLP e RSA).

Fluxo: busca no arXiv (com cache) -> extração dos números dos resumos (regex sempre; LLM local opcional)
-> tabela para revisão humana. Cada número extraído vem com o trecho do resumo que o originou.
Nada extraído automaticamente é tratado como verdade: a tabela curada (data/seed) é a referência.
"""
from __future__ import annotations

import json
import re

import requests

from . import cache
from .fontes import buscar_arxiv

CONSULTAS = {
    "ecdlp_recursos": 'all:"elliptic curve" AND all:"discrete logarithm" AND all:quantum AND (all:resource OR all:Toffoli)',
    "ecc_shor": 'all:Shor AND all:"elliptic curve" AND (all:qubits OR all:Toffoli)',
    "rsa_recursos": 'all:"RSA" AND all:factoring AND (all:"noisy qubits" OR all:"logical qubits")',
}

OLLAMA_HOST = "http://localhost:11434"

# ---------------------------------------------------------------- regex

_MULT = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12,
         "mil": 1e3, "milhão": 1e6, "milhões": 1e6, "bilhão": 1e9, "bilhões": 1e9}
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
_ESCALA = r"(?:\s*(thousand|million|billion|trillion|mil|milhão|milhões|bilhão|bilhões))?"


def _num(s: str, escala: str | None) -> float:
    return float(s.replace(",", "")) * _MULT.get((escala or "").lower(), 1)


def _trecho(texto: str, ini: int, fim: int, margem: int = 70) -> str:
    return re.sub(r"\s+", " ", texto[max(0, ini - margem): fim + margem]).strip()


def _achar(padrao: str, texto: str, conv) -> list[dict]:
    out = []
    for m in re.finditer(padrao, texto, flags=re.IGNORECASE):
        try:
            out.append({"valor": conv(m), "evidencia": _trecho(texto, m.start(), m.end())})
        except (ValueError, TypeError):
            continue
    return out


def alvo(texto: str) -> str | None:
    t = texto.lower()
    if re.search(r"secp256k1|bitcoin|ethereum", t):
        return "ECDLP-256 (secp256k1)"
    if re.search(r"elliptic|ecdlp|ecc\b|ecdsa", t):
        m = re.search(r"(\d{3})[- ]bit", t)
        return f"ECDLP-{m.group(1)}" if m else "ECDLP"
    m = re.search(r"rsa[- ]?(\d{4})|(\d{4})[- ]bit rsa", t)
    if m:
        return f"RSA-{m.group(1) or m.group(2)}"
    if "rsa" in t or "factor" in t:
        return "RSA"
    return None


def extrair_regex(texto: str) -> dict:
    """Números de recursos citados no texto, cada um com a evidência."""
    return {
        "alvo": alvo(texto),
        "qubits_logicos": _achar(_NUM + _ESCALA + r"\s*logical\s+qubits?", texto, lambda m: _num(m.group(1), m.group(2))),
        "qubits_fisicos": _achar(_NUM + _ESCALA + r"\s*(?:noisy|physical)\s+qubits?", texto, lambda m: _num(m.group(1), m.group(2))),
        "toffoli": _achar(_NUM + _ESCALA + r"\s*Toffoli", texto, lambda m: _num(m.group(1), m.group(2))),
        "tempo": _achar(r"(?:in|within|under)\s+((?:less than\s+)?(?:a|one|\d+(?:\.\d+)?)\s+(?:hours?|days?|weeks?|minutes?))",
                        texto, lambda m: m.group(1)),
    }


# ---------------------------------------------------------------- LLM local (opcional)

ESQUEMA = {"alvo": "ex: ECDLP-256, RSA-2048 ou null", "qubits_logicos": "número ou null",
           "qubits_fisicos": "número ou null", "toffoli": "número ou null", "tempo": "texto curto ou null",
           "contribuicao": "uma frase: o que o artigo melhora"}


def modelos_ollama(host: str = OLLAMA_HOST) -> list[str]:
    try:
        r = requests.get(f"{host}/api/tags", timeout=1.5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except (requests.RequestException, ValueError, KeyError):
        return []


def extrair_llm(texto: str, modelo: str, host: str = OLLAMA_HOST) -> dict:
    prompt = ("Extraia do resumo abaixo os campos do esquema. Use só o que está escrito; o que não aparecer é null. "
              f"Responda só com JSON.\nESQUEMA: {json.dumps(ESQUEMA, ensure_ascii=False)}\nRESUMO:\n{texto[:6000]}")
    r = requests.post(f"{host}/api/generate", timeout=120,
                      json={"model": modelo, "prompt": prompt, "format": "json", "stream": False, "options": {"temperature": 0}})
    r.raise_for_status()
    return json.loads(r.json()["response"])


# ---------------------------------------------------------------- pipeline

def buscar(forcar: bool = False) -> dict[str, dict]:
    """Roda as consultas que faltam no cache. Retorna {nome: registro}."""
    out = {}
    for nome, q in CONSULTAS.items():
        reg, _ = cache.obter_ou_calcular("arxiv", cache.chave("arxiv", q), lambda q=q: buscar_arxiv(q, 30), {"nome": nome}, forcar)
        out[nome] = reg
    return out


def _primeiro(itens: list[dict]):
    return itens[0]["valor"] if itens else None


def tabela(registros: list[dict], modelo: str | None = None) -> list[dict]:
    """Uma linha por artigo distinto, com os números extraídos e a evidência."""
    vistos, linhas = set(), []
    for reg in registros:
        for a in reg.get("artigos", []):
            base_id = a["id"].split("v")[0]
            if base_id in vistos:
                continue
            vistos.add(base_id)
            texto = f"{a['titulo']}. {a['resumo']}"
            k = cache.chave("extracao", base_id, modelo or "regex")
            ext, _ = cache.obter_ou_calcular("extracao", k, lambda t=texto: _extrair(t, modelo))
            rx = ext["regex"]
            llm = ext.get("llm") or {}
            linhas.append({
                "ano": int(a["publicado"][:4]) if a.get("publicado") else None,
                "titulo": a["titulo"],
                "alvo": llm.get("alvo") or rx["alvo"],
                "qubits_logicos": llm.get("qubits_logicos") or _primeiro(rx["qubits_logicos"]),
                "qubits_fisicos": llm.get("qubits_fisicos") or _primeiro(rx["qubits_fisicos"]),
                "toffoli": llm.get("toffoli") or _primeiro(rx["toffoli"]),
                "tempo": llm.get("tempo") or _primeiro(rx["tempo"]),
                "contribuicao": llm.get("contribuicao"),
                "evidencia": "; ".join(i["evidencia"] for campo in ("qubits_logicos", "qubits_fisicos", "toffoli") for i in rx[campo][:1]),
                "metodo": ext["metodo"],
                "url": a["url"],
            })
    linhas.sort(key=lambda r: (r["ano"] or 0), reverse=True)
    return linhas


def _extrair(texto: str, modelo: str | None) -> dict:
    out = {"regex": extrair_regex(texto), "llm": None, "metodo": "regex"}
    if modelo:
        try:
            out["llm"] = extrair_llm(texto, modelo)
            out["metodo"] = f"regex + {modelo}"
        except (requests.RequestException, ValueError, KeyError) as e:
            out["erro_llm"] = str(e)
    return out
