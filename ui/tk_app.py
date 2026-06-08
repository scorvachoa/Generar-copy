from __future__ import annotations

import os
import queue
import threading
from datetime import datetime
from tkinter import Tk, Toplevel, Frame, Label, Button, Text, Spinbox, StringVar, messagebox, filedialog, ttk, DISABLED, NORMAL, END, WORD, LEFT, RIGHT, X, Y, BOTH, W, E, EW, CENTER
from tkinter.scrolledtext import ScrolledText

from core.paths import get_env_path, get_outputs_dir
from services import copy_service
from services.key_service import normalize_keys, validate_keys, read_key_file
from storage.env_store import write_keys
from storage.processed_store import load_processed, add_processed

EXTENSIONES_VALIDAS = (".jpg", ".jpeg", ".png", ".webp")

# ── Modern dark palette (GitHub-inspired) ──
BG      = "#0d1117"
SURFACE = "#161b22"
INPUT   = "#21262d"
BORDER  = "#30363d"
ACCENT  = "#6366f1"
TEXT    = "#f0f6fc"
TEXT2   = "#8b949e"
BTN_BG  = "#21262d"
BTN_HV  = "#30363d"


def _card(parent, **kw):
    kw.setdefault("bg", SURFACE)
    kw.setdefault("padx", 16)
    kw.setdefault("pady", 12)
    return Frame(parent, **kw)


def _make_button(parent, text, command, **kw):
    kw.setdefault("bg", BTN_BG)
    kw.setdefault("fg", TEXT)
    kw.setdefault("relief", "flat")
    kw.setdefault("activebackground", BTN_HV)
    kw.setdefault("activeforeground", TEXT)
    kw.setdefault("cursor", "hand2")
    kw.setdefault("padx", 22)
    kw.setdefault("pady", 8)
    kw.setdefault("font", ("Segoe UI", 10))
    kw.setdefault("bd", 0)
    kw.setdefault("disabledforeground", TEXT2)
    return Button(parent, text=text, command=command, **kw)


class Worker(threading.Thread):
    def __init__(self, folder, amount, cancel_event, log_cb, progress_cb, done_cb):
        super().__init__(daemon=True)
        self.folder = folder
        self.amount = amount
        self.cancel_event = cancel_event
        self.log_cb = log_cb
        self.progress_cb = progress_cb
        self.done_cb = done_cb

    def run(self):
        try:
            images = [f for f in os.listdir(self.folder) if f.lower().endswith(EXTENSIONES_VALIDAS)]
            if not images:
                self.log_cb("No se encontraron im\u00e1genes v\u00e1lidas.")
                return

            outputs_dir = get_outputs_dir()
            outputs_dir.mkdir(parents=True, exist_ok=True)
            fecha = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            ruta_salida = outputs_dir / f"{fecha}.txt"

            processed = load_processed()
            pending = []
            for name in images:
                image_path = os.path.abspath(os.path.join(self.folder, name))
                if image_path in processed or name in processed:
                    continue
                pending.append((name, image_path))

            if not pending:
                self.log_cb("No hay im\u00e1genes nuevas para procesar.")
                return

            pending = pending[:self.amount]
            total = len(pending)
            self.progress_cb(0, total)
            self.log_cb(f"Im\u00e1genes encontradas: {len(images)}")
            self.log_cb(f"Im\u00e1genes pendientes: {len(pending)}")
            self.log_cb(f"Archivo de salida: {ruta_salida}")
            self.log_cb("\u2500" * 50)

            for idx, (name, image_path) in enumerate(pending, start=1):
                if self.cancel_event.is_set():
                    self.log_cb("Proceso cancelado por el usuario.")
                    break
                self.log_cb(f"[{idx}/{len(pending)}] Procesando: {name}")
                try:
                    copy = copy_service.generate_copy_from_image(image_path)
                    with ruta_salida.open("a", encoding="utf-8") as f:
                        f.write(name + "\n")
                        f.write(copy.strip() + "\n\n")
                        f.write("-" * 40 + "\n\n")
                    add_processed(os.path.abspath(image_path))
                    self.log_cb("\u2714 Copy generado")
                except Exception as e:
                    self.log_cb(f"\u2716 Error: {e}")
                self.progress_cb(idx, total)

            self.log_cb("\u2500" * 50)
            self.log_cb("Proceso finalizado")
        finally:
            self.done_cb()


class KeysDialog(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Claves Gemini")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.keys = None
        self._build_ui()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build_ui(self):
        frame = Frame(self, bg=BG, padx=20, pady=20)
        frame.pack(fill=BOTH, expand=True)

        Label(frame, text="🔑 Claves de API Gemini", bg=BG, fg=TEXT,
              font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 4))
        Label(frame, text="Ingresa una clave por l\u00ednea o carga un .txt",
              bg=BG, fg=TEXT2, font=("Segoe UI", 10)).pack(anchor=W, pady=(0, 14))

        self.text = Text(frame, bg=INPUT, fg=TEXT, insertbackground=TEXT,
                         relief="flat", highlightthickness=1, highlightbackground=BORDER,
                         height=8, width=55, font=("Consolas", 10), padx=10, pady=10)
        self.text.pack(fill=BOTH, expand=True, pady=(0, 14))

        btn_frame = Frame(frame, bg=BG)
        btn_frame.pack(fill=X)

        _make_button(btn_frame, "  Cargar .txt  ", self._load_file).pack(side=LEFT)

        right = Frame(btn_frame, bg=BG)
        right.pack(side=RIGHT)

        _make_button(right, "Cancelar", self._cancel).pack(side=LEFT)
        _make_button(right, "  Guardar  ", self._accept, bg=ACCENT, fg=BG,
                     activebackground="#79c0ff").pack(side=LEFT, padx=(10, 0))

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Selecciona un archivo .txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            content = read_key_file(path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el archivo.\n{e}", parent=self)
            return
        self.text.delete("1.0", END)
        self.text.insert("1.0", content)

    def _accept(self):
        raw = self.text.get("1.0", END).splitlines()
        keys = normalize_keys(raw)
        if not keys:
            messagebox.showwarning("Claves requeridas",
                                   "No se ingresaron claves v\u00e1lidas.", parent=self)
            return
        self.keys = keys
        self.destroy()

    def _cancel(self):
        self.keys = None
        self.destroy()


class App:
    def __init__(self):
        self.root = Tk()
        self.root.title("Generador de Copys \u2014 Gemini")
        self.root.geometry("860x640+240+80")
        self.root.configure(bg=BG)
        self.root.minsize(740, 500)

        self.env_path = get_env_path()
        copy_service.load_env(str(self.env_path))

        self.cancel_event = threading.Event()
        self.worker = None
        self.q = queue.Queue()

        self._setup_styles()
        self._build_ui()
        self._poll_queue()
        self.root.after(300, self.verify_tokens_on_start)

    # ── ttk styling ─────────────────────────────────────────────
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TProgressbar",
                        background=ACCENT,
                        troughcolor=INPUT,
                        bordercolor=SURFACE,
                        lightcolor=ACCENT,
                        darkcolor=ACCENT,
                        thickness=10)

        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.map("TLabel", background=[("", BG)])

        style.configure("TEntry",
                        fieldbackground=INPUT,
                        foreground=TEXT,
                        insertcolor=TEXT,
                        borderwidth=0,
                        relief="flat",
                        padding=8)
        style.map("TEntry",
                  fieldbackground=[("focus", INPUT)],
                  foreground=[("focus", TEXT)])

    # ── UI construction ─────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──
        header = Frame(self.root, bg=ACCENT, padx=24, pady=10)
        header.pack(fill=X)

        Label(header, text="\u2728  Generador de Copys",
              bg=ACCENT, fg="white", font=("Segoe UI", 18, "bold")).pack(anchor=W)

        # ── Main body ──
        body = Frame(self.root, bg=BG, padx=20, pady=12)
        body.pack(fill=BOTH, expand=True)

        # ── Card: Configuraci\u00f3n ──
        cfg = _card(body)
        cfg.pack(fill=X, pady=(0, 10))

        Label(cfg, text="📂  Configuraci\u00f3n", bg=SURFACE, fg=TEXT,
              font=("Segoe UI", 13, "bold")).pack(anchor=W, pady=(0, 8))

        # Carpeta
        row1 = Frame(cfg, bg=SURFACE)
        row1.pack(fill=X, pady=(0, 6))

        Label(row1, text="Carpeta de im\u00e1genes:", bg=SURFACE, fg=TEXT2,
              font=("Segoe UI", 10), width=22, anchor=W).pack(side=LEFT)

        self.folder_var = StringVar()
        self.folder_entry = ttk.Entry(row1, textvariable=self.folder_var,
                                      font=("Segoe UI", 10))
        self.folder_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8), ipady=3)

        _make_button(row1, "  Examinar  ", self._select_folder).pack(side=LEFT)

        # Cantidad
        row2 = Frame(cfg, bg=SURFACE)
        row2.pack(fill=X)

        Label(row2, text="Cantidad de im\u00e1genes:", bg=SURFACE, fg=TEXT2,
              font=("Segoe UI", 10), width=22, anchor=W).pack(side=LEFT)

        self.amount_var = StringVar(value="1")
        self.spin_amount = Spinbox(row2, from_=1, to=9999,
                                   textvariable=self.amount_var,
                                   width=7, bg=INPUT, fg=TEXT,
                                   insertbackground=TEXT, relief="flat",
                                   highlightthickness=1, highlightbackground=BORDER,
                                   buttonbackground=INPUT, font=("Segoe UI", 10),
                                   justify=CENTER)

        self.spin_amount.pack(side=LEFT, ipady=2)

        # ── Buttons ──
        btn_row = Frame(body, bg=BG)
        btn_row.pack(fill=X, pady=(0, 10))

        self.btn_generate = _make_button(btn_row, "  \u25b6 Generar copys  ",
                                         self._start_process,
                                         bg=ACCENT, fg="white", activebackground="#818cf8",
                                         font=("Segoe UI", 11, "bold"), padx=24, pady=10)
        self.btn_generate.pack(side=LEFT)

        self.btn_cancel = _make_button(btn_row, "  \u25a0 Cancelar  ",
                                       self._cancel_process, state=DISABLED,
                                       font=("Segoe UI", 10), padx=16, pady=8)
        self.btn_cancel.pack(side=LEFT, padx=(10, 0))

        _make_button(btn_row, "  🔑 Claves  ", self._update_keys,
                     font=("Segoe UI", 10), padx=16, pady=8).pack(side=LEFT, padx=(10, 0))

        # ── Card: Progreso ──
        prog = _card(body)
        prog.pack(fill=X, pady=(0, 8))

        Label(prog, text="📊  Progreso", bg=SURFACE, fg=TEXT,
              font=("Segoe UI", 13, "bold")).pack(anchor=W, pady=(0, 6))

        self.progress_var = StringVar(value="0 / 0")
        prog_top = Frame(prog, bg=SURFACE)
        prog_top.pack(fill=X, pady=(0, 4))
        Label(prog_top, textvariable=self.progress_var,
              bg=SURFACE, fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(side=LEFT)
        self.progress_bar = ttk.Progressbar(prog, mode="determinate",
                                            style="TProgressbar")
        self.progress_bar.pack(fill=X, ipady=1)

        # ── Card: Logs ──
        log_card = _card(body)
        log_card.pack(fill=BOTH, expand=True)

        Label(log_card, text="📝  Logs", bg=SURFACE, fg=TEXT,
              font=("Segoe UI", 13, "bold")).pack(anchor=W, pady=(0, 6))

        self.log_text = ScrolledText(log_card, bg=INPUT, fg=TEXT,
                                     insertbackground=TEXT, relief="flat",
                                     highlightthickness=1, highlightbackground=BORDER,
                                     wrap=WORD, font=("Consolas", 10),
                                     padx=12, pady=10)
        self.log_text.bind("<Key>", lambda e: "break")
        self.log_text.pack(fill=BOTH, expand=True)

    # ── Thread-safe queue ───────────────────────────────────────
    def _safe_cb(self, fn, *args):
        self.q.put(lambda: fn(*args))

    def _poll_queue(self):
        try:
            while True:
                cb = self.q.get_nowait()
                cb()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    # ── UI helpers ──────────────────────────────────────────────
    def log(self, msg):
        self.log_text.insert(END, msg + "\n")
        self.log_text.see(END)

    def set_progress(self, current, total):
        self.progress_var.set(f"{current} / {total}")
        self.progress_bar.configure(maximum=total, value=current)

    def set_running(self, running):
        self.btn_generate.configure(state=DISABLED if running else NORMAL)
        self.btn_cancel.configure(state=NORMAL if running else DISABLED)

    # ── Actions ─────────────────────────────────────────────────
    def _select_folder(self):
        folder = filedialog.askdirectory(title="Selecciona carpeta con im\u00e1genes")
        if folder:
            self.folder_var.set(folder)

    def verify_tokens_on_start(self):
        if not self._ensure_gemini_keys():
            self.btn_generate.configure(state=DISABLED)
            self.log("\u26a0 No hay claves configuradas. Haz clic en \u201cClaves\u201d para continuar.")

    def _ensure_gemini_keys(self, force=False):
        keys = copy_service.load_env(str(self.env_path))
        if keys and not force:
            return True

        dialog = KeysDialog(self.root)
        self.root.wait_window(dialog)
        keys = dialog.keys
        if not keys:
            messagebox.showwarning("Claves requeridas",
                                   "No se ingresaron claves.", parent=self.root)
            return False

        ok, errors = validate_keys(keys)
        if not ok:
            messagebox.showerror("Claves inv\u00e1lidas",
                                 "\n".join(errors), parent=self.root)
            return False
        if errors:
            messagebox.showwarning("Formato inusual",
                                   "\n".join(errors), parent=self.root)

        write_keys(keys)
        for idx, key in enumerate(keys, start=1):
            os.environ[f"GEMINI_KEY_{idx}"] = key
        copy_service.load_env(str(self.env_path))
        return True

    def _start_process(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Selecciona una carpeta v\u00e1lida.",
                                 parent=self.root)
            return

        try:
            amount = int(self.amount_var.get())
        except ValueError:
            amount = 1

        if amount <= 0:
            messagebox.showerror("Error", "La cantidad debe ser mayor a 0.",
                                 parent=self.root)
            return

        if self.worker and self.worker.is_alive():
            messagebox.showinfo("En proceso",
                                "Ya hay un proceso en ejecuci\u00f3n.",
                                parent=self.root)
            return

        if not self._ensure_gemini_keys():
            return

        self.cancel_event.clear()
        self.set_running(True)

        self.worker = Worker(
            folder, amount, self.cancel_event,
            log_cb=lambda m: self._safe_cb(self.log, m),
            progress_cb=lambda c, t: self._safe_cb(self.set_progress, c, t),
            done_cb=lambda: self._safe_cb(self._on_finished),
        )
        self.worker.start()

    def _cancel_process(self):
        self.cancel_event.set()
        self.log("\u23f1 Cancelaci\u00f3n solicitada. Finalizando\u2026")

    def _update_keys(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("En proceso",
                                "Espera a que termine el proceso actual.",
                                parent=self.root)
            return

        if not messagebox.askyesno(
            "Actualizar claves",
            "\u00bfDeseas reemplazar las claves actuales?",
            parent=self.root
        ):
            return

        if self._ensure_gemini_keys(force=True):
            self.btn_generate.configure(state=NORMAL)
            self.log("\u2705 Claves actualizadas.")

    def _on_finished(self):
        self.set_running(False)

    def run(self):
        self.root.mainloop()


def run_app():
    App().run()
