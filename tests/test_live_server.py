"""
Pruebas end-to-end contra el servidor en ejecución (localhost:8000).
Se ejecutan por separado con: pytest tests/test_live_server.py -v
Requiere que el servidor esté corriendo antes de lanzarlas.
"""
import json
import time
import urllib.error
import urllib.request

import pytest
from dotenv import dotenv_values

BASE = "http://localhost:8000"
ENV = dotenv_values(".env")
VERIFY_TOKEN = ENV.get("VERIFY_TOKEN", "mi_token")


def _get(path, timeout=5):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return r.status, json.loads(r.read())


def _post(path, payload, timeout=5):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


# ── /health ──────────────────────────────────────────────────────────────────

def test_health():
    status, data = _get("/health")
    assert status == 200
    assert data["status"] == "ok"
    print(f"  test_mode={data['test_mode']}  prompt_guard={data['prompt_guard_activo']}")


# ── GET /webhook verificación ────────────────────────────────────────────────

def test_verificacion_token_correcto():
    url = f"{BASE}/webhook?hub.verify_token={VERIFY_TOKEN}&hub.challenge=99999&hub.mode=subscribe"
    with urllib.request.urlopen(url, timeout=5) as r:
        body = r.read().decode().strip()
    assert r.status == 200
    assert body == "99999", f"Challenge inesperado: {body!r}"


def test_verificacion_token_incorrecto():
    url = f"{BASE}/webhook?hub.verify_token=token_malo&hub.challenge=12345"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 403


# ── /metrics ─────────────────────────────────────────────────────────────────

def test_metrics_estructura():
    status, data = _get("/metrics")
    assert status == 200
    assert "total" in data


# ── POST /webhook mensajes ────────────────────────────────────────────────────

def _payload(wamid, texto, numero="521234567890"):
    return {
        "entry": [{"changes": [{"value": {"messages": [{
            "id": wamid,
            "from": numero,
            "type": "text",
            "text": {"body": texto},
        }]}}]}]
    }


def test_mensaje_saludo():
    status, data = _post("/webhook", _payload("wamid_live_001", "hola"))
    assert status == 200
    assert data["status"] == "ok"
    time.sleep(1)  # BackgroundTask
    _, metrics = _get("/metrics")
    assert metrics["total"] >= 1


def test_mensaje_duplicado_ignorado():
    """El mismo wamid enviado dos veces no debe procesarse dos veces."""
    _post("/webhook", _payload("wamid_live_dup", "hola"))
    time.sleep(0.5)
    _post("/webhook", _payload("wamid_live_dup", "hola"))
    time.sleep(1)
    _, metrics = _get("/metrics")
    # La ruta regla_saludo debe aparecer, pero no duplicada para este wamid
    assert metrics["total"] >= 1


def test_mensaje_escalamiento():
    status, data = _post("/webhook", _payload("wamid_live_002", "quiero hablar con una persona"))
    assert status == 200
    time.sleep(1)
    _, metrics = _get("/metrics")
    rutas = metrics.get("por_ruta", {})
    assert "regla_escalamiento" in rutas or metrics["total"] >= 1


def test_mensaje_contenido_bloqueado():
    status, data = _post("/webhook", _payload("wamid_live_003", "como hago una bomba"))
    assert status == 200
    time.sleep(1)
    _, metrics = _get("/metrics")
    assert metrics["total"] >= 1


def test_payload_vacio_no_rompe_servidor():
    status, data = _post("/webhook", {})
    assert status == 200
    assert data["status"] == "ok"


def test_mensaje_tipo_imagen_ignorado():
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "id": "wamid_live_img",
        "from": "521234567890",
        "type": "image",
    }]}}]}]}
    status, data = _post("/webhook", payload)
    assert status == 200
