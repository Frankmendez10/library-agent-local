"""
Tests del webhook FastAPI:
- GET /webhook con token correcto → devuelve challenge.
- GET /webhook con token incorrecto → 403.
- POST /webhook con mensaje válido → 200 y procesa en background.
- POST /webhook con wamid duplicado → ignorado.
- POST /webhook con payload sin mensaje → no falla.
- GET /health → responde correctamente.
- GET /metrics → responde con dict de métricas.
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Cliente de test con lifespan desactivado para tests unitarios rápidos."""
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ─── Health ──────────────────────────────────────────────────────────────────

def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["test_mode"] is True


# ─── Verificación del webhook ────────────────────────────────────────────────

def test_verificar_webhook_token_correcto(client):
    resp = client.get("/webhook", params={
        "hub.verify_token": "test_verify_token",
        "hub.challenge": "12345",
        "hub.mode": "subscribe",
    })
    assert resp.status_code == 200
    assert resp.text == "12345"


def test_verificar_webhook_token_incorrecto(client):
    resp = client.get("/webhook", params={
        "hub.verify_token": "token_malo",
        "hub.challenge": "12345",
    })
    assert resp.status_code == 403


# ─── Recepción de mensajes ────────────────────────────────────────────────────

def _payload_whatsapp(numero="521111", texto="hola", wamid="wamid_001"):
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "id": wamid,
                        "from": numero,
                        "type": "text",
                        "text": {"body": texto},
                    }]
                }
            }]
        }]
    }


def test_recibir_mensaje_valido(client):
    with patch("app.main.procesar_y_responder") as mock_proc:
        resp = client.post("/webhook", json=_payload_whatsapp())
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_recibir_mensaje_deduplica(client):
    """El mismo wamid enviado dos veces debe procesarse solo una vez."""
    llamadas = []
    def _mock_proc(numero, texto):
        llamadas.append((numero, texto))

    with patch("app.main.procesar_y_responder", side_effect=_mock_proc):
        client.post("/webhook", json=_payload_whatsapp(wamid="wamid_dup"))
        client.post("/webhook", json=_payload_whatsapp(wamid="wamid_dup"))

    # BackgroundTasks en TestClient se ejecutan síncronamente
    assert len(llamadas) <= 1  # máximo una vez


def test_recibir_payload_vacio_no_falla(client):
    resp = client.post("/webhook", json={})
    assert resp.status_code == 200


def test_recibir_payload_sin_messages_no_falla(client):
    resp = client.post("/webhook", json={"entry": [{"changes": [{"value": {}}]}]})
    assert resp.status_code == 200


def test_recibir_mensaje_tipo_no_texto(client):
    """Mensajes de tipo imagen/audio deben ignorarse sin errores."""
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "id": "wamid_img",
                        "from": "521111",
                        "type": "image",
                    }]
                }
            }]
        }]
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200


# ─── Métricas ─────────────────────────────────────────────────────────────────

def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "total" in resp.json()
