"""
Tests de monitoring:
- registrar_metrica guarda correctamente.
- registrar_bloqueo guarda correctamente.
- registrar_error guarda correctamente.
- resumen_metricas calcula correctamente.
- limpiar_metricas funciona.
"""
import pytest


def test_registrar_metrica():
    from app.monitoring import registrar_metrica, metricas
    registrar_metrica("521111", "llama", 1.23)
    assert len(metricas) == 1
    assert metricas[0]["ruta"] == "llama"
    assert metricas[0]["duracion_s"] == 1.23
    assert metricas[0]["numero"] == "521111"


def test_registrar_bloqueo():
    from app.monitoring import registrar_bloqueo, bloqueos
    registrar_bloqueo("521111", "texto peligroso", "llama_guard_entrada", "S9")
    assert len(bloqueos) == 1
    assert bloqueos[0]["capa"] == "llama_guard_entrada"
    assert bloqueos[0]["detalle"] == "S9"


def test_registrar_error():
    from app.monitoring import registrar_error, errores_procesamiento
    registrar_error("521111", "texto", "llama_timeout", "tardó mucho", TimeoutError("t"))
    assert len(errores_procesamiento) == 1
    assert errores_procesamiento[0]["causa"] == "llama_timeout"


def test_resumen_metricas_sin_datos():
    from app.monitoring import resumen_metricas
    resumen = resumen_metricas()
    assert resumen["total"] == 0


def test_resumen_metricas_con_datos():
    from app.monitoring import registrar_metrica, resumen_metricas

    registrar_metrica("521111", "llama", 2.0)
    registrar_metrica("521111", "regla_saludo", 0.1)
    registrar_metrica("521111", "error", 0.5)

    resumen = resumen_metricas()
    assert resumen["total"] == 3
    assert resumen["por_ruta"]["llama"] == 1
    assert resumen["por_ruta"]["regla_saludo"] == 1
    assert resumen["tasa_error"] == pytest.approx(1 / 3, abs=0.01)
    assert resumen["tiempo_promedio_s"] == pytest.approx((2.0 + 0.1 + 0.5) / 3, abs=0.01)
    assert resumen["tiempo_promedio_llama_s"] == 2.0


def test_resumen_metricas_sin_llama():
    from app.monitoring import registrar_metrica, resumen_metricas
    registrar_metrica("521111", "regla_saludo", 0.1)
    resumen = resumen_metricas()
    assert resumen["tiempo_promedio_llama_s"] is None


def test_limpiar_metricas():
    from app.monitoring import registrar_metrica, limpiar_metricas, metricas, bloqueos, errores_procesamiento
    registrar_metrica("521111", "llama", 1.0)
    limpiar_metricas()
    assert metricas == []
    assert bloqueos == []
    assert errores_procesamiento == []
