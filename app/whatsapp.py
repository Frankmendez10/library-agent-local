"""
Integración con WhatsApp Cloud API (Meta Graph API).

- enviar_respuesta(): POST al endpoint de mensajes de Meta.
- En TEST_MODE, simula el envío sin llamar a la API real.
- Los tokens nunca se loguean; solo el status_code y el número de destino.
"""
import logging
from typing import Optional

import requests

from app import config

logger = logging.getLogger(__name__)

# Registro interno para pruebas (no loguea el contenido en producción)
_respuestas_enviadas: list[dict] = []


def enviar_respuesta(numero: str, texto: str) -> None:
    """
    Envía un mensaje de texto al número de WhatsApp indicado.

    Lanza requests.exceptions.RequestException si la API de Meta rechaza el envío
    (p. ej. token vencido → 401, número inválido → 400).
    El caller es responsable de capturar y registrar ese error.
    """
    if config.TEST_MODE:
        logger.debug("TEST_MODE: mensaje simulado → %s: %r", numero, texto[:80])
        _respuestas_enviadas.append(
            {"numero": numero, "status": 200, "texto": texto, "simulado": True}
        )
        return

    if not config.WHATSAPP_TOKEN or not config.PHONE_ID:
        raise EnvironmentError(
            "WHATSAPP_ACCESS_TOKEN y PHONE_NUMBER_ID deben estar configurados "
            "para enviar mensajes reales."
        )

    url = f"https://graph.facebook.com/v21.0/{config.PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto},
    }

    # No loguear headers (contienen el token)
    logger.debug("Enviando mensaje a %s (%d chars)", numero, len(texto))
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    _respuestas_enviadas.append(
        {"numero": numero, "status": response.status_code, "simulado": False}
    )
    response.raise_for_status()


def get_respuestas_enviadas() -> list[dict]:
    """Retorna copia del registro de respuestas (para tests e inspección)."""
    return list(_respuestas_enviadas)


def limpiar_respuestas() -> None:
    """Limpia el registro de respuestas (útil para tests)."""
    _respuestas_enviadas.clear()
