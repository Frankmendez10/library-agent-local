"""
Núcleo del agente: orquestación del flujo completo.

Flujo de cada mensaje:
  1. Seguridad sobre la entrada (Prompt Guard → Llama Guard)
  2. Reglas fijas (escalamiento humano, saludo)
  3. Llama Stack con function calling (consultar_libro / buscar_en_reglamento)
  4. Seguridad sobre la salida (Llama Guard)
  5. Envío de respuesta vía WhatsApp

En TEST_MODE, el LLM es reemplazado por un stub que responde usando las
herramientas directamente sin llamar a Llama Stack.
"""
import json
import logging
import time
import threading
from typing import Optional

from app import config
from app import guardrails
from app import monitoring
from app import memory
from app import whatsapp
from app.knowledge import buscar_en_reglamento, HERRAMIENTA_REGLAMENTO
from app.tools import consultar_libro, HERRAMIENTA_LIBRO, FUNCIONES_DISPONIBLES

logger = logging.getLogger(__name__)

# ─── Constantes de comportamiento ────────────────────────────────────────────
SYSTEM_PROMPT = (
    "Eres el asistente de la biblioteca. "
    "Responde de forma breve (2-3 líneas). "
    "Solo usa una herramienta cuando el usuario pregunte algo específico que la herramienta pueda responder "
    "(la disponibilidad de un libro, o una duda sobre el reglamento). No uses ninguna herramienta para "
    "confirmaciones o respuestas cortas del usuario (como 'sí, por favor' o 'gracias'). "
    "No puedes reservar, renovar ni prestar libros de ninguna forma — solo puedes consultar disponibilidad "
    "y explicar el reglamento. Si el usuario quiere reservar, renovar o pedir un libro, dile que acuda a mostrador "
    "o que un miembro del equipo se pondrá en contacto. "
    "Para dudas del reglamento responde únicamente con lo que diga el fragmento que regrese la herramienta. "
    "Si una herramienta no encuentra una respuesta, dilo honestamente en vez de inventar un dato. "
    "Si una herramienta SÍ regresa un resultado real, siempre comunícalo claramente al usuario; nunca lo ignores. "
    "Responde siempre de forma directa con la información final, basándote únicamente en el resultado real de las "
    "herramientas; nunca inventes datos que no vengan de una herramienta. "
    "Nunca describas tu proceso, ni menciones nombres de funciones, parámetros o claves de un resultado."
)

FRASES_ESCALAMIENTO = [
    "hablar con alguien",
    "hablar con una persona",
    "agente humano",
    "asistente humano",
    "quiero hablar con alguien",
]

FRASES_SALUDO = [
    "hola",
    "buenas",
    "buenos dias",
    "buenos días",
    "buenas tardes",
    "buenas noches",
    "que tal",
    "buen dia",
    "buen día",
]

HERRAMIENTAS = [HERRAMIENTA_LIBRO, HERRAMIENTA_REGLAMENTO]
_TODAS_FUNCIONES = {
    **FUNCIONES_DISPONIBLES,
    "buscar_en_reglamento": buscar_en_reglamento,
}

# ─── Cliente Llama Stack (singleton) ─────────────────────────────────────────
_client = None
_client_lock = threading.Lock()


def get_client():
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            if config.TEST_MODE:
                _client = _ClienteStub()
                logger.debug("TEST_MODE: usando cliente LLM stub")
            else:
                from llama_stack_client import LlamaStackClient

                _client = LlamaStackClient(
                    base_url=config.LLAMA_STACK_URL,
                    timeout=config.LLAMA_STACK_TIMEOUT,
                )
                logger.info("LlamaStackClient conectado a %s", config.LLAMA_STACK_URL)
    return _client


# ─── Stub del LLM para TEST_MODE ─────────────────────────────────────────────
class _RespuestaStub:
    """Simula respuesta de client.responses.create()."""

    def __init__(self, texto: str):
        self.output_text = texto
        self.output = []  # sin function calls


class _ConversacionStub:
    def __init__(self):
        self.id = f"stub-conv-{id(self)}"


class _ConversacionesStub:
    def create(self):
        return _ConversacionStub()


class _ResponsesStub:
    def create(self, model, input, conversation=None, instructions=None, tools=None):
        # En TEST_MODE intentamos llamar a las herramientas directamente si detectamos
        # palabras clave, para que los tests de function calling tengan cobertura básica.
        if isinstance(input, str):
            texto = input.lower()
            if any(kw in texto for kw in ["libro", "principito", "paramo", "soledad", "rulfo"]):
                # Extraer posible título
                resultado = consultar_libro(input)
                return _RespuestaStub(resultado)
            if any(kw in texto for kw in ["reglamento", "horario", "préstamo", "multa", "credencial", "sala"]):
                resultado = buscar_en_reglamento(input)
                return _RespuestaStub(resultado)
        return _RespuestaStub(
            "Hola, soy el asistente de la biblioteca. ¿En qué puedo ayudarte? "
            "[TEST_MODE: LLM simulado]"
        )


class _ClienteStub:
    def __init__(self):
        self.conversations = _ConversacionesStub()
        self.responses = _ResponsesStub()


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _es_solo_saludo(texto_low: str) -> bool:
    texto_limpio = texto_low.strip(" ,.!¡¿?")
    return texto_limpio in FRASES_SALUDO


# ─── Generación de respuesta con memoria y function calling ──────────────────
def generar_respuesta(numero: str, texto_usuario: str) -> str:
    """
    Llama a Llama Stack con el historial de conversación del número
    y ejecuta las function calls que el modelo solicite.
    """
    client = get_client()
    conversation_id = memory.obtener_conversacion(numero, client)

    respuesta = client.responses.create(
        model=config.LLAMA_MODEL,
        input=texto_usuario,
        conversation=conversation_id,
        instructions=SYSTEM_PROMPT,
        tools=HERRAMIENTAS,
    )

    # Ejecutar function calls si el modelo las solicitó
    llamadas_funcion = [
        item for item in respuesta.output if item.type == "function_call"
    ]
    if llamadas_funcion:
        resultados = []
        for llamada in llamadas_funcion:
            if llamada.name not in _TODAS_FUNCIONES:
                raise KeyError(llamada.name)
            funcion = _TODAS_FUNCIONES[llamada.name]
            argumentos = json.loads(llamada.arguments)
            resultado = funcion(**argumentos)
            resultados.append(
                {
                    "type": "function_call_output",
                    "call_id": llamada.call_id,
                    "output": resultado,
                }
            )
        respuesta = client.responses.create(
            model=config.LLAMA_MODEL,
            input=resultados,
            conversation=conversation_id,
            instructions=SYSTEM_PROMPT,
            tools=HERRAMIENTAS,
        )

    return respuesta.output_text


# ─── Flujo de decisión (seguridad + reglas + LLM) ────────────────────────────
def decidir_y_responder(numero: str, texto: str) -> str:
    """
    Procesa un mensaje entrante siguiendo el flujo:
      1. Prompt Guard (inyección)
      2. Llama Guard (contenido de entrada)
      3. Reglas fijas (escalamiento / saludo)
      4. LLM con herramientas
      5. Llama Guard (contenido de salida)

    Retorna la ruta tomada: 'llama', 'regla_saludo', 'regla_escalamiento',
    'bloqueado_prompt_guard', 'bloqueado_llama_guard_entrada',
    'bloqueado_llama_guard_salida'.
    """
    texto_low = texto.lower()

    # 1. Prompt Guard
    if guardrails.es_inyeccion(texto):
        monitoring.registrar_bloqueo(numero, texto, "prompt_guard", "inyección de prompt")
        whatsapp.enviar_respuesta(numero, guardrails.MENSAJE_BLOQUEO)
        return "bloqueado_prompt_guard"

    # 2. Llama Guard (entrada)
    seguro, categoria = guardrails.revisar_con_llama_guard(
        [{"role": "user", "content": texto}]
    )
    if not seguro:
        monitoring.registrar_bloqueo(numero, texto, "llama_guard_entrada", categoria)
        whatsapp.enviar_respuesta(numero, guardrails.MENSAJE_BLOQUEO)
        return "bloqueado_llama_guard_entrada"

    # 3. Reglas fijas
    if any(frase in texto_low for frase in FRASES_ESCALAMIENTO):
        # NOTA: este mensaje informa al usuario que será contactado.
        # No existe integración real con un sistema de tickets o notificaciones.
        # En producción se debería conectar al sistema CRM correspondiente.
        whatsapp.enviar_respuesta(
            numero,
            "Claro, en un momento un miembro del equipo te contacta directamente.",
        )
        return "regla_escalamiento"

    if _es_solo_saludo(texto_low):
        whatsapp.enviar_respuesta(
            numero,
            "Hola, soy el asistente de la biblioteca. ¿En qué puedo ayudarte?",
        )
        return "regla_saludo"

    # 4. LLM con herramientas
    respuesta = generar_respuesta(numero, texto)

    # 5. Llama Guard (salida)
    seguro, categoria = guardrails.revisar_con_llama_guard(
        [
            {"role": "user", "content": texto},
            {"role": "assistant", "content": respuesta},
        ]
    )
    if not seguro:
        monitoring.registrar_bloqueo(numero, respuesta, "llama_guard_salida", categoria)
        whatsapp.enviar_respuesta(numero, guardrails.MENSAJE_RESPUESTA_BLOQUEADA)
        return "bloqueado_llama_guard_salida"

    whatsapp.enviar_respuesta(numero, respuesta)
    return "llama"


# ─── Función principal de procesamiento (con lock por número y métricas) ─────
def procesar_y_responder(numero: str, texto: str) -> None:
    """
    Punto de entrada para procesar un mensaje.
    Serializa mensajes del mismo número con un Lock individual.
    Registra métricas y errores clasificados.
    """
    from app.whatsapp import enviar_respuesta as _enviar

    def _aviso_error():
        try:
            _enviar(
                numero,
                "Estamos teniendo un problema técnico. Intenta de nuevo en un momento.",
            )
        except Exception:
            pass

    lock = memory.obtener_lock(numero)
    inicio = time.perf_counter()
    ruta = "error"

    with lock:
        try:
            ruta = decidir_y_responder(numero, texto)

        except Exception as exc:
            # Importar excepciones de Llama Stack solo si el módulo está disponible
            ruta = _clasificar_y_registrar_error(numero, texto, exc)
            _aviso_error()

        finally:
            monitoring.registrar_metrica(numero, ruta, time.perf_counter() - inicio)


def _clasificar_y_registrar_error(numero: str, texto: str, exc: Exception) -> str:
    """Clasifica la excepción, registra el error y retorna la causa como string."""
    # ── Llama Stack ──────────────────────────────────────────────────────────
    try:
        from llama_stack_client import APITimeoutError, APIConnectionError, APIStatusError

        if isinstance(exc, APITimeoutError):
            monitoring.registrar_error(
                numero, texto, "llama_timeout",
                "Llama Stack conectó pero la generación tardó demasiado.", exc
            )
            return "error"

        if isinstance(exc, APIConnectionError):
            monitoring.registrar_error(
                numero, texto, "llama_stack_caido",
                "No se pudo conectar a Llama Stack.", exc
            )
            return "error"

        if isinstance(exc, APIStatusError):
            monitoring.registrar_error(
                numero, texto, "llama_stack_error_http",
                f"Llama Stack respondió con error HTTP {exc.status_code}.", exc
            )
            return "error"
    except ImportError:
        pass

    # ── Ollama (Llama Guard) ─────────────────────────────────────────────────
    try:
        import ollama as _ollama
        if isinstance(exc, _ollama.ResponseError):
            monitoring.registrar_error(
                numero, texto, "llama_guard_no_disponible",
                "Falló la llamada a Ollama desde la capa de seguridad.", exc
            )
            return "error"
    except ImportError:
        pass

    # ── Conexión rechazada a Ollama (sin paquete instalado o servidor caído) ─
    if isinstance(exc, (ConnectionError, ConnectionRefusedError, OSError)):
        monitoring.registrar_error(
            numero, texto, "ollama_conexion_fallida",
            "No se pudo conectar a Ollama. Verifica que esté corriendo en el puerto configurado.", exc
        )
        return "error"

    # ── WhatsApp API ─────────────────────────────────────────────────────────
    import requests as _req
    if isinstance(exc, _req.exceptions.RequestException):
        monitoring.registrar_error(
            numero, texto, "whatsapp_api_error",
            "Falló el envío a la API de WhatsApp.", exc
        )
        return "error"

    # ── Herramienta desconocida ───────────────────────────────────────────────
    if isinstance(exc, KeyError):
        monitoring.registrar_error(
            numero, texto, "herramienta_no_reconocida",
            f"El modelo pidió una herramienta desconocida: {exc}.", exc
        )
        return "error"

    # ── Error no clasificado ──────────────────────────────────────────────────
    monitoring.registrar_error(
        numero, texto, "desconocido", "Error no clasificado.", exc
    )
    return "error"
