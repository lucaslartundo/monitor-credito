"""
ia.py — capa de datos del recolector, SOLO con Firecrawl (gratis).

Firecrawl hace las dos cosas:
  scrape()          entra a una URL (aunque tenga Cloudflare o JS) -> markdown.
  extraer_acciones()usa el endpoint de extraccion de Firecrawl con un esquema
                    JSON, y devuelve las acciones ya estructuradas. La IA la
                    pone Firecrawl; NO se necesita cuenta de Anthropic.

La clave se lee de FIRECRAWL_API_KEY (variable de entorno). Nunca va en el repo.
"""
import os
import time
import requests

FIRECRAWL_KEY = os.environ.get('FIRECRAWL_API_KEY', '').strip()
SCRAPE_URL = 'https://api.firecrawl.dev/v1/scrape'


def _headers():
    if not FIRECRAWL_KEY:
        raise RuntimeError('Falta FIRECRAWL_API_KEY. Ver LEEME para configurarla.')
    return {'Authorization': f'Bearer {FIRECRAWL_KEY}',
            'Content-Type': 'application/json'}


def _post(payload):
    for intento in range(3):
        try:
            r = requests.post(SCRAPE_URL, headers=_headers(), json=payload, timeout=120)
            if r.status_code == 402:
                raise RuntimeError('Firecrawl sin créditos este mes.')
            r.raise_for_status()
            return r.json()
        except RuntimeError:
            raise
        except Exception:
            if intento == 2:
                raise
            time.sleep(2 * (intento + 1))
    return {}


def scrape(url, esperar_js=True, sigilo=False):
    payload = {'url': url, 'formats': ['markdown'],
               'onlyMainContent': True, 'timeout': 45000}
    if sigilo:
        payload['proxy'] = 'stealth'
    if esperar_js:
        payload['waitFor'] = 2500
    data = _post(payload)
    return (data.get('data', {}) or {}).get('markdown', '') or ''


ESQUEMA_ACCIONES = {
    "type": "object",
    "properties": {
        "acciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "Fecha YYYY-MM-DD"},
                    "emisor": {"type": "string", "description": "Nombre del emisor, sin el tipo de instrumento"},
                    "instrumento": {"type": "string", "description": "solvencia, bonos, acciones, etc."},
                    "escala": {"type": "string", "enum": ["largo", "corto", "acciones"]},
                    "anterior": {"type": "string", "description": "Nota previa si se menciona; vacío si no"},
                    "actual": {"type": "string", "description": "Nota nueva o vigente"},
                    "perspectiva": {"type": "string", "description": "Estable/Positiva/Negativa/En Observación o vacío"},
                    "accion": {"type": "string", "enum": ["sube", "baja", "mantiene", "nueva", "retiro", "perspectiva"]},
                    "documento_url": {"type": "string", "description": "URL del PDF si aparece; vacío si no"},
                    "titular": {"type": "string", "description": "Frase original de la clasificadora"},
                },
                "required": ["fecha", "emisor", "actual", "accion", "titular"],
            },
        }
    },
    "required": ["acciones"],
}


def extraer_acciones(url, clasificadora, desde, hasta, esperar_js=False, sigilo=False):
    prompt = (
        f"Esta es una página de la clasificadora de riesgo {clasificadora} (Chile). "
        f"Extrae SOLO las acciones de clasificación cuya fecha esté entre {desde} y "
        f"{hasta} (inclusive). Emisor sin el tipo de instrumento: 'de los bonos de "
        f"Empresa X' -> 'Empresa X'. Fecha YYYY-MM-DD. Tipo de acción según el verbo: "
        f"sube/aumenta->sube, baja/disminuye->baja, ratifica/mantiene/confirma->"
        f"mantiene, asigna/clasifica primera vez->nueva, retira->retiro, solo cambia "
        f"tendencia->perspectiva. Incluye la URL del PDF si aparece. Lista vacía si "
        f"no hay acciones en el rango."
    )
    payload = {
        'url': url, 'formats': ['json'], 'onlyMainContent': True, 'timeout': 60000,
        'jsonOptions': {'schema': ESQUEMA_ACCIONES, 'prompt': prompt},
    }
    if sigilo:
        payload['proxy'] = 'stealth'
    if esperar_js:
        payload['waitFor'] = 3000

    data = _post(payload)
    obj = (data.get('data', {}) or {}).get('json', {}) or {}
    acciones = obj.get('acciones', []) if isinstance(obj, dict) else []
    limpias = []
    for a in acciones:
        if not isinstance(a, dict):
            continue
        for k in ('anterior', 'perspectiva', 'documento_url', 'instrumento'):
            if not a.get(k):
                a[k] = None
        limpias.append(a)
    return limpias
