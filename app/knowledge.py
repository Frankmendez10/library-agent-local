"""
Base de conocimiento RAG del reglamento de la biblioteca.

- Fragmentos del reglamento definidos como constante (fácil de ampliar).
- Embeddings calculados con sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2).
- En TEST_MODE, encode() devuelve vectores aleatorios unitarios para no
  requerir la descarga del modelo.
- Búsqueda por similitud coseno (dot product sobre embeddings normalizados).
"""
import logging
import unicodedata
from typing import Optional

import numpy as np

from app import config

logger = logging.getLogger(__name__)

# ─── Fragmentos del reglamento ───────────────────────────────────────────────
DOCUMENTOS: list[str] = [
    "Horario: la biblioteca abre de lunes a viernes de 8:00 a 20:00 y los sábados "
    "de 9:00 a 14:00. Los domingos y días festivos permanece cerrada.",
    "Credencial: para solicitar libros en préstamo se requiere credencial vigente "
    "de la biblioteca. Se tramita sin costo en mostrador con una identificación oficial.",
    "Préstamo a domicilio: cada persona puede llevarse hasta 3 libros por 7 días naturales.",
    "Renovaciones: un préstamo se puede renovar hasta 2 veces por 7 días más, siempre "
    "que nadie tenga el libro reservado. La renovación se solicita en mostrador o en línea.",
    "Multas: el retraso en la devolución genera una multa de $10 por libro por cada día "
    "de retraso. Con multas pendientes no se pueden solicitar nuevos préstamos.",
    "Libros dañados o perdidos: la persona debe reponer un ejemplar igual o pagar el valor "
    "del libro más un cargo administrativo de $100.",
    "Consulta en sala: las obras de consulta, como enciclopedias, diccionarios y tesis, "
    "no salen de la biblioteca y solo se pueden usar en sala.",
    "Salas de estudio: se pueden reservar hasta 2 horas al día para grupos de 3 a 6 "
    "personas, con al menos 24 horas de anticipación.",
    "Equipos de cómputo: el uso es de 1 hora por persona, ampliable si no hay personas "
    "en espera.",
    "Convivencia: en las salas se debe guardar silencio. No se permite consumir alimentos; "
    "las bebidas solo se permiten con tapa.",
]

# ─── Inicialización del modelo de embeddings ─────────────────────────────────
_modelo_embeddings = None
_embeddings_documentos: Optional[np.ndarray] = None


def _quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _get_modelo():
    global _modelo_embeddings
    if _modelo_embeddings is None:
        if config.TEST_MODE:
            _modelo_embeddings = _ModeloStub()
            logger.debug("TEST_MODE: usando modelo de embeddings stub")
        else:
            from sentence_transformers import SentenceTransformer
            _modelo_embeddings = SentenceTransformer(config.EMBEDDING_MODEL)
            logger.info("Modelo de embeddings cargado: %s", config.EMBEDDING_MODEL)
    return _modelo_embeddings


class _ModeloStub:
    """Stub del modelo para TEST_MODE: devuelve vectores unitarios aleatorios reproducibles."""

    def encode(self, textos: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        rng = np.random.default_rng(seed=42)
        vecs = rng.random((len(textos), 384)).astype(np.float32)
        if normalize_embeddings:
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            vecs = vecs / np.maximum(norms, 1e-9)
        return vecs


def _get_embeddings() -> np.ndarray:
    global _embeddings_documentos
    if _embeddings_documentos is None:
        modelo = _get_modelo()
        _embeddings_documentos = modelo.encode(DOCUMENTOS, normalize_embeddings=True)
        logger.debug("Embeddings calculados: shape=%s", _embeddings_documentos.shape)
    return _embeddings_documentos


def similitudes(pregunta: str) -> np.ndarray:
    """Retorna vector de similitudes coseno entre `pregunta` y cada fragmento."""
    modelo = _get_modelo()
    emb_pregunta = modelo.encode([pregunta], normalize_embeddings=True)
    embs = _get_embeddings()
    return np.dot(embs, emb_pregunta.T).flatten()


def buscar_en_reglamento(pregunta: str, k: int = 2) -> str:
    """
    Busca los fragmentos más relevantes del reglamento para `pregunta`.
    Retorna un string con los fragmentos encontrados o un mensaje indicando
    que el reglamento no cubre esa pregunta.

    Esta función es la herramienta de function calling expuesta al LLM.
    El parámetro `pregunta` es validado antes de usarse.
    """
    if not isinstance(pregunta, str) or not pregunta.strip():
        return "El reglamento no cubre esa pregunta; un miembro del equipo puede confirmarte directamente."

    # Sanitización básica: truncar a 500 chars para no enviar entradas enormes al modelo
    pregunta = pregunta.strip()[:500]

    sims = similitudes(pregunta)
    indices = np.argsort(sims)[::-1][:k]
    relevantes = [i for i in indices if sims[i] >= config.RAG_THRESHOLD]

    if not relevantes:
        return "El reglamento no cubre esa pregunta; un miembro del equipo puede confirmarte directamente."

    fragmentos = " | ".join(DOCUMENTOS[i] for i in relevantes)
    return f"Fragmentos del reglamento: {fragmentos}"


# ─── Definición de la herramienta para Llama Stack ───────────────────────────
HERRAMIENTA_REGLAMENTO: dict = {
    "type": "function",
    "name": "buscar_en_reglamento",
    "description": (
        "Busca en el reglamento de la biblioteca la respuesta a dudas sobre "
        "horarios, credencial, préstamos, renovaciones, multas, salas de estudio "
        "y equipos de cómputo."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pregunta": {
                "type": "string",
                "description": "La pregunta del usuario sobre el reglamento, en texto libre.",
            }
        },
        "required": ["pregunta"],
    },
}


def reiniciar_cache() -> None:
    """Limpia el caché de embeddings (útil para tests)."""
    global _modelo_embeddings, _embeddings_documentos
    _modelo_embeddings = None
    _embeddings_documentos = None
