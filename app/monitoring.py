"""
Logs y métricas del Library Agent.

- metricas: lista de dicts con ruta tomada y duración de cada mensaje procesado.
- bloqueos: mensajes o respuestas bloqueados por la capa de seguridad.
- errores_procesamiento: errores clasificados por causa.
- resumen_metricas(): imprime estadísticas básicas (volumen, latencia, tasa de error).
"""
import logging
import threading
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# ─── Almacenes de métricas (en memoria; en producción → base de datos / logs) ─
metricas: list[dict] = []
bloqueos: list[dict] = []
errores_procesamiento: list[dict] = []


def registrar_metrica(numero: str, ruta: str, duracion_s: float) -> None:
    with _lock:
        metricas.append(
            {"numero": numero, "ruta": ruta, "duracion_s": round(duracion_s, 2)}
        )
    logger.info(
        "mensaje procesado | numero=%s ruta=%s duracion=%.2fs",
        numero,
        ruta,
        duracion_s,
    )


def registrar_bloqueo(
    numero: str, texto: str, capa: str, detalle: Optional[str]
) -> None:
    with _lock:
        bloqueos.append(
            {"numero": numero, "texto": texto, "capa": capa, "detalle": detalle}
        )
    # No loguear el texto del usuario para evitar datos sensibles en logs
    logger.warning("bloqueo | numero=%s capa=%s detalle=%s", numero, capa, detalle)


def registrar_error(
    numero: str, texto: str, causa: str, detalle: str, error: Exception
) -> None:
    with _lock:
        errores_procesamiento.append(
            {
                "numero": numero,
                "texto": texto,
                "causa": causa,
                "detalle": detalle,
                "error": repr(error),
            }
        )
    logger.error(
        "error procesamiento | numero=%s causa=%s detalle=%s error=%s",
        numero,
        causa,
        detalle,
        repr(error),
    )


def resumen_metricas() -> dict:
    """
    Retorna un dict con estadísticas básicas y lo imprime también en el logger.
    """
    with _lock:
        total = len(metricas)
        if total == 0:
            logger.info("Aún no hay mensajes procesados.")
            return {"total": 0}

        por_ruta = Counter(m["ruta"] for m in metricas)
        errores = por_ruta.get("error", 0)
        tiempos = [m["duracion_s"] for m in metricas]
        tiempos_llama = [m["duracion_s"] for m in metricas if m["ruta"] == "llama"]

        resumen = {
            "total": total,
            "por_ruta": dict(por_ruta),
            "tasa_error": round(errores / total, 4),
            "tiempo_promedio_s": round(sum(tiempos) / total, 2),
            "tiempo_promedio_llama_s": (
                round(sum(tiempos_llama) / len(tiempos_llama), 2)
                if tiempos_llama
                else None
            ),
            "causas_error": (
                dict(Counter(e["causa"] for e in errores_procesamiento))
                if errores_procesamiento
                else {}
            ),
        }

    logger.info("resumen_metricas: %s", resumen)
    return resumen


def limpiar_metricas() -> None:
    """Limpia todos los almacenes (útil para tests)."""
    with _lock:
        metricas.clear()
        bloqueos.clear()
        errores_procesamiento.clear()
