# ia-corrector-mvp

MVP de una API con FastAPI para corregir entregas educativas. Primero aplica un corrector objetivo y luego usa Ollama local para redactar feedback pedagogico.

## Requisitos

- Python 3.11+
- Docker y Docker Compose
- Ollama si se corre local sin Docker

No usa OpenAI, APIs pagas ni LangChain.

## Instalacion local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ejecutar la API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Si Ollama corre localmente, la API usa por defecto:

```bash
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

## Correr con Docker

```bash
docker compose up --build
```

Descargar el modelo por defecto:

```bash
docker exec -it ollama ollama pull llama3.1:8b
```

Tambien podes usar otros modelos cambiando `OLLAMA_MODEL` en `docker-compose.yml`, por ejemplo:

```yaml
OLLAMA_MODEL: mistral-small3.2
```

o:

```yaml
OLLAMA_MODEL: devstral
```

Luego descarga el modelo elegido:

```bash
docker exec -it ollama ollama pull mistral-small3.2
docker exec -it ollama ollama pull devstral
```

## Probar salud

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{ "ok": true }
```

## Probar feedback

```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "class_id": "python-inicial-clase-03",
    "mode": "practice",
    "language": "python",
    "files": [
      {
        "name": "main.py",
        "content": "edad = input(\"Edad: \").strip()\nif edad.isdigit():\n    edad = int(edad)\n    print(\"Edad valida\")\nelse:\n    print(\"Ingresa un numero\")"
      }
    ]
  }'
```

Salida esperada, con `feedback` redactado por el modelo:

```json
{
  "ok": true,
  "passed": true,
  "score": 83,
  "errors": [
    "No se detecto validacion basica de campos vacios."
  ],
  "successes": [
    "Usa input() para solicitar datos.",
    "Limpia entradas con strip().",
    "Valida numeros con isdigit().",
    "Usa condicionales if.",
    "Evita convertir a int antes de validar."
  ],
  "context_used": ["py03-strip", "py03-isdigit", "py03-empty-fields", "py03-if-elif-else"],
  "feedback": "..."
}
```

## Modos

`practice`:
- Feedback docente y claro.
- Primero menciona logros.
- Da pistas graduales.
- No entrega solucion completa.
- No usa temas bloqueados.

`graded`:
- Devolucion formal.
- Criterios cumplidos y pendientes.
- Justificacion del resultado.
- Sin pistas para resolver.
- Sin solucion completa.

## Estructura

```text
ia-corrector-mvp/
|-- app/
|   |-- main.py
|   |-- schemas.py
|   |-- rag.py
|   |-- grader.py
|   |-- llm.py
|   `-- utils.py
|-- data/
|   |-- classes_metadata.json
|   |-- chunks.json
|   `-- resources_metadata.json
|-- requirements.txt
|-- Dockerfile
|-- docker-compose.yml
`-- README.md
```

## Diseno del MVP

- `grader.py`: determina aciertos, errores, score y aprobacion.
- `rag.py`: recupera contexto por palabras clave filtrando por clase y lenguaje.
- `llm.py`: arma el prompt, llama a Ollama y sanitiza temas bloqueados.
- `main.py`: coordina validacion, grading, RAG y feedback.

La busqueda RAG no usa embeddings todavia. Queda preparado un TODO para reemplazar el scoring por busqueda vectorial mas adelante.
