"""Interfaz gráfica de escritorio de GAIA v0.4.1, construida con Tkinter."""
from __future__ import annotations
import argparse
import os
import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk, messagebox, simpledialog
from desktop_api import LumenDesktopAPI, LumenAPIError, POLL_SECONDS, record_microphone, play_audio
from action_response import parse_action_response, response_for_display

BG = "#10121a"
PANEL = "#171a25"
TEXT = "#e9eaf2"
MUTED = "#9ca3b7"
ACCENT = "#7c5cff"
GOOD = "#45d19a"
BAD = "#ef6677"


class LumenGUI(tk.Tk):
    def __init__(self, api: LumenDesktopAPI) -> None:
        super().__init__()
        self.api = api
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lumen-gui")
        self.events: queue.Queue[tuple] = queue.Queue()
        self.voice_output = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Core: comprobando...")
        self.backend_var = tk.StringVar(value="LLM: --")
        self.profile_var = tk.StringVar(value=os.getenv("LUMEN_LLM_PROFILE", "auto"))
        self.generation_var = tk.StringVar(value="Listo")
        self.title("GAIA v0.5.3 | Cliente PC")
        self.geometry("960x680")
        self.minsize(760, 520)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._style()
        self._build()
        self.after(100, self._drain_events)
        self._refresh_status()
        self.after(POLL_SECONDS * 1000, self._poll_proactive)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 19))
        style.configure("Accent.TButton", background=ACCENT, foreground="white", padding=(12, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#9077ff")])
        style.configure("Tool.TButton", background=PANEL, foreground=TEXT, padding=(10, 8), borderwidth=0)
        style.map("Tool.TButton", background=[("active", "#242938")])
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])

    def _build(self) -> None:
        header = ttk.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill="x")
        ttk.Label(header, text="G A I A", style="Header.TLabel").pack(side="left")
        indicators = ttk.Frame(header)
        indicators.pack(side="right")
        ttk.Label(indicators, textvariable=self.backend_var, style="Muted.TLabel").pack(anchor="e")
        ttk.Label(indicators, textvariable=self.generation_var, style="Muted.TLabel").pack(anchor="e")
        self.status_label = ttk.Label(indicators, textvariable=self.status_var, style="Muted.TLabel")
        self.status_label.pack(anchor="e")

        toolbar = ttk.Frame(self, padding=(20, 0, 20, 10))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Backup", style="Tool.TButton", command=self._backup).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Memoria", style="Tool.TButton", command=self._open_memory).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Diagnóstico", style="Tool.TButton", command=self._diagnostics).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Probar aviso", style="Tool.TButton", command=self._test_proactive).pack(side="left")
        ttk.Label(toolbar, text="Perfil:").pack(side="right", padx=(10, 4))
        self.profile_combo = ttk.Combobox(toolbar, textvariable=self.profile_var, values=("auto", "fast", "normal", "reasoning", "code"), state="readonly", width=11)
        self.profile_combo.pack(side="right", padx=(0, 8))
        ttk.Checkbutton(toolbar, text="Responder con voz", variable=self.voice_output).pack(side="right")

        chat_panel = tk.Frame(self, bg=PANEL, highlightthickness=0)
        chat_panel.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self.chat = tk.Text(chat_panel, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                            borderwidth=0, relief="flat", padx=18, pady=16, font=("Segoe UI", 11), state="disabled")
        scrollbar = ttk.Scrollbar(chat_panel, command=self.chat.yview)
        self.chat.configure(yscrollcommand=scrollbar.set)
        self.chat.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.chat.tag_configure("user", foreground="#bcaeff", spacing1=10, spacing3=6)
        self.chat.tag_configure("assistant", foreground=TEXT, spacing1=10, spacing3=8)
        self.chat.tag_configure("system", foreground=MUTED, spacing1=10, spacing3=8)
        self._append("system", "GAIA v0.5.3 PC. Streaming activo; memoria jerárquica, RBAC y Action Engine seguro. Qué época para estar vivos.")

        composer = ttk.Frame(self, padding=(20, 0, 20, 18))
        composer.pack(fill="x")
        self.input = tk.Text(composer, height=3, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                             relief="flat", padx=12, pady=10, font=("Segoe UI", 11))
        self.input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input.bind("<Control-Return>", lambda _e: self._send())
        controls = ttk.Frame(composer)
        controls.pack(side="right", fill="y")
        ttk.Button(controls, text="Enviar", style="Accent.TButton", command=self._send).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Detener", style="Tool.TButton", command=self._cancel_generation).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="🎙 Hablar", style="Tool.TButton", command=self._record_and_send).pack(fill="x")
        ttk.Label(composer, text="Ctrl + Enter para enviar", style="Muted.TLabel").place(relx=0, rely=1.05)

    def _run(self, func, on_success=None, on_error=None) -> None:
        future = self.executor.submit(func)
        def done(fut):
            try:
                self.events.put((on_success, fut.result()))
            except Exception as exc:
                self.events.put((on_error or self._show_error, exc))
        future.add_done_callback(done)

    def _drain_events(self) -> None:
        try:
            while True:
                callback, result = self.events.get_nowait()
                if callback:
                    callback(result)
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _append(self, role: str, text: str) -> None:
        label = {"user": "Tú", "assistant": "GAIA", "system": "Sistema"}.get(role, role)
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{label}: ", role)
        self.chat.insert("end", f"{text}\n", role)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _refresh_status(self) -> None:
        self._run(self.api.status, self._set_status, self._set_disconnected)
        self.after(10000, self._refresh_status)

    def _set_status(self, data: dict) -> None:
        llm = data.get("llm", {})
        vault = data.get("vault", {})
        features = data.get("features", {})
        self.status_var.set(f"Core: conectado | Vault: {vault.get('status', '--')} | Action Engine: {'activo' if features.get('action_engine') else 'apagado'}")
        self.backend_var.set(f"LLM: {llm.get('backend', '--')} | {llm.get('status', '--')} | {llm.get('selected_model', llm.get('model', '--'))} | Perfil: {self.profile_var.get()}")
        self.status_label.configure(foreground=GOOD)

    def _set_disconnected(self, _exc: Exception) -> None:
        self.status_var.set("Core: desconectado / token inválido")
        self.backend_var.set("LLM: --")
        self.status_label.configure(foreground=BAD)

    def _send(self) -> None:
        message = self.input.get("1.0", "end").strip()
        if not message:
            return
        self.input.delete("1.0", "end")
        self._append("user", message)
        self.generation_var.set(f"Generando ({self.profile_var.get()})...")
        speak = bool(self.voice_output.get())
        profile = self.profile_var.get()
        self._run(lambda: self.api.send_assistant(message, profile=profile, speak=speak), self._receive_chat)

    def _receive_chat(self, data: dict) -> None:
        self.generation_var.set("Listo" if data.get("kind") != "cancelled" else "Cancelado")
        parsed = parse_action_response(data)
        if parsed and parsed.confirmation_required:
            preview = response_for_display(parsed)
            title = "Confirmar plan | GAIA" if parsed.is_plan else "Confirmar acción | GAIA"
            if messagebox.askyesno(title, preview, parent=self):
                self.generation_var.set("Ejecutando plan confirmado..." if parsed.is_plan else "Ejecutando acción confirmada...")
                self._run(lambda: self.api.confirm_action(data), self._receive_chat)
            else:
                self._run(lambda: self.api.cancel_action(data), lambda _result: self._append("system", "Plan cancelado por el usuario." if parsed.is_plan else "Acción cancelada por el usuario."), self._show_error)
            return
        text = data.get("response", "")
        if text:
            self._append("assistant", text)
        if self.voice_output.get() and text and not data.get("tts_streamed"):
            self._run(lambda: play_audio(self.api.request_tts(text)), None)

    def _cancel_generation(self) -> None:
        self._run(self.api.cancel_generation, lambda _data: self.generation_var.set("Cancelación solicitada"), self._show_error)

    def _record_and_send(self) -> None:
        self._append("system", "Grabando 5 segundos...")
        def task():
            audio = record_microphone(5)
            return self.api.send_voice(audio)
        self._run(task, self._receive_voice)

    def _receive_voice(self, data: dict) -> None:
        self._append("user", f"[voz] {data.get('user_text', '')}")
        parsed = parse_action_response(data)
        if parsed and parsed.confirmation_required:
            self._receive_chat(data)
            return
        self._append("assistant", data.get("response", ""))
        if data.get("tts_error"):
            self._append("system", f"Texto recibido, pero TTS falló: {data['tts_error']}")
        if self.voice_output.get() and data.get("audio_url"):
            self._run(lambda: play_audio(self.api.download_audio(data["audio_url"])), None)

    def _backup(self) -> None:
        self._run(self.api.backup, lambda data: self._append("system", f"Backup creado: {data['path']}"))

    def _test_proactive(self) -> None:
        self._run(self.api.enqueue_test_message, lambda _d: self._append("system", "Mensaje proactivo encolado; se recogerá por polling."))
        self.after(800, self._poll_proactive)

    def _poll_proactive(self) -> None:
        def received(data: dict) -> None:
            if data.get("has_message"):
                message = data.get("message", "")
                self._append("assistant", f"[proactiva] {message}")
                if self.voice_output.get():
                    self._run(lambda: play_audio(self.api.request_tts(message)), None)
        self._run(self.api.poll_proactive, received, lambda _e: None)
        self.after(POLL_SECONDS * 1000, self._poll_proactive)

    def _diagnostics(self) -> None:
        self._run(self.api.diagnostics, self._show_diagnostics)

    def _show_diagnostics(self, data: dict) -> None:
        sections = ("core", "database", "vault", "ollama", "voice", "action_engine", "devices")
        text = "\n".join(f"{section}: {data.get(section, {})}" for section in sections)
        messagebox.showinfo("Diagnóstico seguro | GAIA", text, parent=self)

    def _open_memory(self) -> None:
        self._run(self.api.facts, self._memory_window)

    def _memory_window(self, facts: list[dict]) -> None:
        window = tk.Toplevel(self)
        window.title("Memoria y continuidad | GAIA")
        window.geometry("760x520")
        window.configure(bg=BG)
        search_row = ttk.Frame(window, padding=(16, 12, 16, 4))
        search_row.pack(fill="x")
        query = tk.StringVar()
        ttk.Entry(search_row, textvariable=query).pack(side="left", fill="x", expand=True, padx=(0, 8))
        listbox = tk.Listbox(window, bg=PANEL, fg=TEXT, selectbackground=ACCENT, borderwidth=0, font=("Segoe UI", 10))
        listbox.pack(fill="both", expand=True, padx=16, pady=(8, 8))
        def render(items: list[dict]) -> None:
            listbox.delete(0, "end")
            for item in items:
                if "task" in item:
                    listbox.insert("end", f"TAREA #{item.get('id')}: {item.get('task')}")
                else:
                    listbox.insert("end", f"#{item.get('id')}  [{item.get('category')}] {item.get('fact')}  ({item.get('source', 'search')})")
        render(facts)
        def search() -> None:
            text = query.get().strip()
            if text:
                self._run(lambda: self.api.search_memories(text), render)
            else:
                render(facts)
        ttk.Button(search_row, text="Buscar", style="Accent.TButton", command=search).pack(side="right")
        task_row = ttk.Frame(window, padding=(16, 0, 16, 6))
        task_row.pack(fill="x")
        ttk.Button(task_row, text="Mostrar tareas abiertas", style="Tool.TButton", command=lambda: self._run(self.api.open_tasks, render)).pack(side="left")
        buttons = ttk.Frame(window, padding=(16, 0, 16, 16))
        buttons.pack(fill="x")
        def add():
            category = simpledialog.askstring("Categoría", "Categoría del fact:", parent=window)
            if not category:
                return
            fact = simpledialog.askstring("Fact", "Dato que GAIA debe guardar:", parent=window)
            if fact:
                self._run(lambda: self.api.add_fact(category, fact), lambda _x: (window.destroy(), self._open_memory()))
        def delete():
            selected = listbox.curselection()
            if not selected:
                return
            fact_id = facts[selected[0]]["id"]
            self._run(lambda: self.api.delete_fact(fact_id), lambda _x: (window.destroy(), self._open_memory()))
        ttk.Button(buttons, text="Agregar manual", style="Accent.TButton", command=add).pack(side="left")
        ttk.Button(buttons, text="Eliminar seleccionado", style="Tool.TButton", command=delete).pack(side="left", padx=8)
        ttk.Label(buttons, text="Auto-extracción desactivada por defecto", style="Muted.TLabel").pack(side="right")

    def _show_error(self, exc: Exception) -> None:
        self._append("system", f"Error: {exc}")

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="GAIA GUI PC")
    parser.add_argument("--url", default=None, help="URL del Core")
    parser.add_argument("--token", default=None, help="Token local (mejor configurar .env)")
    parser.add_argument("--check", action="store_true", help="Valida importación de la GUI sin abrir ventana")
    args = parser.parse_args()
    if args.check:
        print("GUI IMPORT OK")
        return
    defaults = LumenDesktopAPI()
    api = LumenDesktopAPI(args.url or defaults.base_url, args.token or defaults.secret)
    LumenGUI(api).mainloop()


if __name__ == "__main__":
    main()
