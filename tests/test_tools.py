"""
Tests de herramientas (function calling):
- consultar_libro con título existente disponible.
- consultar_libro con libro no disponible.
- consultar_libro con libro desconocido.
- consultar_libro sin título.
- Validación de entradas (tipo incorrecto, string vacío).
- Normalización de acentos y mayúsculas.
"""
import pytest


def test_libro_disponible():
    from app.tools import consultar_libro
    resultado = consultar_libro("Cien años de soledad")
    assert "disponible" in resultado.lower()
    assert "García Márquez" in resultado or "garcia marquez" in resultado.lower()


def test_libro_no_disponible():
    from app.tools import consultar_libro
    resultado = consultar_libro("El principito")
    assert "no hay ejemplares" in resultado.lower()
    assert "2026" in resultado  # fecha de devolución


def test_libro_desconocido():
    from app.tools import consultar_libro
    resultado = consultar_libro("Rayuela")
    assert "no encontramos" in resultado.lower() or "catálogo" in resultado.lower()


def test_libro_sin_titulo():
    from app.tools import consultar_libro
    resultado = consultar_libro()
    assert "título" in resultado.lower() or "titulo" in resultado.lower()


def test_libro_sin_titulo_none():
    from app.tools import consultar_libro
    resultado = consultar_libro(None)
    assert "título" in resultado.lower() or "titulo" in resultado.lower()


def test_libro_string_vacio():
    from app.tools import consultar_libro
    resultado = consultar_libro("")
    assert "título" in resultado.lower() or "titulo" in resultado.lower()


def test_libro_normalizacion_acentos():
    from app.tools import consultar_libro
    resultado = consultar_libro("pedro paramo")
    assert "Pedro Páramo" in resultado
    assert "Rulfo" in resultado


def test_libro_normalizacion_mayusculas():
    from app.tools import consultar_libro
    resultado = consultar_libro("PEDRO PARAMO")
    assert "Pedro Páramo" in resultado


def test_libro_tipo_invalido():
    from app.tools import consultar_libro
    resultado = consultar_libro(12345)  # type: ignore
    # No debe lanzar excepción
    assert isinstance(resultado, str)


def test_herramienta_definicion_correcta():
    """La definición de la herramienta debe tener los campos requeridos por Llama Stack."""
    from app.tools import HERRAMIENTA_LIBRO
    assert HERRAMIENTA_LIBRO["type"] == "function"
    assert HERRAMIENTA_LIBRO["name"] == "consultar_libro"
    assert "parameters" in HERRAMIENTA_LIBRO
    assert "descripci" in HERRAMIENTA_LIBRO["description"].lower() or len(HERRAMIENTA_LIBRO["description"]) > 0


def test_funciones_disponibles_contiene_consultar_libro():
    from app.tools import FUNCIONES_DISPONIBLES
    assert "consultar_libro" in FUNCIONES_DISPONIBLES
    assert callable(FUNCIONES_DISPONIBLES["consultar_libro"])
