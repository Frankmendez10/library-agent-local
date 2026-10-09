"""
Capa de seguridad del agente: Llama Guard y Prompt Guard.

Llama Guard (vía Ollama):
  - Revisa contenido de entradas y salidas.
  - Devuelve (True, None) si es seguro, o (False, categoría) si no.
  - Si el servicio falla, lanza excepción — nunca trata el contenido como válido.

Prompt Guard (Hugging Face):
  - Detecta inyección de prompt.
  - Es opcional: si no está disponible (token HF faltante, modelo restringido),
    se desactiva y el agente continúa solo con Llama Guard.
  - En TEST_MODE, ambos guardrails devuelven resultados simulados seguros.
"""
import logging
from typing import Optional

from app import config

logger = logging.getLogger(__name__)

# ─── Mensajes de bloqueo ─────────────────────────────────────────────────────
MENSAJE_BLOQUEO = (
    "Lo siento, no puedo ayudar con ese mensaje. "
    "Si necesitas apoyo de la biblioteca, escríbeme tu duda."
)
MENSAJE_RESPUESTA_BLOQUEADA = (
    "No puedo compartir esa respuesta. "
    "Un miembro del equipo se pondrá en contacto contigo."
)

# ─── Estado de Prompt Guard ──────────────────────────────────────────────────
_prompt_guard_activo: bool = False
_pg_tokenizer = None
_pg_modelo = None


def inicializar_prompt_guard() -> bool:
    """
    Intenta cargar Prompt Guard desde Hugging Face.
    Retorna True si se cargó correctamente, False si no está disponible.
    En TEST_MODE siempre retorna False (se usa el stub).
    """
    global _prompt_guard_activo, _pg_tokenizer, _pg_modelo

    if config.TEST_MODE:
        logger.debug("TEST_MODE: Prompt Guard desactivado (stub)")
        return False

    if not config.HF_TOKEN:
        logger.warning(
            "HF_TOKEN no configurado — Prompt Guard desactivado. "
            "El agente continuará solo con Llama Guard."
        )
        return False

    try:
        from huggingface_hub import login
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        login(token=config.HF_TOKEN)
        _pg_tokenizer = AutoTokenizer.from_pretrained(config.PROMPT_GUARD_MODEL)
        _pg_modelo = AutoModelForSequenceClassification.from_pretrained(
            config.PROMPT_GUARD_MODEL
        )
        _prompt_guard_activo = True
        logger.info(
            "Prompt Guard cargado: %s. Etiquetas: %s",
            config.PROMPT_GUARD_MODEL,
            _pg_modelo.config.id2label,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Prompt Guard no disponible, el agente continuará solo con Llama Guard: %s",
            repr(exc),
        )
        _prompt_guard_activo = False
        return False


def prompt_guard_activo() -> bool:
    return _prompt_guard_activo


def es_inyeccion(texto: str) -> bool:
    """
    Retorna True si el texto parece un intento de inyección de prompt.
    - Si Prompt Guard no está activo, siempre retorna False.
    - En TEST_MODE, retorna False (stub seguro).
    """
    if not _prompt_guard_activo:
        return False

    if config.TEST_MODE:
        return False

    try:
        import torch

        entradas = _pg_tokenizer(
            texto, return_tensors="pt", truncation=True, max_length=512
        )
        with torch.no_grad():
            logits = _pg_modelo(**entradas).logits
        etiqueta = _pg_modelo.config.id2label[logits.argmax().item()].upper()
        return etiqueta not in ("BENIGN", "LABEL_0")
    except Exception as exc:
        # Si el modelo falla, no asumimos que es seguro: registramos y re-lanzamos
        logger.error("Error en Prompt Guard: %s", repr(exc))
        raise


def revisar_con_llama_guard(mensajes: list[dict]) -> tuple[bool, Optional[str]]:
    """
    Evalúa `mensajes` con Llama Guard.
    Retorna (True, None) si el contenido es seguro.
    Retorna (False, categoría) si es inseguro (ej. 'S9').
    Lanza excepción si el servicio no responde — NUNCA trata el contenido como válido ante fallo.

    En TEST_MODE retorna (True, None) sin llamar a Ollama.
    """
    if config.TEST_MODE:
        # Stub: detecta heurísticas básicas para que los tests de bloqueo funcionen
        for m in mensajes:
            contenido = m.get("content", "").lower()
            if any(
                kw in contenido
                for kw in ["bomba", "explosivo", "veneno", "droga", "arma", "matar"]
            ):
                return False, "S9"
        return True, None

    try:
        import ollama as ollama_lib

        r = ollama_lib.chat(model=config.LLAMA_GUARD_MODEL, messages=mensajes)
        veredicto = r["message"]["content"].strip().lower()

        if veredicto.startswith("safe"):
            return True, None
        if veredicto.startswith("unsafe"):
            partes = veredicto.split()
            categoria = partes[1].upper() if len(partes) > 1 else "sin_categoria"
            return False, categoria
        # Veredicto inesperado: no asumir que es seguro
        raise ValueError(f"Veredicto inesperado de Llama Guard: {veredicto!r}")
    except ValueError:
        raise
    except Exception as exc:
        logger.error("Llama Guard no disponible: %s", repr(exc))
        raise
