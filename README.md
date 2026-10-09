# Library Agent Local

Agente conversacional de biblioteca para WhatsApp, construido con FastAPI, Llama Stack, Ollama y sentence-transformers. Basado en el Proyecto Integrador del curso Meta.

---

## Tabla de contenidos

- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Instalación en Windows](#instalación-en-windows)
- [Configuración del archivo .env](#configuración-del-archivo-env)
- [Modelos y servicios necesarios](#modelos-y-servicios-necesarios)
- [Modo de pruebas local](#modo-de-pruebas-local)
- [Ejecución del servidor](#ejecución-del-servidor)
- [WhatsApp Cloud API](#whatsapp-cloud-api)
- [Túnel ngrok](#túnel-ngrok)
- [Comandos de test](#comandos-de-test)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Solución de problemas](#solución-de-problemas)

---

## Arquitectura

```
library-agent-local/
├── app/
│   ├── main.py          # FastAPI + endpoints del webhook
│   ├── config.py        # Variables de entorno y validación
│   ├── agent.py         # Orquestación del flujo completo
│   ├── memory.py        # Conversación por número, locks de concurrencia
│   ├── knowledge.py     # RAG: embeddings del reglamento de biblioteca
│   ├── tools.py         # Herramientas de function calling (catálogo de libros)
│   ├── guardrails.py    # Llama Guard y Prompt Guard
│   ├── whatsapp.py      # Envío de mensajes via Meta Graph API
│   └── monitoring.py    # Métricas, bloqueos y registro de errores
├── tests/               # Suite de pruebas pytest (74 tests)
├── notebooks/           # Notebook original (no modificado)
├── .env.example         # Plantilla de variables de entorno
├── .gitignore
├── requirements.txt
└── README.md
```

### Flujo de cada mensaje entrante

```
WhatsApp → POST /webhook
    │
    ├─ 1. Prompt Guard (inyección de prompt) ──→ bloquear
    ├─ 2. Llama Guard entrada (contenido) ─────→ bloquear
    ├─ 3. Reglas fijas (saludo / escalamiento) → responder directo
    ├─ 4. Llama Stack + function calling ──────→ consultar_libro / buscar_en_reglamento
    └─ 5. Llama Guard salida (respuesta) ──────→ bloquear o enviar
```

---

## Requisitos

| Componente | Versión mínima | Notas |
|---|---|---|
| Python | 3.11 | Recomendado 3.11 o 3.12 |
| Ollama | última | Descarga los modelos localmente |
| Llama Stack | 0.2.x | Servidor local en puerto 8321 |
| RAM | 16 GB | 8 GB mínimo con solo llama3.1:8b |
| GPU (opcional) | — | Sin GPU el tiempo de respuesta es de varios segundos |

Servicios externos opcionales (solo para integración real con WhatsApp):
- Cuenta de Meta for Developers con WhatsApp Business API configurada
- ngrok (para exponer el webhook durante desarrollo)
- Cuenta de Hugging Face con acceso a `meta-llama/Llama-Prompt-Guard-2-86M` (para Prompt Guard)

---

## Instalación en Windows

### 1. Clonar o descargar el repositorio

```bash
git clone <url-del-repo>
cd library-agent-local
```

### 2. Crear y activar el entorno virtual

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalar dependencias

```cmd
pip install -r requirements.txt
```

> **Nota sobre torch y transformers:** Solo son necesarios para Prompt Guard. Si no vas a usar Prompt Guard (requiere cuenta HF con acceso al modelo), puedes omitirlos. El agente funciona perfectamente con Llama Guard solo.

Para instalar sin Prompt Guard:

```cmd
pip install fastapi uvicorn httpx requests python-dotenv numpy sentence-transformers llama-stack-client ollama pytest pytest-asyncio
```

---

## Configuración del archivo .env

```cmd
copy .env.example .env
```

Abre `.env` y configura las variables según tu entorno:

```env
# Token de verificación del webhook (elige cualquier cadena secreta)
VERIFY_TOKEN=mi_token_secreto

# WhatsApp Cloud API (obtener en Meta for Developers)
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxxx...
PHONE_NUMBER_ID=123456789
WABA_TOKEN_ID=987654321

# Llama Stack (levantado localmente)
LLAMA_STACK_URL=http://localhost:8321
LLAMA_MODEL=ollama/llama3.1:8b

# Ollama
OLLAMA_URL=http://localhost:11434

# Hugging Face (solo si usas Prompt Guard)
HF_TOKEN=hf_xxxxxxxx

# Modo de pruebas (sin servicios externos)
TEST_MODE=false
```

---

## Modelos y servicios necesarios

### Ollama + modelos LLM

Instala Ollama desde [https://ollama.com](https://ollama.com).

```cmd
# Descargar el modelo conversacional (~4.7 GB)
ollama pull llama3.1:8b

# Descargar Llama Guard (~2.5 GB)
ollama pull llama-guard3
```

Ollama levanta automáticamente su servidor en `http://localhost:11434`.

### Llama Stack

```cmd
pip install "llama-stack[starter]"
```

Registrar el modelo y levantar el servidor:

```cmd
set OLLAMA_URL=http://localhost:11434/v1
llama stack run --port 8321
```

Si necesitas registrar el modelo manualmente en la configuración de Llama Stack, edita el archivo `config.yaml` de la distribución `starter` y añade `llama3.1:8b` en `registered_resources.models` (ver notebook original para referencia exacta).

### sentence-transformers (embeddings RAG)

El modelo `paraphrase-multilingual-MiniLM-L12-v2` (~120 MB) se descarga automáticamente la primera vez que el servidor arranca. No requiere cuenta de Hugging Face.

### Prompt Guard (opcional)

Requiere:
1. Aceptar la licencia de `meta-llama/Llama-Prompt-Guard-2-86M` en [huggingface.co](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M)
2. Generar un token de acceso en Hugging Face → Settings → Access Tokens
3. Configurar `HF_TOKEN=hf_xxxxxxxx` en `.env`

Si Prompt Guard no está disponible, el agente lo indica en el log de arranque y continúa usando solo Llama Guard.

---

## Modo de pruebas local

Activa `TEST_MODE=true` en tu `.env` (o como variable de entorno). En este modo:

- No se conecta a Ollama ni Llama Stack
- No llama a la API de WhatsApp
- Los embeddings RAG usan vectores aleatorios deterministas
- El LLM usa un stub local que responde basándose en palabras clave
- Llama Guard usa heurísticas simples (detecta palabras como "bomba", "veneno")

Útil para desarrollar y ejecutar los tests sin ningún servicio externo.

```cmd
set TEST_MODE=true
python -m uvicorn app.main:app --reload --port 8000
```

---

## Ejecución del servidor

### Modo desarrollo (con recarga automática)

```cmd
# Asegúrate de que Ollama y Llama Stack estén corriendo primero
.venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Modo producción

```cmd
python app/main.py
```

El servidor queda disponible en `http://localhost:8000`.

Endpoints disponibles:
- `GET  /health`  → Estado del servicio
- `GET  /metrics` → Resumen de métricas
- `GET  /webhook` → Verificación del webhook de Meta
- `POST /webhook` → Recepción de mensajes de WhatsApp

---

## WhatsApp Cloud API

### Configuración en Meta for Developers

1. Ve a [developers.facebook.com](https://developers.facebook.com) y crea una app de tipo **Business**.
2. Añade el producto **WhatsApp**.
3. En **WhatsApp > Configuración de la API**, anota el `Phone Number ID` y el `WhatsApp Business Account ID`.
4. Copia el **Access Token** temporal (válido 24 horas en desarrollo; en producción crea un usuario del sistema con token permanente).
5. En **WhatsApp > Configuración > Webhooks**, configura:
   - **Callback URL:** `https://<tu-dominio>/webhook`
   - **Verify Token:** el mismo valor que pusiste en `VERIFY_TOKEN`
   - Suscríbete al campo `messages`

### Token permanente para producción

El token temporal expira en 24 horas. Para producción:
1. En Meta Business Suite → Configuración → Usuarios del sistema → crear usuario del sistema
2. Asignarle la app y generar un token permanente con los permisos `whatsapp_business_messaging`

---

## Túnel ngrok

Necesario durante desarrollo para que Meta pueda enviar mensajes a tu máquina local.

```cmd
# Instalar ngrok desde https://ngrok.com/download
# O con pip:
pip install pyngrok

# Abrir túnel (con tu authtoken de ngrok.com)
ngrok authtoken <tu_authtoken>
ngrok http 8000
```

La URL que muestra ngrok (p. ej. `https://abc123.ngrok-free.app`) es la que configuras como Callback URL en Meta for Developers, agregando `/webhook` al final.

Cada vez que reinicies ngrok obtendrás una URL distinta y tendrás que actualizarla en el dashboard de Meta.

---

## Comandos de test

```cmd
# Activar entorno virtual primero
.venv\Scripts\activate

# Ejecutar todos los tests
pytest tests/ -v

# Solo un módulo
pytest tests/test_agent.py -v

# Con cobertura (requiere pytest-cov)
pip install pytest-cov
pytest tests/ --cov=app --cov-report=term-missing
```

Los tests no requieren ningún servicio externo (usan `TEST_MODE=true` automáticamente vía `conftest.py`).

**Resultado actual: 74/74 tests pasan.**

---

## Limitaciones conocidas

| Componente | Estado | Notas |
|---|---|---|
| Llama Stack `responses` API | Requiere Llama Stack ≥0.2 | La API de conversaciones puede cambiar entre versiones |
| Prompt Guard | Opcional | Requiere HF_TOKEN y aceptar licencia en HF |
| Escalamiento humano | Mensaje informativo únicamente | No existe integración real con CRM o sistema de tickets |
| Estado en memoria | Se pierde al reiniciar | En producción usar Redis o base de datos para `conversaciones_por_numero` e `ids_procesados` |
| Catálogo de libros | Dict estático | En producción conectar a base de datos real |
| Llama Guard en TEST_MODE | Heurísticas simples | Solo detecta palabras clave predefinidas |
| Tipos de mensaje WhatsApp | Solo texto | Imágenes, audio y otros tipos se ignoran |

---

## Solución de problemas

**`ModuleNotFoundError: No module named 'llama_stack_client'`**
```cmd
pip install llama-stack-client
```

**`ConnectionRefusedError` al conectar a Llama Stack**
- Verifica que Ollama esté corriendo: `ollama list`
- Verifica que Llama Stack esté corriendo en el puerto 8321
- Revisa `LLAMA_STACK_URL` en tu `.env`

**`ollama pull llama-guard3` falla o el modelo no se encuentra**
- Prueba: `ollama pull llama-guard3:latest`
- Verifica la lista de modelos disponibles en [ollama.com/library](https://ollama.com/library)

**Las respuestas del agente tardan mucho (>30 s)**
- Normal sin GPU. `llama3.1:8b` en CPU puede tardar 15-60 s por respuesta.
- Aumenta `LLAMA_STACK_TIMEOUT` en `.env` si ves errores de timeout.
- Para desarrollo con TEST_MODE las respuestas son instantáneas.

**Error 401 de WhatsApp API**
- El token temporal de 24 horas expiró. Genera uno nuevo en Meta for Developers.
- Actualiza `WHATSAPP_ACCESS_TOKEN` en `.env` y reinicia el servidor.

**`EnvironmentError: Variable de entorno requerida 'X' no está configurada`**
- El archivo `.env` no se cargó o falta la variable indicada.
- Verifica que `.env` esté en la raíz del proyecto (mismo nivel que `requirements.txt`).

**Pytest falla con `ModuleNotFoundError: No module named 'app'`**
- Ejecuta pytest desde la raíz del proyecto, no desde dentro de `app/` o `tests/`.
- Asegúrate de que el entorno virtual esté activado.
