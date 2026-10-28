#!/usr/bin/env python3
"""Proof that this repo can reach both Azure resources.

    uv run python scripts/check_azure.py

No secrets are printed. Exits non-zero if any of the three legs fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mk_rag_lab.clients import chat, embed, index_client, settings
from mk_rag_lab.schema import EMBEDDING_DIMS, build_index


def main() -> int:
    s = settings()
    print(f"env file      : {s.env_file} ({'ok' if s.env_file.exists() else 'MISSING'})")
    print(f"openai        : {s.openai_endpoint}")
    print(f"search        : {s.search_endpoint}")
    print(f"índice        : {s.index_name}")
    failures = 0

    try:
        vector = embed(["prueba de conexión"])[0]
        ok = len(vector) == EMBEDDING_DIMS
        print(f"[{'ok' if ok else 'FAIL'}] embeddings  : {len(vector)} dims (esperado {EMBEDDING_DIMS})")
        failures += 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] embeddings  : {type(exc).__name__}: {exc}")
        failures += 1

    try:
        answer = chat([{"role": "user", "content": "Responde solo: ok"}])
        print(f"[{'ok' if answer else 'FAIL'}] chat        : {answer.strip()[:60]!r}")
        failures += 0 if answer else 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] chat        : {type(exc).__name__}: {exc}")
        failures += 1

    try:
        ic = index_client()
        ic.create_or_update_index(build_index(s.index_name))
        names = [ix.name for ix in ic.list_indexes()]
        ok = s.index_name in names
        print(f"[{'ok' if ok else 'FAIL'}] search      : índice '{s.index_name}' {'creado/existente' if ok else 'ausente'}")
        failures += 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] search      : {type(exc).__name__}: {exc}")
        failures += 1

    print("\n" + ("TODO VERDE" if failures == 0 else f"{failures} fallo(s)"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
