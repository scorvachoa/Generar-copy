import os
import json
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from generar_copy import generar_copy_desde_imagen

ARCHIVO_PROCESADAS = "procesadas.json"
EXTENSIONES_VALIDAS = (".jpg", ".jpeg", ".png", ".webp")

def cargar_procesadas():
    if not os.path.exists(ARCHIVO_PROCESADAS):
        return set()

    with open(ARCHIVO_PROCESADAS, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("imagenes_procesadas", []))


def guardar_procesada(nombre_imagen):
    procesadas = cargar_procesadas()
    procesadas.add(nombre_imagen)

    with open(ARCHIVO_PROCESADAS, "w", encoding="utf-8") as f:
        json.dump(
            {"imagenes_procesadas": list(procesadas)},
            f,
            indent=4,
            ensure_ascii=False
        )

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Generador de Copys (Gemini)")
        self.geometry("700x500")
        self.resizable(False, False)

        self.carpeta_imagenes = tk.StringVar()
        self.cantidad_imagenes = tk.IntVar(value=1)

        self._crear_ui()

    def _crear_ui(self):
        # --- Selección de carpeta ---
        frame_folder = tk.Frame(self)
        frame_folder.pack(pady=10, padx=10, fill="x")

        tk.Label(frame_folder, text="Carpeta de imágenes:").pack(anchor="w")
        entry = tk.Entry(frame_folder, textvariable=self.carpeta_imagenes, width=80)
        entry.pack(side="left", padx=(0, 5))

        tk.Button(
            frame_folder,
            text="Seleccionar",
            command=self.seleccionar_carpeta
        ).pack(side="left")

        # --- Cantidad de imágenes ---
        frame_cantidad = tk.Frame(self)
        frame_cantidad.pack(pady=5, padx=10, anchor="w")

        tk.Label(frame_cantidad, text="Cantidad de imágenes:").pack(side="left")
        tk.Spinbox(
            frame_cantidad,
            from_=1,
            to=9999,
            width=5,
            textvariable=self.cantidad_imagenes
        ).pack(side="left", padx=5)

        # --- Botón generar ---
        frame_btn = tk.Frame(self)
        frame_btn.pack(pady=10)

        tk.Button(
            frame_btn,
            text="Generar copys",
            width=20,
            command=self.iniciar_proceso
        ).pack()

        # --- Logs ---
        frame_logs = tk.Frame(self)
        frame_logs.pack(padx=10, pady=10, fill="both", expand=True)

        tk.Label(frame_logs, text="Logs:").pack(anchor="w")
        self.log_text = scrolledtext.ScrolledText(
            frame_logs,
            height=18,
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

    # -----------------------------------------------------

    def seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory()
        if carpeta:
            self.carpeta_imagenes.set(carpeta)

    def iniciar_proceso(self):
        carpeta = self.carpeta_imagenes.get()

        if not carpeta or not os.path.isdir(carpeta):
            messagebox.showerror("Error", "Selecciona una carpeta válida.")
            return

        cantidad = self.cantidad_imagenes.get()
        if cantidad <= 0:
            messagebox.showerror("Error", "La cantidad debe ser mayor a 0.")
            return

        # Hilo para no congelar la UI
        hilo = threading.Thread(
            target=self.procesar_imagenes,
            daemon=True
        )
        hilo.start()

    # -----------------------------------------------------

    def procesar_imagenes(self):

        carpeta = self.carpeta_imagenes.get()
        cantidad = self.cantidad_imagenes.get()

        imagenes = [
            f for f in os.listdir(carpeta)
            if f.lower().endswith(EXTENSIONES_VALIDAS)
        ]

        if not imagenes:
            self.log("❌ No se encontraron imágenes válidas.")
            return

        imagenes = imagenes[:cantidad]

        os.makedirs("outputs", exist_ok=True)
        fecha = datetime.now().strftime("%Y-%m-%d")
        ruta_salida = os.path.join("outputs", f"{fecha}.txt")

        self.log(f"📂 Imágenes encontradas: {len(imagenes)}")
        self.log(f"📝 Archivo de salida: {ruta_salida}")
        self.log("-" * 50)

        procesadas = cargar_procesadas()

        for idx, nombre in enumerate(imagenes, start=1):

            if nombre in procesadas:
                self.log(f"⏭ Imagen ya procesada, se omite: {nombre}")
                continue

            ruta_imagen = os.path.join(carpeta, nombre)
            self.log(f"[{idx}/{len(imagenes)}] Procesando: {nombre}")

            try:
                copy = generar_copy_desde_imagen(ruta_imagen)

                with open(ruta_salida, "a", encoding="utf-8") as f:
                    f.write(nombre + "\n")
                    f.write(copy.strip() + "\n\n")
                    f.write("-" * 40 + "\n\n")

                guardar_procesada(nombre)  # ← ahora sí guardamos

                self.log("✅ Copy generado")

            except Exception as e:
                self.log(f"❌ Error: {e}")

        self.log("=" * 50)
        self.log("🎉 Proceso finalizado")

    # -----------------------------------------------------

    def log(self, mensaje):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", mensaje + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
