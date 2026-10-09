"""
Tests de configuración:
- Variables con valores por defecto.
- Validación de WhatsApp (faltantes).
- TEST_MODE activo en el entorno de tests.
"""
import os


def test_test_mode_activo():
    from app import config
    assert config.TEST_MODE is True


def test_verify_token_cargado():
    from app import config
    assert config.VERIFY_TOKEN == "test_verify_token"


def test_valores_por_defecto():
    from app import config
    assert config.LLAMA_STACK_URL == "http://localhost:8321"
    assert config.PORT == 8000
    assert config.RAG_THRESHOLD == 0.30


def test_validar_para_whatsapp_detecta_faltantes(monkeypatch):
    """Sin WHATSAPP_ACCESS_TOKEN ni PHONE_NUMBER_ID, debe reportar ambas."""
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("PHONE_NUMBER_ID", raising=False)
    from app import config
    faltantes = config.validar_para_whatsapp()
    assert "WHATSAPP_ACCESS_TOKEN" in faltantes
    assert "PHONE_NUMBER_ID" in faltantes


def test_validar_para_whatsapp_ok(monkeypatch):
    """Con las variables configuradas, no debe reportar faltantes."""
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok_fake")
    monkeypatch.setenv("PHONE_NUMBER_ID", "123456")
    from app import config
    import importlib
    importlib.reload(config)
    faltantes = config.validar_para_whatsapp()
    assert faltantes == []
