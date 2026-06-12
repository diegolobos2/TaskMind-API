# Instrucciones del Proyecto: TaskMind-API
- Adoptar estrictamente la estrategia de ramificación GitHub Flow (main es
sagrado, se trabaja en ramas cortas).
- Estructurar el backend de forma modular adoptando principios de Arquitectura
Limpia.
- Frameworks obligatorios: FastAPI para la API, Firebase Admin SDK para la
persistencia y Google GenAI SDK para la IA.
- Regla de oro de rendimiento: Todo el código de entrada/salida (I/O), base de
datos y enrutamiento debe ser estrictamente asíncrono utilizando 'async' y 'await'.