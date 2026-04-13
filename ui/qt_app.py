from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

from core.paths import get_env_path, get_outputs_dir
from services import copy_service
from services.key_service import normalize_keys, validate_keys, read_key_file
from storage.env_store import write_keys
from storage.processed_store import load_processed, add_processed

EXTENSIONES_VALIDAS = (".jpg", ".jpeg", ".png", ".webp")


def apply_dark_palette(app: QtWidgets.QApplication) -> None:
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#121212"))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#E6E6E6"))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#1B1B1B"))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#181818"))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#E6E6E6"))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#1E1E1E"))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#E6E6E6"))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#4CC2FF"))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#0B0B0B"))
    app.setPalette(palette)


class Worker(QtCore.QThread):
    log = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int, int)
    finished = QtCore.pyqtSignal()
    state = QtCore.pyqtSignal(bool)

    def __init__(self, folder: str, amount: int, cancel_flag: QtCore.QObject):
        super().__init__()
        self.folder = folder
        self.amount = amount
        self.cancel_flag = cancel_flag

    def run(self) -> None:
        images = [
            f for f in os.listdir(self.folder)
            if f.lower().endswith(EXTENSIONES_VALIDAS)
        ]

        if not images:
            self.log.emit("No se encontraron imágenes válidas.")
            self.state.emit(False)
            self.finished.emit()
            return

        outputs_dir = get_outputs_dir()
        outputs_dir.mkdir(parents=True, exist_ok=True)
        fecha = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ruta_salida = outputs_dir / f"{fecha}.txt"

        processed = load_processed()
        pending: list[tuple[str, str]] = []

        for name in images:
            image_path = os.path.abspath(os.path.join(self.folder, name))
            if image_path in processed or name in processed:
                continue
            pending.append((name, image_path))

        if not pending:
            self.log.emit("No hay imágenes nuevas para procesar.")
            self.state.emit(False)
            self.finished.emit()
            return

        pending = pending[: self.amount]
        total = len(pending)
        self.progress.emit(0, total)

        self.log.emit(f"Imágenes encontradas: {len(images)}")
        self.log.emit(f"Imágenes pendientes: {len(pending)}")
        self.log.emit(f"Archivo de salida: {ruta_salida}")
        self.log.emit("-" * 50)

        for idx, (name, image_path) in enumerate(pending, start=1):
            if self.cancel_flag.property("cancel") is True:
                self.log.emit("Proceso cancelado por el usuario.")
                break

            self.log.emit(f"[{idx}/{len(pending)}] Procesando: {name}")
            try:
                copy = copy_service.generate_copy_from_image(image_path)
                with ruta_salida.open("a", encoding="utf-8") as f:
                    f.write(name + "\n")
                    f.write(copy.strip() + "\n\n")
                    f.write("-" * 40 + "\n\n")
                add_processed(os.path.abspath(image_path))
                self.log.emit("Copy generado")
            except Exception as e:
                self.log.emit(f"Error: {e}")

            self.progress.emit(idx, total)

        self.log.emit("=" * 50)
        self.log.emit("Proceso finalizado")
        self.state.emit(False)
        self.finished.emit()


class KeysDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Claves Gemini")
        self.setFixedSize(520, 360)
        self.keys: list[str] | None = None

        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel("Ingresa una clave por línea o carga un .txt:")
        layout.addWidget(label)

        self.text = QtWidgets.QPlainTextEdit()
        self.text.setPlaceholderText("Una clave por línea")
        layout.addWidget(self.text)

        btns = QtWidgets.QHBoxLayout()
        self.btn_load = QtWidgets.QPushButton("Cargar .txt")
        self.btn_load.clicked.connect(self.load_file)
        btns.addWidget(self.btn_load)
        btns.addStretch(1)
        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_cancel)
        self.btn_ok = QtWidgets.QPushButton("Guardar")
        self.btn_ok.clicked.connect(self.accept_keys)
        btns.addWidget(self.btn_ok)
        layout.addLayout(btns)

    def load_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Selecciona un archivo .txt",
            "",
            "Text files (*.txt);;All files (*)",
        )
        if not path:
            return
        try:
            content = read_key_file(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo leer el archivo. {e}")
            return
        self.text.setPlainText(content)

    def accept_keys(self) -> None:
        raw = self.text.toPlainText().splitlines()
        keys = normalize_keys(raw)
        if not keys:
            QtWidgets.QMessageBox.warning(self, "Claves requeridas", "No se ingresaron claves válidas.")
            return
        self.keys = keys
        self.accept()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Generador de Copys (Gemini)")
        self.resize(820, 560)

        self.env_path = get_env_path()
        copy_service.load_env(str(self.env_path))

        self.cancel_flag = QtCore.QObject()
        self.cancel_flag.setProperty("cancel", False)

        self.worker: Worker | None = None

        self._build_ui()
        QtCore.QTimer.singleShot(200, self.verify_tokens_on_start)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Generador de copys")
        title.setObjectName("Title")
        layout.addWidget(title)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)

        form.addWidget(QtWidgets.QLabel("Carpeta de imágenes:"), 0, 0)
        self.folder_edit = QtWidgets.QLineEdit()
        form.addWidget(self.folder_edit, 1, 0, 1, 2)
        self.btn_folder = QtWidgets.QPushButton("Seleccionar")
        self.btn_folder.clicked.connect(self.select_folder)
        form.addWidget(self.btn_folder, 1, 2)

        form.addWidget(QtWidgets.QLabel("Cantidad de imágenes:"), 2, 0)
        self.spin_amount = QtWidgets.QSpinBox()
        self.spin_amount.setRange(1, 9999)
        self.spin_amount.setValue(1)
        form.addWidget(self.spin_amount, 2, 1)

        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_generate = QtWidgets.QPushButton("Generar copys")
        self.btn_generate.clicked.connect(self.start_process)
        btn_row.addWidget(self.btn_generate)

        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.cancel_process)
        self.btn_cancel.setEnabled(False)
        btn_row.addWidget(self.btn_cancel)

        self.btn_keys = QtWidgets.QPushButton("Actualizar claves")
        self.btn_keys.clicked.connect(self.update_keys)
        btn_row.addWidget(self.btn_keys)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.progress_label = QtWidgets.QLabel("Progreso: 0/0")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(0)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        layout.addWidget(QtWidgets.QLabel("Logs:"))
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(180)
        layout.addWidget(self.log_text, 1)

        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #121212; color: #E6E6E6; font-family: 'Segoe UI'; }
            QLabel#Title { font-size: 18px; font-weight: 600; }
            QLineEdit, QPlainTextEdit, QSpinBox { background: #1B1B1B; border: 1px solid #2A2A2A; padding: 6px; }
            QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus { border: 1px solid #4CC2FF; }
            QPushButton { background: #1E1E1E; border: 1px solid #2A2A2A; padding: 6px 12px; }
            QPushButton:hover { background: #2A2A2A; }
            QPushButton:disabled { color: #7A7A7A; background: #1A1A1A; }
            QProgressBar { background: #202020; border: 1px solid #2A2A2A; height: 14px; text-align: center; }
            QProgressBar::chunk { background: #4CC2FF; }
            """
        )

    def log(self, message: str) -> None:
        self.log_text.appendPlainText(message)

    def select_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecciona carpeta")
        if folder:
            self.folder_edit.setText(folder)

    def start_process(self) -> None:
        folder = self.folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QtWidgets.QMessageBox.critical(self, "Error", "Selecciona una carpeta válida.")
            return

        amount = self.spin_amount.value()
        if amount <= 0:
            QtWidgets.QMessageBox.critical(self, "Error", "La cantidad debe ser mayor a 0.")
            return

        if self.worker and self.worker.isRunning():
            QtWidgets.QMessageBox.information(self, "En proceso", "Ya hay un proceso en ejecución.")
            return

        if not self.ensure_gemini_keys():
            return

        self.cancel_flag.setProperty("cancel", False)
        self.set_running(True)

        self.worker = Worker(folder, amount, self.cancel_flag)
        self.worker.log.connect(self.log)
        self.worker.progress.connect(self.set_progress)
        self.worker.state.connect(self.set_running)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def cancel_process(self) -> None:
        self.cancel_flag.setProperty("cancel", True)
        self.log("Cancelación solicitada. Finalizando...")

    def update_keys(self) -> None:
        if self.worker and self.worker.isRunning():
            QtWidgets.QMessageBox.information(self, "En proceso", "Espera a que termine el proceso actual.")
            return

        if QtWidgets.QMessageBox.question(
            self,
            "Actualizar claves",
            "Esto reemplazará las claves actuales. ¿Deseas continuar?",
        ) != QtWidgets.QMessageBox.Yes:
            return

        if self.ensure_gemini_keys(force=True):
            self.btn_generate.setEnabled(True)
            self.log("Claves actualizadas.")

    def ensure_gemini_keys(self, force: bool = False) -> bool:
        keys = copy_service.load_env(str(self.env_path))
        if keys and not force:
            return True

        dialog = KeysDialog(self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            QtWidgets.QMessageBox.warning(self, "Claves requeridas", "No se ingresaron claves.")
            return False

        keys = dialog.keys or []
        ok, errors = validate_keys(keys)
        if not ok:
            QtWidgets.QMessageBox.critical(self, "Claves inválidas", "\n".join(errors))
            return False
        if errors:
            QtWidgets.QMessageBox.warning(self, "Claves con formato inusual", "\n".join(errors))

        write_keys(keys)
        for idx, key in enumerate(keys, start=1):
            os.environ[f"GEMINI_KEY_{idx}"] = key

        copy_service.load_env(str(self.env_path))
        return True

    def verify_tokens_on_start(self) -> None:
        if not self.ensure_gemini_keys():
            self.set_running(False)
            self.btn_generate.setEnabled(False)
            self.log("No hay claves configuradas. Agrega claves para continuar.")

    def set_progress(self, current: int, total: int) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Progreso: {current}/{total}")

    def set_running(self, running: bool) -> None:
        self.btn_generate.setEnabled(not running)
        self.btn_cancel.setEnabled(running)

    def on_finished(self) -> None:
        self.set_running(False)


def run_app() -> None:
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")
    app = QtWidgets.QApplication([])
    apply_dark_palette(app)
    window = MainWindow()
    window.show()
    app.exec_()
