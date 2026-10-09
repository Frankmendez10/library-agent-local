"""
Servidor FastAPI: webhook de WhatsApp Cloud API.

Endpoints:
  GET  /webhook   → verificación del webhook (Meta)
  POST /webhook   → recepción de mensajes entrantes
  GET  /health    → estado del servicio
  GET  /metrics   → resumen de métricas (solo para operadores)
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from app import config
from app import guardrails
from app import memory
from app import monitoring
from app.agent import procesar_y_responder
from app.memory import normalizar_numero

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=config.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ─── Estado de IDs procesados (deduplicación de mensajes) ────────────────────
_ids_procesados: set[str] = set()

# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Arranque
    if config.TEST_MODE:
        logger.info("=== Library Agent arrancando en TEST_MODE ===")
    else:
        logger.info("=== Library Agent arrancando en modo PRODUCCIÓN ===")
        faltantes = config.validar_para_whatsapp()
        if faltantes:
            logger.warning(
                "Variables de entorno faltantes para WhatsApp: %s. "
                "Los mensajes reales no se podrán enviar.",
                faltantes,
            )

    # Intentar cargar Prompt Guard (falla silenciosamente si no está disponible)
    guardrails.inicializar_prompt_guard()

    yield
    # Apagado
    logger.info("Library Agent detenido.")


app = FastAPI(
    title="Library Agent",
    description="Agente conversacional de biblioteca vía WhatsApp.",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "test_mode": config.TEST_MODE,
        "prompt_guard_activo": guardrails.prompt_guard_activo(),
    }


# ─── Métricas ─────────────────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    return monitoring.resumen_metricas()


# ─── Verificación del webhook (GET) ───────────────────────────────────────────
@app.get("/webhook")
async def verificar_webhook(request: Request):
    """
    Meta envía un GET con hub.verify_token y hub.challenge.
    Si el token coincide, respondemos con el challenge como texto plano.
    """
    params = request.query_params
    token_recibido = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    if token_recibido == config.VERIFY_TOKEN:
        logger.info("Webhook verificado correctamente.")
        return PlainTextResponse(content=challenge)

    logger.warning("Verificación de webhook fallida. Token recibido: %r", token_recibido)
    return JSONResponse(status_code=403, content={"error": "token inválido"})


# ─── Recepción de mensajes (POST) ─────────────────────────────────────────────
@app.post("/webhook")
async def recibir_mensaje(request: Request, background_tasks: BackgroundTasks):
    """
    Recibe notificaciones de WhatsApp Cloud API.
    - Responde 200 OK a Meta de inmediato (requisito de la API).
    - Deduplicación por wamid para ignorar reenvíos de Meta.
    - Delega el procesamiento pesado a BackgroundTasks.
    """
    body: dict[str, Any] = await request.json()

    try:
        mensaje = body["entry"][0]["changes"][0]["value"]["messages"][0]
        wamid: str = mensaje["id"]

        # Deduplicación
        if wamid in _ids_procesados:
            logger.debug("Mensaje duplicado ignorado: %s", wamid)
            return {"status": "ok"}
        _ids_procesados.add(wamid)

        # Solo procesamos mensajes de texto por ahora
        if mensaje.get("type") != "text":
            logger.debug("Tipo de mensaje no soportado: %s", mensaje.get("type"))
            return {"status": "ok"}

        numero = normalizar_numero(mensaje["from"])
        texto: str = mensaje["text"]["body"]

        logger.info("Mensaje recibido | wamid=%s numero=%s", wamid, numero)
        background_tasks.add_task(procesar_y_responder, numero, texto)

    except (KeyError, IndexError, TypeError):
        # Payload de Meta que no contiene un mensaje de texto (p. ej. status update)
        logger.debug("Payload sin mensaje de texto procesable")

    return {"status": "ok"}


# ─── Punto de entrada ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL,
    )
