"""
Configuración centralizada del Library Agent.
Lee todos los secretos desde variables de entorno / archivo .env.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env si existe (no falla si no existe)
load_dotenv(Path(__file__).parent.parent / ".env")


def _get(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise EnvironmentError(
            f"Variable de entorno requerida '{name}' no está configurada. "
            f"Agrega '{name}=<valor>' a tu archivo .env o al entorno del sistema."
        )
    return value


# ─── WhatsApp ────────────────────────────────────────────────────────────────
# Fallback solo para desarrollo local. En producción SIEMPRE configura VERIFY_TOKEN en .env.
VERIFY_TOKEN: str = _get("VERIFY_TOKEN", "cambiar_en_produccion")
WHATSAPP_TOKEN: str | None = _get("WHATSAPP_ACCESS_TOKEN")
PHONE_ID: str | None = _get("PHONE_NUMBER_ID")
WABA_ID: str | None = _get("WABA_TOKEN_ID")

# ─── Llama Stack ─────────────────────────────────────────────────────────────
LLAMA_STACK_URL: str = _get("LLAMA_STACK_URL", "http://localhost:8321")
LLAMA_STACK_TIMEOUT: int = int(_get("LLAMA_STACK_TIMEOUT", "300"))
LLAMA_MODEL: str = _get("LLAMA_MODEL", "ollama/llama3.1:8b")

# ─── Ollama ───────────────────────────────────────────────────────────────────
OLLAMA_URL: str = _get("OLLAMA_URL", "http://localhost:11434")
LLAMA_GUARD_MODEL: str = _get("LLAMA_GUARD_MODEL", "llama-guard3")

# ─── Hugging Face (Prompt Guard) ─────────────────────────────────────────────
HF_TOKEN: str | None = _get("HF_TOKEN")
PROMPT_GUARD_MODEL: str = _get(
    "PROMPT_GUARD_MODEL", "meta-llama/Llama-Prompt-Guard-2-86M"
)

# ─── Embeddings (RAG) ─────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = _get(
    "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)
RAG_THRESHOLD: float = float(_get("RAG_THRESHOLD", "0.30"))

# ─── Modo de pruebas ──────────────────────────────────────────────────────────
# TEST_MODE=true → no se llama a servicios externos; se usan stubs locales
TEST_MODE: bool = _get("TEST_MODE", "false").lower() in ("1", "true", "yes")

# ─── Servidor ─────────────────────────────────────────────────────────────────
HOST: str = _get("HOST", "0.0.0.0")
PORT: int = int(_get("PORT", "8000"))
LOG_LEVEL: str = _get("LOG_LEVEL", "info")


def validar_para_whatsapp() -> list[str]:
    """
    Retorna lista de variables faltantes para que WhatsApp funcione.
    Úsala al arrancar para avisar al operador qué falta configurar.
    """
    faltantes = []
    for var in ("WHATSAPP_ACCESS_TOKEN", "PHONE_NUMBER_ID"):
        if not os.environ.get(var):
            faltantes.append(var)
    return faltantes
