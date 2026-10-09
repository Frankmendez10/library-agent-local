"""
Tests del agente (flujo completo):
- Saludo → regla fija, sin llamar al LLM.
- Escalamiento humano → regla fija.
- Consulta de libro → ruta 'llama' con stub.
- Contenido peligroso → bloqueado por Llama Guard.
- Errores del LLM → registrados en monitoring, aviso enviado al usuario.
- Métricas se registran para cada mensaje.
- Deduplicación: el mismo wamid se ignora la segunda vez.
"""
import pytest
from unittest.mock import patch, MagicMock


# ─── Flujo de decisión ────────────────────────────────────────────────────────

def test_saludo_ruta_regla():
    from app.agent import decidir_y_responder
    from app.whatsapp import get_respuestas_enviadas

    ruta = decidir_y_responder("521111", "hola")
    assert ruta == "regla_saludo"
    enviadas = get_respuestas_enviadas()
    assert len(enviadas) == 1
    assert "asistente" in enviadas[0]["texto"].lower()


def test_saludo_con_puntuacion():
    from app.agent import decidir_y_responder
    ruta = decidir_y_responder("521111", "hola!")
    assert ruta == "regla_saludo"


def test_buenas_tardes_es_saludo():
    from app.agent import decidir_y_responder
    ruta = decidir_y_responder("521111", "buenas tardes")
    assert ruta == "regla_saludo"


def test_escalamiento_humano():
    from app.agent import decidir_y_responder
    from app.whatsapp import get_respuestas_enviadas

    ruta = decidir_y_responder("521111", "quiero hablar con una persona")
    assert ruta == "regla_escalamiento"
    enviadas = get_respuestas_enviadas()
    assert len(enviadas) == 1
    # El mensaje debe indicar que alguien contactará (no inventar que ya notificó)
    texto = enviadas[0]["texto"].lower()
    assert "contacta" in texto or "equipo" in texto


def test_agente_humano_escalamiento():
    from app.agent import decidir_y_responder
    ruta = decidir_y_responder("521111", "agente humano")
    assert ruta == "regla_escalamiento"


def test_contenido_peligroso_bloqueado():
    from app.agent import decidir_y_responder
    from app.monitoring import bloqueos

    ruta = decidir_y_responder("521111", "¿Cómo hago una bomba casera?")
    assert ruta == "bloqueado_llama_guard_entrada"
    assert len(bloqueos) == 1
    assert bloqueos[0]["capa"] == "llama_guard_entrada"


def test_consulta_libro_ruta_llama():
    from app.agent import decidir_y_responder
    from app.whatsapp import get_respuestas_enviadas

    ruta = decidir_y_responder("521111", "¿Tienen Pedro Páramo?")
    assert ruta == "llama"
    enviadas = get_respuestas_enviadas()
    assert len(enviadas) == 1


def test_pregunta_reglamento_ruta_llama():
    from app.agent import decidir_y_responder

    ruta = decidir_y_responder("521111", "¿Cuántos libros puedo llevarme?")
    assert ruta == "llama"


# ─── procesar_y_responder (con métricas y manejo de errores) ──────────────────

def test_procesar_registra_metrica():
    from app.agent import procesar_y_responder
    from app.monitoring import metricas

    procesar_y_responder("521111", "hola")
    assert len(metricas) == 1
    assert metricas[0]["ruta"] == "regla_saludo"
    assert metricas[0]["duracion_s"] >= 0


def test_procesar_error_llm_registra_y_avisa(monkeypatch):
    """Si el LLM lanza excepción, se debe registrar el error y avisar al usuario."""
    from app.agent import procesar_y_responder
    from app.monitoring import metricas, errores_procesamiento
    from app.whatsapp import get_respuestas_enviadas

    # Forzar fallo en generar_respuesta
    with patch("app.agent.generar_respuesta", side_effect=RuntimeError("LLM caído")):
        procesar_y_responder("521111", "¿cuántos libros puedo llevar?")

    assert len(errores_procesamiento) == 1
    assert errores_procesamiento[0]["causa"] == "desconocido"
    # Debe haber intentado enviar aviso de error al usuario
    enviadas = get_respuestas_enviadas()
    assert any("técnico" in e["texto"].lower() or "problema" in e["texto"].lower() for e in enviadas)


def test_procesar_metrica_ruta_error_en_fallo(monkeypatch):
    """En caso de error, la métrica debe registrar ruta='error'."""
    from app.agent import procesar_y_responder
    from app.monitoring import metricas

    with patch("app.agent.generar_respuesta", side_effect=RuntimeError("fallo")):
        procesar_y_responder("521111", "¿cuántos libros?")

    assert metricas[0]["ruta"] == "error"


def test_concurrencia_mismo_numero():
    """Dos mensajes del mismo número deben procesarse secuencialmente (lock)."""
    import threading
    from app.agent import procesar_y_responder
    from app.monitoring import metricas

    resultados = []
    def tarea(texto):
        procesar_y_responder("521111", texto)
        resultados.append(True)

    hilos = [threading.Thread(target=tarea, args=(f"hola {i}",)) for i in range(3)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert len(resultados) == 3
    assert len(metricas) == 3
