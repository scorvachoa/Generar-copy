# Generar-copy
Generador de copys para Facebook a partir de imágenes usando Gemini (UI en tkinter).

## Requisitos
- Windows 10/11
- Python 3.10+ (recomendado)
- Claves de Gemini

## Instalación
```bash
pip install -r requirements.txt
```

## Configuración de claves
- Copia `.env.example` a `.env` y completa la clave.
- Si no existe `.env`, la app te pedirá las claves al iniciar y las guardará automáticamente.

Formato válido (una clave por línea o separadas por espacios/comas/;):
```
GEMINI_KEY_1=AIzaSy...
AIzaSy...
AIzaSy... , AIzaSy...
```

Ejemplo `.env`:
```
GEMINI_KEY_1=tu_clave
# Opcional: modelo
GEMINI_MODEL=gemini-2.5-flash
```

## Uso
```bash
python app.py
```

También puedes usar el ejecutable compilado en `dist/GenerarCopy.exe`.

## Interfaz
- UI con tkinter (tema oscuro moderno, estilo GitHub Dark).
- Permite cargar claves por línea o desde un `.txt`.
- Botón "Actualizar claves" con confirmación.
- Diseño tipo card con acento índigo.

## Salida
- Se genera un archivo por ejecución en `outputs/` con timestamp.
- Las imágenes procesadas se registran en `procesadas.json` usando rutas absolutas.

## Estructura del proyecto
- `app.py` → entry point
- `ui/tk_app.py` → UI tkinter
- `services/` → lógica de Gemini y validaciones
- `storage/` → persistencia de `.env` y procesadas
- `core/paths.py` → rutas base

## Compilar a .exe
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon assets/copy.ico --name GenerarCopy app.py
```
