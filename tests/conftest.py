"""
Configuración global de pytest.
Activa TEST_MODE para todos los tests y limpia el estado compartido entre pruebas.
"""
import os

import pytest

# Activar modo de pruebas ANTES de importar cualquier módulo de la app
os.environ["TEST_MODE"] = "true"
os.environ["VERIFY_TOKEN"] = "test_verify_token"
os.environ["LOG_LEVEL"] = "warning"


@pytest.fixture(autouse=True)
def limpiar_estado():
    """Limpia el estado en memoria entre cada test."""
    from app import memory, monitoring
    from app.whatsapp import limpiar_respuestas
    from app.knowledge import reiniciar_cache
    from app import agent

    memory.limpiar_conversaciones()
    monitoring.limpiar_metricas()
    limpiar_respuestas()
    reiniciar_cache()
    # Resetear el cliente singleton del agente
    agent._client = None
    yield
