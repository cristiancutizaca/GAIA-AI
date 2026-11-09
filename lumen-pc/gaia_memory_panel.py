"""Edit and export explicit memories from the resident desktop."""
import json
from pathlib import Path
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)


class MemoryPanel(QDialog):
    completed = Signal(str, object, str)

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("GAIA · Recuerdos explícitos")
        self.resize(680, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Escribe «Recuerda que …» en el chat para guardar un recuerdo."))
        filters = QHBoxLayout()
        self.project = QLineEdit()
        self.project.setPlaceholderText("Proyecto (vacío para recuerdos personales)")
        self.query = QLineEdit()
        self.query.setPlaceholderText("Buscar en estos recuerdos")
        for widget in (self.project, self.query):
            filters.addWidget(widget)
            widget.returnPressed.connect(self.refresh)
        layout.addLayout(filters)
        self.results = QListWidget()
        self.results.currentItemChanged.connect(self._select)
        layout.addWidget(self.results)
        self.content = QTextEdit()
        self.content.setAcceptRichText(False)
        self.content.setPlaceholderText("Selecciona un recuerdo para editarlo")
        layout.addWidget(self.content)
        actions = QHBoxLayout()
        for title, handler in (
            ("Buscar", self.refresh), ("Guardar cambios", self._save),
            ("Borrar", self._delete), ("Exportar JSON", self._export),
        ):
            button = QPushButton(title)
            button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.busy = False
        self.completed.connect(self._finished)

    def _run(self, operation, work):
        if self.busy:
            return
        self.busy = True
        self.status.setText("Trabajando…")

        def worker():
            try:
                self.completed.emit(operation, work(), "")
            except Exception as exc:
                self.completed.emit(operation, None, str(exc)[:400])

        threading.Thread(target=worker, daemon=True, name="gaia-memory-panel").start()

    def refresh(self):
        query = self.query.text().strip()
        project = self.project.text().strip()
        self._run("list", lambda: self.api.explicit_memories(query, project))

    def _select(self, item, _previous):
        self.content.setPlainText(item.data(Qt.UserRole)["content"] if item else "")

    def _save(self):
        item = self.results.currentItem()
        content = self.content.toPlainText().strip()
        if item and content:
            item_id = item.data(Qt.UserRole)["memory_id"]
            self._run("update", lambda: self.api.edit_explicit_memory(item_id, content))

    def _delete(self):
        item = self.results.currentItem()
        if self.busy or item is None:
            return
        if QMessageBox.question(self, "Borrar recuerdo", "¿Borrar el recuerdo seleccionado?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            item_id = item.data(Qt.UserRole)["memory_id"]
            self._run("delete", lambda: self.api.delete_explicit_memory(item_id))

    def _export(self):
        if self.busy:
            return
        name, _ = QFileDialog.getSaveFileName(self, "Exportar recuerdos de este dispositivo",
                                              "gaia-recuerdos.json", "JSON (*.json)")
        if not name:
            return

        def write():
            rows = self.api.export_explicit_memories()
            Path(name).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            return len(rows)

        self._run("export", write)

    def _finished(self, operation, data, error):
        self.busy = False
        if error:
            self.status.setText(error)
        elif operation == "list":
            self.results.clear()
            for row in data:
                preview = " ".join(row["content"].split())[:100]
                item = QListWidgetItem(preview)
                item.setData(Qt.UserRole, row)
                self.results.addItem(item)
            self.status.setText(f"{len(data)} recuerdo(s) encontrado(s).")
        elif operation == "export":
            self.status.setText(f"{data} recuerdo(s) exportado(s).")
        else:
            self.refresh()
