"""Configuration — reads credentials from outside the repo.

The env file defaults to ``$XDG_CONFIG_HOME/mk-rag-lab/env`` (``~/.config`` when the
variable is unset) and is never committed. Override the path with MK_RAG_ENV_FILE.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENV_FILE = Path(
    os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
) / "mk-rag-lab" / "env"


def _load_env_file(path: Path) -> None:
    """Minimal KEY=VALUE loader. Never overrides an already-set variable."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    openai_endpoint: str
    openai_key: str
    chat_deployment: str
    embed_deployment: str
    openai_api_version: str
    search_endpoint: str
    search_key: str
    index_name: str
    env_file: Path

    @classmethod
    def load(cls) -> Settings:
        env_file = Path(os.environ.get("MK_RAG_ENV_FILE", DEFAULT_ENV_FILE))
        _load_env_file(env_file)

        missing = [
            name
            for name in (
                "AZURE_OPENAI_ENDPOINT",
                "AZURE_OPENAI_KEY",
                "AZURE_SEARCH_ENDPOINT",
                "AZURE_SEARCH_KEY",
            )
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                f"faltan variables: {', '.join(missing)} — esperaba {env_file}"
            )

        return cls(
            openai_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/"),
            openai_key=os.environ["AZURE_OPENAI_KEY"],
            chat_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_CHAT", "chat"),
            embed_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_EMBED", "embed"),
            openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            search_endpoint=os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/"),
            search_key=os.environ["AZURE_SEARCH_KEY"],
            index_name=os.environ.get("AZURE_SEARCH_INDEX", "mk-rag-lab"),
            env_file=env_file,
        )
