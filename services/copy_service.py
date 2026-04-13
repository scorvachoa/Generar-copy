from __future__ import annotations

import os
import time
import mimetypes
from itertools import cycle

from dotenv import load_dotenv
import google.generativeai as genai

GEMINI_KEYS: list[str] = []
GEMINI_MODEL = "gemini-2.5-flash"
_token_cycle = None

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


def load_env(env_path: str | None = None) -> list[str]:
    load_dotenv(env_path)

    global GEMINI_MODEL
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", GEMINI_MODEL)

    keys = [
        os.getenv("GEMINI_KEY_1"),
        os.getenv("GEMINI_KEY_2"),
        os.getenv("GEMINI_KEY_3"),
        os.getenv("GEMINI_KEY_4"),
        os.getenv("GEMINI_KEY_5"),
    ]

    keys = [k for k in keys if k]
    if keys:
        _set_keys(keys)

    return keys


def _set_keys(keys: list[str]) -> None:
    global GEMINI_KEYS, _token_cycle
    GEMINI_KEYS = list(keys)
    _token_cycle = cycle(GEMINI_KEYS)


def generate_copy_from_image(image_path: str, max_intentos: int = 3) -> str:
    if not GEMINI_KEYS:
        load_env()

    if not GEMINI_KEYS:
        raise RuntimeError("No se encontraron claves GEMINI. Configura .env o ingrésalas en la app.")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    mime_type = _detect_mime(image_path)
    last_error = None

    for intento in range(1, max_intentos + 1):
        try:
            api_key = next(_token_cycle)
            genai.configure(api_key=api_key)

            model = genai.GenerativeModel(GEMINI_MODEL)

            response = model.generate_content(
                [
                    PROMPT_BASE,
                    {
                        "mime_type": mime_type,
                        "data": image_bytes,
                    },
                ]
            )

            if not response or not response.text:
                raise RuntimeError("Respuesta vacía de Gemini")

            return _clean_text(response.text)

        except Exception as e:
            last_error = e
            if intento < max_intentos:
                time.sleep(1.5 * intento)
                continue
            raise last_error


def _clean_text(text: str) -> str:
    return text.strip().replace("\r\n", "\n")


def _detect_mime(image_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    return mime_type or "image/jpeg"
