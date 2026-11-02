"""GAIA desktop control center: explicit statuses, visual feedback and actions."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QComboBox, QFrame, QScrollArea, QSizePolicy
)

STYLES = """
QWidget#gaiaPanel { background: #0a0f1d; color: #e5f2ff; }
QScrollArea { border:0; background: #0e192a; }
QWidget { font-family: 'Segoe UI'; font-size: 13px; }
QLabel { color: #dceaf8; background: transparent; }
QLabel#brand { font-size: 28px; font-weight: 800; color: #e7fbff; }
QLabel#tagline { color: #7b93b7; font-size: 12px; }
QLabel#statusBadge { color:#65e8fa; background:#112c40; border:1px solid #266b83; padding:6px 13px; border-radius:13px; font-weight:700; }
QLabel#hint { color:#9bb5cf; font-size:11px; }
QLabel#sectionTitle { color:#8fbff2; font-size:12px; font-weight:700; }
QFrame#card { border-radius: 16px; background:#121b30; border:1px solid #243851; }
QFrame#side { background:#0e192a; border-right:1px solid #203450; }
QLineEdit, QComboBox { background: #0e1c30; border:1px solid #31506f; padding:12px; border-radius:10px; color:#effbff; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #46ccf2; }
QTextEdit { background:#111b2d; border:1px solid #203751; border-radius:12px; color:#e7f4ff; padding:12px; }
QPushButton { border:1px solid #355572; border-radius:10px; padding:11px 16px; background:#172a43; color:#ddf5ff; font-weight:600; }
QPushButton:hover { border:1px solid #59d6ff; background:#203e58; }
QPushButton:disabled { color:#668099; background:#121d2c; }
QPushButton#primary { background:#176389; border:1px solid #42cbf5; }
QPushButton#vision { background:#1d324b; border:1px solid #5e92c3; }
"""

class GaiaControlPanel(QWidget):
    send_requested = Signal(str)
    vision_requested = Signal(str, str)
    mic_requested = Signal()
    wake_requested = Signal()
    refresh_requested = Signal()
    ptt_requested = Signal()
    pc_diagnostic_requested = Signal()
    comfy_diagnostic_requested = Signal()
    readiness_requested = Signal()
    tasks_requested = Signal()
    def __init__(self):
        super().__init__()
        self.setObjectName("gaiaPanel"); self.setWindowTitle("GAIA · Centro de Control")
        self.setStyleSheet(STYLES); self.setMinimumSize(730, 550); self.resize(900, 690)
        base=QHBoxLayout(self);base.setContentsMargins(0,0,0,0);base.setSpacing(0)
        side=QFrame();side.setObjectName("side");side.setFixedWidth(230)
        left=QVBoxLayout(side);left.setContentsMargins(20,25,20,18);left.setSpacing(14)
        brand=QLabel("✧  G A I A"); brand.setObjectName("brand");left.addWidget(brand)
        tag=QLabel("ASISTENTE LOCAL · 2.0");tag.setObjectName("tagline");left.addWidget(tag)
        left.addSpacing(15)
        self.state_label=QLabel("● INICIANDO");self.state_label.setObjectName("statusBadge");left.addWidget(self.state_label)
        left.addSpacing(15)
        left.addWidget(self._title("SISTEMAS"))
        self.core_state=self._small("Core: verificando…")
        self.chat_state=self._small("Chat/IA: verificando…")
        self.vision_state=self._small("Visión: verificando…")
        self.voice_state=self._small("Voz: Push-to-talk")
        for label in (self.core_state,self.chat_state,self.vision_state,self.voice_state):left.addWidget(label)
        left.addSpacing(10)
        left.addWidget(self._title("ACCESOS RÁPIDOS"))
        self.ptt_button=QPushButton("🎙  Hablar / Detener");self.ptt_button.clicked.connect(self.ptt_requested);left.addWidget(self.ptt_button)
        self.mic_button=QPushButton("Micrófono ON/OFF");self.mic_button.clicked.connect(self.mic_requested);left.addWidget(self.mic_button)
        self.wake_button=QPushButton("Activación por voz");self.wake_button.clicked.connect(self.wake_requested);left.addWidget(self.wake_button)
        self.refresh_button=QPushButton("↻  Estado Core");self.refresh_button.clicked.connect(self.refresh_requested);left.addWidget(self.refresh_button)
        self.pc_button=QPushButton("▣  Diagnosticar PC");self.pc_button.clicked.connect(self.pc_diagnostic_requested);left.addWidget(self.pc_button)
        self.comfy_button=QPushButton("◈  Diagnosticar ComfyUI");self.comfy_button.clicked.connect(self.comfy_diagnostic_requested);left.addWidget(self.comfy_button)
        self.readiness_button=QPushButton("⚙  Comprobar voz e IA");self.readiness_button.clicked.connect(self.readiness_requested);left.addWidget(self.readiness_button)
        self.tasks_button=QPushButton("≡  Historial de tareas");self.tasks_button.clicked.connect(self.tasks_requested);left.addWidget(self.tasks_button)
        left.addStretch()
        caution=self._small("Privacidad: GAIA solo captura el\nmonitor cuando se lo ordenas.\nNo ejecuta acciones desde imágenes.")
        caution.setWordWrap(True);left.addWidget(caution)
        # Side content must scroll on small laptop displays rather than clip buttons.
        side_scroll=QScrollArea()
        side_scroll.setWidget(side)
        side_scroll.setWidgetResizable(True)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side_scroll.setFixedWidth(250)
        base.addWidget(side_scroll)
        right=QWidget();area=QVBoxLayout(right);area.setContentsMargins(25,25,25,22);area.setSpacing(13)
        title=QLabel("Centro de Control");title.setStyleSheet("font-size:24px;font-weight:700;color:#ecfaff");area.addWidget(title)
        subtitle=self._small("Conversación, visión y estado del equipo · Todo bajo tu control")
        area.addWidget(subtitle)
        self.log=QTextEdit();self.log.setReadOnly(True);self.log.setAcceptRichText(False)
        self.log.setPlaceholderText("Aquí aparecerán tus mensajes y las respuestas de GAIA.")
        self.log.setMinimumHeight(190);area.addWidget(self.log,1)
        area.addWidget(self._title("ANALIZAR PANTALLA (SELECCIÓN EXPLÍCITA)"))
        monitor_row=QHBoxLayout()
        self.displays=QComboBox();self.displays.setMinimumWidth(200)
        self.displays.addItem("Detectar monitores…", "")
        self.vision_button=QPushButton("◉  Analizar pantalla");self.vision_button.setObjectName("vision")
        self.vision_button.clicked.connect(self._request_vision)
        monitor_row.addWidget(self.displays,1);monitor_row.addWidget(self.vision_button)
        area.addLayout(monitor_row)
        self.input=QLineEdit();self.input.setPlaceholderText("Escribe una orden... Ej.: GAIA, ¿qué ves en mi pantalla?")
        self.input.returnPressed.connect(self._submit)
        input_row=QHBoxLayout();input_row.addWidget(self.input,1)
        self.send_button=QPushButton("Enviar ↗");self.send_button.setObjectName("primary");self.send_button.clicked.connect(self._submit)
        input_row.addWidget(self.send_button);area.addLayout(input_row)
        self.feedback=self._small("Ctrl + Espacio: mantener para hablar · Win + Shift + G: abrir GAIA")
        self.feedback.setWordWrap(True);area.addWidget(self.feedback)
        base.addWidget(right,1)
        self.add_message("GAIA", "Listo para recibir órdenes. Si falta Ollama o un modelo, el diagnóstico mostrará cómo instalarlo.")

    @staticmethod
    def _title(text):
        label=QLabel(text);label.setObjectName("sectionTitle");return label
    @staticmethod
    def _small(text):
        label=QLabel(text);label.setObjectName("hint");return label

    def _submit(self):
        text=self.input.text().strip()
        if not text:return
        self.input.clear();self.send_requested.emit(text)

    def _request_vision(self):
        self.vision_requested.emit(str(self.displays.currentData() or ""), "Describe lo que ves en mi pantalla y avísame si hay errores visibles.")

    def set_displays(self, displays):
        previous=self.displays.currentData();self.displays.clear()
        for monitor in displays:
            title=f"{'★ ' if monitor.get('primary') else ''}{monitor['name']} · {monitor['width']}×{monitor['height']}"
            self.displays.addItem(title, monitor['display_id'])
        if not displays:self.displays.addItem("Sin monitores disponibles", "")
        else:
            index=self.displays.findData(previous)
            if index<0:index=next((i for i,d in enumerate(displays) if d.get("primary")),0)
            self.displays.setCurrentIndex(index)

    def set_state(self, state):
        self.state_label.setText("● " + str(state).upper())

    def set_systems(self, *, core=None, chat=None, vision=None, voice=None):
        if core is not None:self.core_state.setText("Core: " + str(core))
        if chat is not None:self.chat_state.setText("Chat/IA: " + str(chat))
        if vision is not None:self.vision_state.setText("Visión: " + str(vision))
        if voice is not None:self.voice_state.setText("Voz: " + str(voice))

    def set_busy(self, busy):
        self.send_button.setEnabled(not busy);self.vision_button.setEnabled(not busy)
        self.input.setEnabled(not busy)

    def add_message(self, sender, message):
        sender=str(sender).strip()[:40]
        message=str(message).strip()[:8000]
        if not message:return
        self.log.moveCursor(__import__("PySide6.QtGui",fromlist=["QTextCursor"]).QTextCursor.End)
        self.log.insertPlainText(f"{sender.upper()}\n{message}\n\n")
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def show_feedback(self, message):
        self.feedback.setText(str(message)[:500])
