"""Fontes públicas remotas (arXiv)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
UA = {"User-Agent": "q-risk-brasil/1.0 (pesquisa academica)"}

CONSULTAS_ARXIV = {
    "ecdlp_recursos": 'all:"elliptic curve" AND all:"discrete logarithm" AND all:quantum AND all:resource',
    "rsa_recursos": 'all:"RSA" AND all:"noisy qubits"',
    "circuit_cutting_qudit": 'all:"circuit cutting" AND (all:qudit OR all:qutrit)',
    "wire_cutting_otimo": 'all:"wire cutting" AND all:optimal',
    "shor_qutrit": 'all:Shor AND (all:qutrit OR all:qudit)',
}


def buscar_arxiv(consulta: str, max_res: int = 25) -> dict:
    r = requests.get(
        ARXIV_API,
        params={"search_query": consulta, "start": 0, "max_results": max_res, "sortBy": "submittedDate", "sortOrder": "descending"},
        headers=UA,
        timeout=30,
    )
    r.raise_for_status()
    raiz = ET.fromstring(r.text)
    artigos = []
    for e in raiz.findall("a:entry", ATOM):
        artigos.append({
            "id": e.findtext("a:id", "", ATOM).rsplit("/", 1)[-1],
            "titulo": " ".join(e.findtext("a:title", "", ATOM).split()),
            "autores": [a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)],
            "publicado": e.findtext("a:published", "", ATOM)[:10],
            "resumo": " ".join(e.findtext("a:summary", "", ATOM).split()),
            "categoria": (e.find("arxiv:primary_category", ATOM).get("term") if e.find("arxiv:primary_category", ATOM) is not None else None),
            "url": e.findtext("a:id", "", ATOM),
        })
    return {"consulta": consulta, "artigos": artigos}
