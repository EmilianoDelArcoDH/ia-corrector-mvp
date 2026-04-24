# ia-corrector-mvp

MVP de una API con FastAPI para corregir entregas educativas. Primero aplica un corrector objetivo y luego usa Ollama local para redactar feedback pedagogico.

La API acepta entregas en texto/codigo, archivos y enlaces. Eso permite corregir tanto repositorios de codigo como planillas exportadas o publicadas mediante URL.

Si queres subir archivos binarios directamente, usa `POST /feedback/upload` con `multipart/form-data`. Ese endpoint convierte `.csv` y `.xlsx` a texto antes de corregirlos.

## Base de contenido

Para construir la base de contenido desde materiales de clase, usá el manifiesto de fuentes y el script de ingesta:

```bash
python scripts/build_content_base.py --manifest content_sources/manifest.json --output-dir data --base-dir .
```

Ejemplo de `content_sources/manifest.json`:

```json
[
  {
    "id": "python-inicial-clase-03-guia",
    "class_id": "python-inicial-clase-03",
    "language": "python",
    "type": "lesson_notes",
    "title": "Guía de condicionales y validaciones básicas",
    "source": "file",
    "path": "content/python/clase-03/guia.md",
    "keywords": ["input", "strip", "isdigit", "if", "else"]
  },
  {
    "id": "web-inicial-clase-01-slides",
    "class_id": "web-inicial-clase-01",
    "language": "html",
    "type": "slides",
    "title": "Diapositivas de estructura HTML",
    "source": "url",
    "url": "https://docs.google.com/presentation/d/...",
    "keywords": ["html", "head", "body", "p"]
  }
]
```

El script genera:

- `data/resources_metadata.json`
- `data/chunks.json`
- `data/class_catalog.json`

Cada recurso se normaliza a texto, se divide en chunks y se le agregan palabras clave para que el RAG recupere mejor el contenido de la clase.
El catalogo de clase resume que recursos tiene cada `class_id` y ayuda al modelo a entender mejor el contexto de la materia.

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

Tambien podes enviar una entrega tipo enlace o una planilla:

```json
{
  "class_id": "spreadsheet-basico-clase-01",
  "mode": "graded",
  "language": "sheet",
  "files": [
    {
      "name": "entrega",
      "kind": "link",
      "url": "https://example.com/mi-planilla-publica.csv"
    }
  ]
}
```

```json
{
  "class_id": "spreadsheet-basico-clase-01",
  "mode": "graded",
  "language": "csv",
  "files": [
    {
      "name": "ventas.csv",
      "kind": "file",
      "mime_type": "text/csv",
      "content": "mes,total\nenero,10\nfebrero,12"
    }
  ]
}
```

Tambien esta disponible la version para archivos reales:

```bash
curl -X POST http://localhost:8000/feedback/upload \
  -F "class_id=spreadsheet-basico-clase-01" \
  -F "mode=graded" \
  -F "language=sheet" \
  -F "files=@./ventas.xlsx"
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

- `grader.py`: determina aciertos, errores, score y aprobacion para codigo y planillas.
- `rag.py`: recupera contexto por palabras clave filtrando por clase y lenguaje.
- `llm.py`: arma el prompt, llama a Ollama y sanitiza temas bloqueados.
- `main.py`: coordina validacion, grading, RAG y feedback.

La busqueda RAG no usa embeddings todavia. Queda preparado un TODO para reemplazar el scoring por busqueda vectorial mas adelante.
