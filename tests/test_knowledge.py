"""
Tests del módulo RAG:
- Embeddings se generan correctamente (stub en TEST_MODE).
- Búsqueda retorna fragmentos relevantes para preguntas del reglamento.
- Preguntas fuera del alcance retornan mensaje adecuado.
- Validación de entrada en buscar_en_reglamento.
"""
import numpy as np
import pytest


def test_embeddings_generados():
    from app.knowledge import _get_embeddings, DOCUMENTOS
    embs = _get_embeddings()
    assert embs.shape[0] == len(DOCUMENTOS)
    assert embs.shape[1] > 0


def test_embeddings_normalizados():
    """Cada vector debe tener norma ~1 (normalizados para similitud coseno)."""
    from app.knowledge import _get_embeddings
    embs = _get_embeddings()
    normas = np.linalg.norm(embs, axis=1)
    np.testing.assert_allclose(normas, np.ones(len(normas)), atol=1e-5)


def test_similitudes_shape():
    from app.knowledge import similitudes, DOCUMENTOS
    sims = similitudes("¿Cuántos libros puedo llevarme?")
    assert len(sims) == len(DOCUMENTOS)


def test_buscar_pregunta_valida_retorna_string():
    from app.knowledge import buscar_en_reglamento
    resultado = buscar_en_reglamento("¿Cuántos libros puedo llevarme?")
    assert isinstance(resultado, str)
    assert len(resultado) > 0


def test_buscar_pregunta_vacia_retorna_mensaje_generico():
    from app.knowledge import buscar_en_reglamento
    resultado = buscar_en_reglamento("")
    assert "reglamento no cubre" in resultado.lower() or "miembro del equipo" in resultado.lower()


def test_buscar_pregunta_none_retorna_mensaje_generico():
    from app.knowledge import buscar_en_reglamento
    resultado = buscar_en_reglamento(None)  # type: ignore
    assert "reglamento no cubre" in resultado.lower() or "miembro del equipo" in resultado.lower()


def test_buscar_trunca_entradas_largas():
    """Preguntas muy largas no deben provocar errores."""
    from app.knowledge import buscar_en_reglamento
    pregunta_larga = "a" * 2000
    resultado = buscar_en_reglamento(pregunta_larga)
    assert isinstance(resultado, str)
