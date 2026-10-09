"""
Tests de memoria conversacional:
- Normalización de números mexicanos.
- Creación y reutilización de conversaciones.
- Deduplicación de conversation_id por número.
- Control de concurrencia (múltiples hilos).
"""
import threading

import pytest


def test_normalizar_numero_mexico():
    from app.memory import normalizar_numero
    assert normalizar_numero("5213312345678") == "523312345678"


def test_normalizar_numero_ya_correcto():
    from app.memory import normalizar_numero
    assert normalizar_numero("523312345678") == "523312345678"


def test_normalizar_numero_sin_prefijo_mx():
    from app.memory import normalizar_numero
    # Número no mexicano no debe modificarse
    assert normalizar_numero("15551234567") == "15551234567"


def test_conversacion_se_crea():
    from app.memory import obtener_conversacion
    conv_id = obtener_conversacion("521111")
    assert conv_id is not None
    assert len(conv_id) > 0


def test_conversacion_se_reutiliza():
    from app.memory import obtener_conversacion
    id1 = obtener_conversacion("521111")
    id2 = obtener_conversacion("521111")
    assert id1 == id2


def test_conversaciones_distintas_por_numero():
    from app.memory import obtener_conversacion
    id_a = obtener_conversacion("521111")
    id_b = obtener_conversacion("529999")
    assert id_a != id_b


def test_listar_conversaciones():
    from app.memory import obtener_conversacion, listar_conversaciones
    obtener_conversacion("521111")
    obtener_conversacion("529999")
    convs = listar_conversaciones()
    assert len(convs) == 2


def test_limpiar_conversaciones():
    from app.memory import obtener_conversacion, limpiar_conversaciones, listar_conversaciones
    obtener_conversacion("521111")
    limpiar_conversaciones()
    assert listar_conversaciones() == {}


def test_concurrencia_mismo_numero():
    """
    10 hilos solicitan conversación para el mismo número simultáneamente.
    Todos deben obtener el mismo conversation_id (sin duplicados).
    """
    from app.memory import obtener_conversacion, limpiar_conversaciones

    limpiar_conversaciones()
    resultados = []
    errores = []

    def tarea():
        try:
            conv_id = obtener_conversacion("5200000001")
            resultados.append(conv_id)
        except Exception as exc:
            errores.append(exc)

    hilos = [threading.Thread(target=tarea) for _ in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert not errores, f"Errores en hilos: {errores}"
    assert len(resultados) == 10
    assert len(set(resultados)) == 1, "Todos los hilos deben obtener el mismo conversation_id"


def test_lock_por_numero_es_distinto():
    from app.memory import obtener_lock
    lock_a = obtener_lock("521111")
    lock_b = obtener_lock("529999")
    assert lock_a is not lock_b


def test_lock_mismo_numero_es_identico():
    from app.memory import obtener_lock
    lock1 = obtener_lock("521111")
    lock2 = obtener_lock("521111")
    assert lock1 is lock2
