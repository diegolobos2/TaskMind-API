## Descripción

Este Pull Request introduce la estructura base modular del backend **TaskMind-API**, implementando el
esqueleto asíncrono completo con FastAPI, la conexión a Firebase Firestore y el endpoint de creación
de tareas con integración preparada para Google Gemini.

---

## Historias de Usuario relacionadas

### HU-01 — Creación de Tareas con Priorización por IA

> **Como** usuario autenticado, **quiero** crear una tarea enviando título y descripción,
> **para** que el sistema utilice Gemini y me asigne automáticamente un nivel de prioridad.

**Criterios de Aceptación implementados en este PR:**

```gherkin
Dado que el usuario está autenticado con un Firebase ID Token válido
  Y envía una petición POST a /api/v1/tasks con "title" y "description" no vacíos
Cuando el servidor recibe la petición
  Y valida el token contra Firebase Auth
  Y envía los datos a Gemini para determinar la prioridad
  Y Gemini devuelve "low", "medium" o "high"
  Y la tarea es persistida en Firestore con el campo "priority"
Entonces la API responde con HTTP 201 Created
  Y el cuerpo contiene el objeto con "id", "title", "description", "priority", "owner_uid" y "created_at"
```

```gherkin
Dado que el usuario envía datos inválidos (por ejemplo, "title" vacío)
Cuando Pydantic valida el esquema
Entonces la API responde con HTTP 422 Unprocessable Entity
  Y Gemini y Firestore no son invocados
```

```gherkin
Dado que Gemini no está disponible o retorna un error
Entonces la API responde con HTTP 503 Service Unavailable
  Y no se persiste ningún documento en Firestore
```

---

### HU-02 — Autenticación de Usuarios con Firebase Auth

> **Como** usuario, **quiero** que mis peticiones sean verificadas mediante Firebase,
> **para** que solo yo pueda acceder y gestionar mis propios datos.

**Criterios de Aceptación implementados en este PR:**

```gherkin
Dado que el usuario incluye un Firebase ID Token válido en "Authorization: Bearer <token>"
Cuando el middleware verifica el token con Firebase Admin SDK de forma asíncrona
Entonces el servidor permite el acceso y propaga el "uid" al contexto de la petición
```

```gherkin
Dado que el token está expirado o es inválido / está ausente
Entonces la API responde con HTTP 401 Unauthorized
  Y no se expone información interna sobre el motivo del rechazo
  Y Gemini y Firestore no son invocados
```

---

## Cambios incluidos

| Archivo                        | Descripción                                                              |
|-------------------------------|--------------------------------------------------------------------------|
| `requirements.txt`            | Dependencias del proyecto: fastapi, uvicorn, python-dotenv, firebase-admin, google-genai |
| `main.py`                     | Punto de entrada FastAPI con `load_dotenv()` y lifespan para init Firebase |
| `app/database/firebase.py`    | Conexión asíncrona a Firestore usando `GOOGLE_APPLICATION_CREDENTIALS`   |
| `app/routers/tasks.py`        | Endpoint `POST /api/v1/tasks` con autenticación, Gemini y persistencia   |
| `.gitignore`                  | Exclusión de `.env`, `firebase-credentials.json` y artefactos locales    |

---

## Checklist

- [x] Todo el código I/O es estrictamente asíncrono (`async/await` + `asyncio.to_thread`)
- [x] Arquitectura modular respetando principios de Arquitectura Limpia
- [x] Variables de entorno leídas desde `.env` (nunca hardcodeadas)
- [x] `.env` y `firebase-credentials.json` excluidos del control de versiones
- [x] Mensajes de error de autenticación genéricos (sin exponer detalles internos — OWASP)
- [x] Commit en formato Conventional Commits

---

## Cómo probar

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Arrancar el servidor (carga .env automáticamente)
uvicorn main:app --reload

# 3. Abrir Swagger UI
http://127.0.0.1:8000/docs
```
