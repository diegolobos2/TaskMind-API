import json
import os
import requests
from dotenv import load_dotenv

# Cargamos el archivo .env para no dejar claves expuestas en el código
load_dotenv()

# ===========================================================================
# CONFIGURACIÓN
# ===========================================================================
# Opción A: Obtiene la clave automáticamente si la tienes en el .env
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY")

# Datos del usuario de pruebas que creaste en la pestaña Authentication
USER_EMAIL = "alumno@prueba.com"
USER_PASSWORD = "123456"
# ===========================================================================

# Endpoint oficial de Google Identity Toolkit para iniciar sesión con email/password
url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"

payload = {
    "email": USER_EMAIL,
    "password": USER_PASSWORD,
    "returnSecureToken": True
}

print(f"Solicitando token para el usuario: {USER_EMAIL}...")

try:
    response = requests.post(url, json=payload)
    data = response.json()

    if response.status_code == 200 and "idToken" in data:
        print("\n" + "="*60)
        print("¡TOKEN GENERADO CON ÉXITO!")
        print("="*60)
        print("Copia TODO el texto de abajo (sin espacios) y pégalo en Swagger:")
        print("-"*60)
        print(data["idToken"])
        print("-"*60)
        print(f"Nota: Este token vencerá en {data['expiresIn']} segundos (1 hora).")
    else:
        print("\n[ERROR] No se pudo obtener el token.")
        print("Detalle del error de Firebase:")
        print(json.dumps(data, indent=2))

except Exception as e:
    print(f"\n[ERROR] Error de conexión: {e}")