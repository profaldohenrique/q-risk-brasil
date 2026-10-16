"""Cache em disco endereçado por conteúdo. Nada é baixado ou processado duas vezes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
CACHE = DATA / "cache"
SEED = DATA / "seed"

CACHE.mkdir(parents=True, exist_ok=True)


def chave(*partes: str | bytes) -> str:
    h = hashlib.sha256()
    for p in partes:
        h.update(p if isinstance(p, bytes) else p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def caminho(categoria: str, k: str) -> Path:
    d = CACHE / categoria
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{k}.json"


def ler(categoria: str, k: str) -> dict | None:
    p = caminho(categoria, k)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def gravar(categoria: str, k: str, conteudo: dict, meta: dict | None = None) -> Path:
    p = caminho(categoria, k)
    registro = {
        "_meta": {"chave": k, "categoria": categoria, "gravado_em": datetime.now(timezone.utc).isoformat(), **(meta or {})},
        **conteudo,
    }
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
    return p


def obter_ou_calcular(categoria: str, k: str, fn: Callable[[], dict], meta: dict | None = None, forcar: bool = False) -> tuple[dict, bool]:
    """Retorna (registro, veio_do_cache)."""
    if not forcar:
        r = ler(categoria, k)
        if r is not None:
            return r, True
    conteudo = fn()
    gravar(categoria, k, conteudo, meta)
    return ler(categoria, k), False


def listar(categoria: str | None = None) -> list[dict]:
    base = CACHE / categoria if categoria else CACHE
    if not base.exists():
        return []
    out = []
    for p in sorted(base.rglob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return out


def apagar(categoria: str, k: str) -> bool:
    p = caminho(categoria, k)
    if p.exists():
        p.unlink()
        return True
    return False


def carregar_seed(nome: str) -> Any:
    return json.loads((SEED / nome).read_text(encoding="utf-8"))
