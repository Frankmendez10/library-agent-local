"""
Memoria conversacional por número de teléfono.

- Mantiene un conversation_id de Llama Stack por número.
- Normaliza números mexicanos (521XXXXXXXXXX → 52XXXXXXXXXX).
- Serializa los mensajes de un mismo número con un Lock individual
  para evitar condiciones de carrera.
- En TEST_MODE genera IDs locales sin llamar a Llama Stack.
"""
import threading
import uuid
import logging
from typing import Optional

from app import config

logger = logging.getLogger(__name__)

# { numero_normalizado: conversation_id }
_conversaciones: dict[str, str] = {}
# { numero_normalizado: threading.Lock }
_locks: dict[str, threading.Lock] = {}
_meta_lock = threading.Lock()  # protege el acceso a los dicts anteriores


def normalizar_numero(numero: str) -> str:
    """Normaliza números mexicanos con prefijo incorrecto 521 → 52."""
    if numero.startswith("521") and len(numero) == 13:
        return "52" + numero[3:]
    return numero


def obtener_lock(numero: str) -> threading.Lock:
    """Devuelve (creando si no existe) el Lock asociado a un número."""
    with _meta_lock:
        if numero not in _locks:
            _locks[numero] = threading.Lock()
        return _locks[numero]


def obtener_conversacion(numero: str, client=None) -> str:
    """
    Retorna el conversation_id para `numero`.
    Si no existe, crea una nueva conversación en Llama Stack (o genera un UUID
    local en TEST_MODE).
    """
    numero = normalizar_numero(numero)
    with _meta_lock:
        if numero in _conversaciones:
            return _conversaciones[numero]

    # Fuera del lock global para no bloquear mientras llama a la red
    if config.TEST_MODE or client is None:
        conv_id = f"test-conv-{uuid.uuid4().hex[:8]}"
        logger.debug("TEST_MODE: conversación local creada para %s → %s", numero, conv_id)
    else:
        try:
            conv = client.conversations.create()
            conv_id = conv.id
            logger.info("Nueva conversación Llama Stack para %s → %s", numero, conv_id)
        except Exception as exc:
            logger.error("No se pudo crear conversación para %s: %s", numero, exc)
            raise

    with _meta_lock:
        # Doble chequeo: otro hilo pudo haber creado la conversación mientras
        if numero not in _conversaciones:
            _conversaciones[numero] = conv_id
        return _conversaciones[numero]


def limpiar_conversaciones() -> None:
    """Elimina todas las conversaciones en memoria (útil para tests)."""
    with _meta_lock:
        _conversaciones.clear()
        _locks.clear()


def listar_conversaciones() -> dict[str, str]:
    """Devuelve copia del mapa número → conversation_id."""
    with _meta_lock:
        return dict(_conversaciones)
