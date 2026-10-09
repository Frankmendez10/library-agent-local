"""
Herramientas de function calling del agente.

- consultar_libro: consulta el catálogo de disponibilidad de libros.
  El catálogo es un dict estático (suficiente para demo/pruebas);
  en producción se reemplazaría por una consulta a base de datos real.
- Las entradas se validan antes de usarse; nunca se permite SQL arbitrario.
"""
import unicodedata
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Catálogo de libros ───────────────────────────────────────────────────────
# Clave: título normalizado (sin acentos, minúsculas).
# Valor: datos del libro.
CATALOGO: dict[str, dict] = {
    "cien anos de soledad": {
        "titulo": "Cien años de soledad",
        "autor": "Gabriel García Márquez",
        "disponibles": 2,
        "devolucion": None,
    },
    "el principito": {
        "titulo": "El principito",
        "autor": "Antoine de Saint-Exupéry",
        "disponibles": 0,
        "devolucion": "2026-10-09",
    },
    "pedro paramo": {
        "titulo": "Pedro Páramo",
        "autor": "Juan Rulfo",
        "disponibles": 1,
        "devolucion": None,
    },
    "el laberinto de la soledad": {
        "titulo": "El laberinto de la soledad",
        "autor": "Octavio Paz",
        "disponibles": 3,
        "devolucion": None,
    },
}


def _quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _normalizar_titulo(titulo: str) -> str:
    """Normaliza un título para búsqueda: minúsculas, sin acentos, sin puntuación extrema."""
    normalizado = _quitar_acentos(titulo.lower()).strip(" ¿?¡!.\"'")
    # Truncar a 200 chars para evitar entradas abusivas
    return normalizado[:200]


def consultar_libro(titulo: Optional[str] = None) -> str:
    """
    Consulta la disponibilidad de un libro en el catálogo.

    - Si no se proporciona título, pide al usuario que lo especifique.
    - Busca por coincidencia parcial (subcadena) entre la clave normalizada
      y el título normalizado de la consulta.
    - Nunca genera SQL ni accede a sistemas externos; usa solo el dict local.
    """
    # Validación de tipo primero, luego vacío
    if not isinstance(titulo, str):
        return "¿Qué título estás buscando? Dime el nombre del libro para revisar su disponibilidad."

    if not titulo.strip():
        return "¿Qué título estás buscando? Dime el nombre del libro para revisar su disponibilidad."

    titulo_norm = _normalizar_titulo(titulo)

    for clave, libro in CATALOGO.items():
        if clave in titulo_norm or titulo_norm in clave:
            if libro["disponibles"] > 0:
                return (
                    f"«{libro['titulo']}» de {libro['autor']}: "
                    f"hay {libro['disponibles']} ejemplar(es) disponible(s)."
                )
            return (
                f"«{libro['titulo']}» de {libro['autor']}: "
                f"no hay ejemplares disponibles; el próximo regresa el {libro['devolucion']}."
            )

    logger.debug("Libro no encontrado en catálogo: %r", titulo)
    return f"No encontramos «{titulo}» en el catálogo."


# ─── Descripción de la herramienta para Llama Stack ─────────────────────────
HERRAMIENTA_LIBRO: dict = {
    "type": "function",
    "name": "consultar_libro",
    "description": (
        "Consulta en el catálogo si un libro está disponible para préstamo. "
        "Si el usuario no dio un título, omite el parámetro."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "titulo": {
                "type": "string",
                "description": "Título del libro a consultar. Omite este parámetro si el usuario no dio un título.",
            }
        },
        "required": [],
    },
}

# Mapa nombre → función (usado por el agente para ejecutar llamadas)
FUNCIONES_DISPONIBLES: dict = {
    "consultar_libro": consultar_libro,
}
