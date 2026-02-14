import os
from itertools import cycle

from dotenv import load_dotenv
import google.generativeai as genai


# --------------------------------------------------
# Cargar variables de entorno
# --------------------------------------------------

load_dotenv()

GEMINI_KEYS = [
    os.getenv("GEMINI_KEY_1"),
    os.getenv("GEMINI_KEY_2"),
    os.getenv("GEMINI_KEY_3"),
    os.getenv("GEMINI_KEY_4"),
    os.getenv("GEMINI_KEY_5"),
]

# Validación básica
GEMINI_KEYS = [k for k in GEMINI_KEYS if k]
if not GEMINI_KEYS:
    raise RuntimeError("❌ No se encontraron claves GEMINI en el .env")

# Rotador infinito de tokens
token_cycle = cycle(GEMINI_KEYS)

# --------------------------------------------------
# Prompt base (Facebook)
# --------------------------------------------------

PROMPT_BASE = (
    """
    Genera un copy publicitario en español para una publicación en Facebook basado en la imagen proporcionada.

    Formato obligatorio de salida:
    - Primera línea: SOLO el título, sin escribir la palabra "Título".
    - Segunda línea: en blanco.
    - Luego el texto del copy (sin escribir la palabra "Descripción").
    - Luego una línea en blanco.
    - Finalmente los 5 hashtags en una sola línea, sin escribir la palabra "Hashtags".

    No incluyas encabezados, etiquetas, guiones, separadores ni explicaciones.
    Entrega únicamente el texto final listo para copiar y pegar.

    Requisitos del contenido:
    - Título corto, llamativo y creativo, con emojis relevantes.
    - Descripción breve, emocional y cercana.
    - Uso natural de emojis.
    - Lenguaje persuasivo y auténtico.

    No agregues texto introductorio ni frases como "Aquí tienes el copy".
    No uses formato Markdown.
    """
)

# --------------------------------------------------
# Función principal
# --------------------------------------------------

def generar_copy_desde_imagen(imagen_path: str) -> str:
    api_key = next(token_cycle)
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel("gemini-2.5-flash")

    with open(imagen_path, "rb") as f:
        image_bytes = f.read()

    response = model.generate_content(
        [
            PROMPT_BASE,
            {
                "mime_type": "image/jpeg",
                "data": image_bytes
            }
        ]
    )

    if not response or not response.text:
        raise RuntimeError("Respuesta vacía de Gemini")

    return limpiar_texto(response.text)

# --------------------------------------------------
# Utilidad
# --------------------------------------------------

def limpiar_texto(texto: str) -> str:
    """
    Limpia el texto devuelto por Gemini
    """
    return texto.strip().replace("\r\n", "\n")
