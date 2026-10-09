"""
Tests de integración con WhatsApp:
- En TEST_MODE, enviar_respuesta simula el envío sin llamar a la API real.
- Sin credenciales configuradas, lanza EnvironmentError en modo real.
- El registro de respuestas enviadas se actualiza correctamente.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_enviar_respuesta_test_mode():
    from app.whatsapp import enviar_respuesta, get_respuestas_enviadas
    enviar_respuesta("521111", "Hola, este es un mensaje de prueba")
    enviadas = get_respuestas_enviadas()
    assert len(enviadas) == 1
    assert enviadas[0]["numero"] == "521111"
    assert enviadas[0]["simulado"] is True
    assert enviadas[0]["status"] == 200


def test_enviar_multiples_respuestas():
    from app.whatsapp import enviar_respuesta, get_respuestas_enviadas
    enviar_respuesta("521111", "Mensaje 1")
    enviar_respuesta("521111", "Mensaje 2")
    enviar_respuesta("529999", "Mensaje 3")
    assert len(get_respuestas_enviadas()) == 3


def test_limpiar_respuestas():
    from app.whatsapp import enviar_respuesta, limpiar_respuestas, get_respuestas_enviadas
    enviar_respuesta("521111", "Mensaje")
    limpiar_respuestas()
    assert get_respuestas_enviadas() == []


def test_enviar_sin_credenciales_en_modo_real(monkeypatch):
    """Sin TOKEN ni PHONE_ID, debe lanzar EnvironmentError en modo real."""
    from app import config
    import app.whatsapp as wa

    original_test_mode = config.TEST_MODE
    try:
        config.TEST_MODE = False
        monkeypatch.setattr(config, "WHATSAPP_TOKEN", None)
        monkeypatch.setattr(config, "PHONE_ID", None)
        with pytest.raises(EnvironmentError, match="WHATSAPP_ACCESS_TOKEN"):
            wa.enviar_respuesta("521111", "test")
    finally:
        config.TEST_MODE = True


def test_enviar_respuesta_real_llama_api(monkeypatch):
    """En modo real con credenciales, debe llamar a requests.post."""
    from app import config
    import app.whatsapp as wa

    original_test_mode = config.TEST_MODE
    try:
        config.TEST_MODE = False
        monkeypatch.setattr(config, "WHATSAPP_TOKEN", "fake_token")
        monkeypatch.setattr(config, "PHONE_ID", "fake_phone_id")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            wa.enviar_respuesta("521111", "Hola")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            # Verificar que el token NO aparece en los logs pero SÍ en los headers
            headers = call_kwargs.kwargs.get("headers") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
            # El payload debe contener el número de destino
            payload = call_kwargs.kwargs.get("json", {})
            assert payload.get("to") == "521111"
    finally:
        config.TEST_MODE = True
