"""Interfaz gráfica de escritorio de GAIA v0.4.1, construida con Tkinter."""
from __future__ import annotations
import argparse
import os
import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk, messagebox, simpledialog, filedialog
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
        self._generation_busy = False
        self.title("GAIA v1.0-RC6 | Cliente PC")
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
        ttk.Button(toolbar, text="Permisos", style="Tool.TButton", command=self._open_permissions).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Aplicaciones", style="Tool.TButton", command=self._open_apps).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Carpetas", style="Tool.TButton", command=self._open_folders).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Emparejar Android", style="Tool.TButton", command=self._start_pairing).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Diagnóstico", style="Tool.TButton", command=self._diagnostics).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Automatizaciones", style="Tool.TButton", command=self._open_automations).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="DETENER ACCIONES", style="Tool.TButton", command=self._kill_actions).pack(side="left", padx=(0, 8))
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
        self._append("system", "GAIA v1.0-RC6 PC. Verdad antes que personalidad; automatizaciones acotadas, eventos como datos, permisos explícitos y Action Host con preflight. Qué época para automatizar con límites.")

        composer = ttk.Frame(self, padding=(20, 0, 20, 18))
        composer.pack(fill="x")
        self.input = tk.Text(composer, height=3, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                             relief="flat", padx=12, pady=10, font=("Segoe UI", 11))
        self.input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input.bind("<Control-Return>", lambda _e: self._send())
        controls = ttk.Frame(composer)
        controls.pack(side="right", fill="y")
        self.send_button = ttk.Button(controls, text="Enviar", style="Accent.TButton", command=self._send)
        self.send_button.pack(fill="x", pady=(0, 6))
        self.stop_button = ttk.Button(controls, text="Detener", style="Tool.TButton", command=self._cancel_generation)
        self.stop_button.pack(fill="x", pady=(0, 6))
        self.voice_button = ttk.Button(controls, text="🎙 Hablar", style="Tool.TButton", command=self._record_and_send)
        self.voice_button.pack(fill="x")
        self._set_generation_busy(False)
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

    def _set_generation_busy(self, busy: bool) -> None:
        self._generation_busy = bool(busy)
        state = "disabled" if busy else "normal"
        for button_name in ("send_button", "voice_button"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.configure(state=state)
        stop_button = getattr(self, "stop_button", None)
        if stop_button is not None:
            stop_button.configure(state="normal" if busy else "disabled")

    def _generation_error(self, exc: Exception) -> None:
        self._set_generation_busy(False)
        self.generation_var.set("Error")
        self._show_error(exc)

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
        if self._generation_busy:
            self._append("system", "Ya hay una generación en curso. Dos Qwen simultáneos en esta laptop sería una forma creativa de tortura térmica.")
            return
        message = self.input.get("1.0", "end").strip()
        if not message:
            return
        self.input.delete("1.0", "end")
        self._append("user", message)
        self._set_generation_busy(True)
        self.generation_var.set(f"Generando ({self.profile_var.get()})...")
        speak = bool(self.voice_output.get())
        profile = self.profile_var.get()
        self._run(lambda: self.api.send_assistant(message, profile=profile, speak=speak), self._receive_chat, self._generation_error)

    def _receive_chat(self, data: dict) -> None:
        self.generation_var.set("Cancelado" if data.get("kind") == "cancelled" else "Listo")
        parsed = parse_action_response(data)
        if parsed and parsed.confirmation_required:
            self.generation_var.set("Esperando decisión de permisos...")
            decision = self._permission_dialog(data, parsed)
            if decision == "CANCEL":
                self._run(lambda: self.api.cancel_action(data), self._receive_chat, self._generation_error)
            else:
                self.generation_var.set("Ejecutando plan autorizado..." if parsed.is_plan else "Ejecutando acción autorizada...")
                persistent = decision if decision in {"ALLOW_ONCE", "ALWAYS_ALLOW"} else None
                if persistent:
                    self._run(lambda: self.api.confirm_action(data, permission_decision=persistent), self._receive_chat, self._generation_error)
                else:
                    self._run(lambda: self.api.confirm_action(data), self._receive_chat, self._generation_error)
            return
        self._set_generation_busy(False)
        text = data.get("response", "")
        if text:
            self._append("assistant", text)
        if self.voice_output.get() and text and not data.get("tts_streamed"):
            self._run(lambda: play_audio(self.api.request_tts(text)), None)

    def _permission_dialog(self, data: dict, parsed) -> str:
        options = data.get("confirmation_options") or {}
        if "tk" not in object.__getattribute__(self, "__dict__"):
            title = "Confirmar plan | GAIA" if parsed.is_plan else "Confirmar acción | GAIA"
            return "CONFIRM_ONCE" if messagebox.askyesno(title, response_for_display(parsed), parent=self) else "CANCEL"
        raw = data.get("plan") if parsed.is_plan else data.get("action")
        items = raw.get("actions", []) if isinstance(raw, dict) and parsed.is_plan else [raw or {}]
        permission_entries = data.get("permission_entries")
        permission_entries = [entry for entry in permission_entries if isinstance(entry, dict)] if isinstance(permission_entries, list) else []
        scope_lines = []
        for entry in permission_entries:
            description = str(entry.get("human_scope_description") or "scope estructurado no descrito")[:300]
            exact_scope = str(entry.get("resource_scope") or "")[:240]
            scope_lines.append(f"{description} [{exact_scope or 'no resuelto'}]")
        scope = "\n".join(scope_lines) if scope_lines else "Core no entregó un scope de permiso autoritativo."
        risk = max((int(item.get("risk_level", 0)) for item in items if isinstance(item, dict)), default=0)
        dialog = tk.Toplevel(self)
        dialog.title("Permisos | GAIA")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("620x360")
        dialog.configure(bg=BG)
        result = {"decision": "CANCEL"}
        ttk.Label(dialog, text="GAIA necesita una decisión de permiso", style="Header.TLabel").pack(anchor="w", padx=20, pady=(18, 8))
        body = f"{response_for_display(parsed)}\n\nRiesgo máximo: {risk}\nScope mostrado: {scope}\n\nPermitir siempre solo guarda esta capability y este scope; no concede comandos arbitrarios."
        text = tk.Text(dialog, wrap="word", height=10, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", padx=12, pady=12, font=("Segoe UI", 10), state="normal")
        text.insert("1.0", body)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=20, pady=(0, 18))
        def choose(value: str) -> None:
            result["decision"] = value
            dialog.destroy()
        if options.get("allow_once", True):
            ttk.Button(buttons, text="PERMITIR UNA VEZ", style="Accent.TButton", command=lambda: choose("ALLOW_ONCE")).pack(side="left", padx=(0, 8))
        if options.get("allow_always", False):
            ttk.Button(buttons, text="PERMITIR SIEMPRE", style="Accent.TButton", command=lambda: choose("ALWAYS_ALLOW")).pack(side="left", padx=(0, 8))
        confirm_label = "CONFIRMAR" if risk >= 3 or not options.get("allow_once", True) else "EJECUTAR UNA VEZ"
        ttk.Button(buttons, text=confirm_label, style="Tool.TButton", command=lambda: choose("CONFIRM_ONCE")).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="CANCELAR", style="Tool.TButton", command=lambda: choose("CANCEL")).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", lambda: choose("CANCEL"))
        self.wait_window(dialog)
        return str(result["decision"])

    def _cancel_generation(self) -> None:
        self._run(self.api.cancel_generation, lambda _data: self.generation_var.set("Cancelación solicitada"), self._show_error)

    def _record_and_send(self) -> None:
        if self._generation_busy:
            self._append("system", "Ya hay una generación en curso; no voy a alimentar dos inferencias pesadas a la vez.")
            return
        self._set_generation_busy(True)
        self.generation_var.set("Generando voz...")
        self._append("system", "Grabando 5 segundos...")
        def task():
            audio = record_microphone(5)
            return self.api.send_voice(audio)
        self._run(task, self._receive_voice, self._generation_error)

    def _receive_voice(self, data: dict) -> None:
        self._set_generation_busy(False)
        self.generation_var.set("Listo")
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

    def _start_pairing(self) -> None:
        self._run(self.api.start_pairing, self._show_pairing, self._show_error)

    def _show_pairing(self, data: dict) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Emparejar Android | GAIA")
        dialog.transient(self)
        dialog.geometry("760x470")
        dialog.configure(bg=BG)
        ttk.Label(dialog, text="Conectar a GAIA", style="Header.TLabel").pack(anchor="w", padx=20, pady=(20, 8))
        pairing_id = str(data.get("pairing_id", ""))
        code = str(data.get("code", ""))
        pairing_uri = str(data.get("pairing_uri") or data.get("qr_payload") or "").strip()
        body = (
            "En Android pulsa ‘Escanear QR’ y escanea el QR que codifique el URI siguiente, "
            "o pega ese URI en el campo de pairing. También puedes usar los datos manuales.\n\n"
            f"Pairing ID: {pairing_id}\n"
            f"Código de un solo uso: {code}\n"
            f"Expira: {data.get('expires_at', 'TTL configurado')}\n\n"
            "La sesión solo puede usarse una vez. No compartas este URI fuera de tu red confiable."
        )
        text = tk.Text(dialog, height=9, wrap="word", bg=PANEL, fg=TEXT, relief="flat", padx=12, pady=12, font=("Segoe UI", 10))
        text.insert("1.0", body)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        ttk.Label(dialog, text="URI de pairing / contenido del QR", style="Muted.TLabel").pack(anchor="w", padx=20, pady=(0, 4))
        uri_frame = ttk.Frame(dialog)
        uri_frame.pack(fill="x", padx=20, pady=(0, 14))
        uri_var = tk.StringVar(value=pairing_uri)
        uri_entry = ttk.Entry(uri_frame, textvariable=uri_var)
        uri_entry.pack(side="left", fill="x", expand=True)
        def copy_uri() -> None:
            if not pairing_uri:
                return
            self.clipboard_clear()
            self.clipboard_append(pairing_uri)
            self.update()
        ttk.Button(uri_frame, text="Copiar", command=copy_uri).pack(side="left", padx=(8, 0))
        ttk.Button(dialog, text="Cerrar", style="Accent.TButton", command=dialog.destroy).pack(anchor="e", padx=20, pady=(0, 18))

    def _kill_actions(self) -> None:
        self._run(self.api.kill_switch, lambda data: self._append("system", f"Acciones detenidas. Pending canceladas: {data.get('pending_cancelled', 0)}."), self._show_error)

    def _open_permissions(self) -> None:
        self._run(self.api.list_permissions, self._permissions_window)

    def _permissions_window(self, permissions: list[dict]) -> None:
        window = tk.Toplevel(self)
        window.title("Permisos | GAIA")
        window.geometry("900x520")
        window.configure(bg=BG)
        listbox = tk.Listbox(window, bg=PANEL, fg=TEXT, selectbackground=ACCENT, borderwidth=0, font=("Segoe UI", 10))
        listbox.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        current = list(permissions)
        def render() -> None:
            listbox.delete(0, "end")
            for item in current:
                listbox.insert("end", f"{item.get('decision')} | {item.get('capability')} | scope={item.get('resource_scope') or '*'} | device={item.get('device_id')} | risk={item.get('risk_level_at_grant')}")
        def selected() -> dict | None:
            indexes = listbox.curselection()
            return current[indexes[0]] if indexes and indexes[0] < len(current) else None
        def refresh(_result=None) -> None:
            self._run(self.api.list_permissions, lambda data: (current.clear(), current.extend(data), render()))
        def change(decision: str) -> None:
            item = selected()
            if not item:
                return
            self._run(lambda: self.api.grant_permission(str(item.get("capability")), str(item.get("resource_scope") or ""), decision, int(item.get("risk_level_at_grant", 0)), str(item.get("device_id") or "pc-main")), refresh, self._show_error)
        def revoke() -> None:
            item = selected()
            if not item:
                return
            self._run(lambda: self.api.revoke_permission(str(item.get("capability")), str(item.get("resource_scope") or ""), str(item.get("device_id") or "pc-main")), refresh, self._show_error)
        render()
        controls = ttk.Frame(window)
        controls.pack(fill="x", padx=16, pady=(0, 16))
        ttk.Button(controls, text="Permitir siempre", style="Accent.TButton", command=lambda: change("ALWAYS_ALLOW")).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Preguntar siempre", style="Tool.TButton", command=lambda: change("ALWAYS_ASK")).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Denegar siempre", style="Tool.TButton", command=lambda: change("ALWAYS_DENY")).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Revocar", style="Tool.TButton", command=revoke).pack(side="right")

    def _open_apps(self) -> None:
        self._run(lambda: self.api.discovered_apps(force_refresh=True), self._apps_window, self._show_error)

    def _apps_window(self, apps: list[dict]) -> None:
        window = tk.Toplevel(self)
        window.title("Aplicaciones descubiertas | GAIA")
        window.geometry("1040x560")
        window.configure(bg=BG)
        current = list(apps)
        listbox = tk.Listbox(window, bg=PANEL, fg=TEXT, selectbackground=ACCENT, borderwidth=0, font=("Segoe UI", 10))
        listbox.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        def render() -> None:
            listbox.delete(0, "end")
            for item in current:
                state = "TRUSTED" if item.get("trusted") else ("BLOCKED" if item.get("blocked") else "DISCOVERED")
                mode = str(item.get("trust_mode") or "")
                remaining = item.get("uses_remaining")
                suffix = f" | {mode}:{remaining}" if mode == "ONCE" else ""
                listbox.insert("end", f"{state}{suffix} | {item.get('display_name') or item.get('canonical_name')} | {item.get('source')} | {item.get('app_id')}")

        def selected() -> dict | None:
            indexes = listbox.curselection()
            return current[indexes[0]] if indexes and indexes[0] < len(current) else None

        def refresh(_result=None) -> None:
            self._run(lambda: self.api.discovered_apps(force_refresh=True), lambda rows: (current.clear(), current.extend(rows), render()), self._show_error)

        def trust(decision: str) -> None:
            item = selected()
            if not item or not str(item.get("app_id", "")).startswith("discovered:"):
                return
            self._run(lambda: self.api.set_app_trust(str(item["app_id"]), decision), refresh, self._show_error)

        def revoke() -> None:
            item = selected()
            if not item or not str(item.get("app_id", "")).startswith("discovered:"):
                return
            self._run(lambda: self.api.revoke_app_trust(str(item["app_id"])), refresh, self._show_error)

        render()
        controls = ttk.Frame(window)
        controls.pack(fill="x", padx=16, pady=(0, 16))
        ttk.Button(controls, text="Permitir una vez", style="Accent.TButton", command=lambda: trust("ALLOW_ONCE")).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Permitir siempre", style="Accent.TButton", command=lambda: trust("ALWAYS_ALLOW")).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Bloquear", style="Tool.TButton", command=lambda: trust("BLOCK")).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Revocar trust", style="Tool.TButton", command=revoke).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Actualizar", style="Tool.TButton", command=refresh).pack(side="right")

    def _open_folders(self) -> None:
        self._run(self.api.trusted_folders, self._folders_window, self._show_error)

    def _folders_window(self, folders: list[dict]) -> None:
        window = tk.Toplevel(self)
        window.title("Trusted Folders | GAIA")
        window.geometry("1120x600")
        window.configure(bg=BG)
        current = list(folders)
        listbox = tk.Listbox(window, bg=PANEL, fg=TEXT, selectbackground=ACCENT, borderwidth=0, font=("Segoe UI", 10))
        listbox.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        def render() -> None:
            listbox.delete(0, "end")
            for item in current:
                state = str(item.get("state") or ("TRUSTED" if item.get("trusted") else "DISCOVERED"))
                rights = ",".join(item.get("rights") or []) or "sin derechos"
                listbox.insert("end", f"{state} | {rights} | {item.get('label')} | {item.get('path')}")

        def selected() -> dict | None:
            indexes = listbox.curselection()
            return current[indexes[0]] if indexes and indexes[0] < len(current) else None

        def refresh(_result=None) -> None:
            self._run(self.api.trusted_folders, lambda rows: (current.clear(), current.extend(rows), render()), self._show_error)

        def rights_prompt(default: str = "READ,OPEN") -> list[str] | None:
            raw = simpledialog.askstring("Derechos explícitos", "READ, OPEN, CREATE, WRITE, COPY_FROM, COPY_TO, MOVE_FROM, MOVE_TO, RENAME, DELETE", initialvalue=default, parent=window)
            if raw is None:
                return None
            return sorted({part.strip().upper() for part in raw.split(",") if part.strip()})

        def add() -> None:
            path = filedialog.askdirectory(parent=window, title="Selecciona una carpeta; no se concede trust automáticamente")
            if not path:
                return
            rights = rights_prompt()
            if rights is None:
                return
            self._run(lambda: self.api.grant_trusted_folder(path, rights=rights), refresh, self._show_error)

        def edit() -> None:
            item = selected()
            if not item:
                return
            rights = rights_prompt(",".join(item.get("rights") or ["READ", "OPEN"]))
            if rights is None:
                return
            self._run(lambda: self.api.update_trusted_folder(str(item["folder_id"]), rights=rights, trusted=True), refresh, self._show_error)

        def disable() -> None:
            item = selected()
            if item:
                self._run(lambda: self.api.update_trusted_folder(str(item["folder_id"]), trusted=False), refresh, self._show_error)

        def enable() -> None:
            item = selected()
            if item:
                self._run(lambda: self.api.update_trusted_folder(str(item["folder_id"]), rights=item.get("rights") or ["READ", "OPEN"], trusted=True), refresh, self._show_error)

        def revoke() -> None:
            item = selected()
            if item:
                self._run(lambda: self.api.revoke_trusted_folder(str(item["folder_id"])), refresh, self._show_error)

        render()
        controls = ttk.Frame(window)
        controls.pack(fill="x", padx=16, pady=(0, 16))
        ttk.Button(controls, text="Agregar carpeta", style="Accent.TButton", command=add).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Editar derechos", style="Tool.TButton", command=edit).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Habilitar", style="Tool.TButton", command=enable).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Deshabilitar", style="Tool.TButton", command=disable).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Revocar", style="Tool.TButton", command=revoke).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Actualizar", style="Tool.TButton", command=refresh).pack(side="right")

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

    def _open_automations(self) -> None:
        def load() -> dict:
            return {"status": self.api.automation_status(), "rules": self.api.automations().get("automations", []), "notifications": self.api.notifications().get("notifications", [])}
        self._run(load, self._automations_window, self._show_error)

    def _automations_window(self, snapshot: dict) -> None:
        window = tk.Toplevel(self)
        window.title("Automatizaciones y notificaciones | GAIA")
        window.geometry("1060x650")
        window.configure(bg=BG)
        status = snapshot.get("status", {}).get("automation", {}) if isinstance(snapshot.get("status"), dict) else {}
        rules = list(snapshot.get("rules") or [])
        notifications = list(snapshot.get("notifications") or [])
        mode_var = tk.StringVar(value=str(status.get("mode") or "OFF"))
        pause_var = tk.StringVar(value="PAUSAR" if not status.get("paused") else "REANUDAR")
        status_var = tk.StringVar(value=f"Modo: {mode_var.get()} | {'PAUSADO' if status.get('paused') else 'ACTIVO'}")

        top = ttk.Frame(window, padding=(16, 14, 16, 8))
        top.pack(fill="x")
        ttk.Label(top, textvariable=status_var, style="Header.TLabel").pack(side="left")
        ttk.Label(top, text="El kill switch siempre gana a las reglas.", style="Muted.TLabel").pack(side="left", padx=18)
        controls = ttk.Frame(window, padding=(16, 0, 16, 10))
        controls.pack(fill="x")
        ttk.Label(controls, text="Modo:").pack(side="left")
        mode_combo = ttk.Combobox(controls, textvariable=mode_var, values=("OFF", "NOTIFY_ONLY", "ROUTINES", "FULL_CONFIGURED"), state="readonly", width=18)
        mode_combo.pack(side="left", padx=(8, 8))
        rules_list = tk.Listbox(window, bg=PANEL, fg=TEXT, selectbackground=ACCENT, borderwidth=0, font=("Segoe UI", 10), height=9)
        rules_list.pack(fill="x", padx=16, pady=(0, 8))
        notes_list = tk.Listbox(window, bg=PANEL, fg=TEXT, selectbackground=ACCENT, borderwidth=0, font=("Segoe UI", 10))
        notes_list.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        def render() -> None:
            rules_list.delete(0, "end")
            for item in rules:
                state = "ON" if item.get("enabled") else "OFF"
                trigger = (item.get("trigger") or {}).get("event_type", "evento") if isinstance(item.get("trigger"), dict) else "evento"
                rules_list.insert("end", f"{state} | {item.get('name', 'Regla')} | {trigger} | owner={item.get('owner_device', '')}")
            notes_list.delete(0, "end")
            for item in notifications:
                notes_list.insert("end", f"{item.get('severity', 'info').upper()} | {item.get('title', 'GAIA')} | {item.get('message', '')[:260]}")

        def refresh(_result=None) -> None:
            self._run(lambda: {"status": self.api.automation_status(), "rules": self.api.automations().get("automations", []), "notifications": self.api.notifications().get("notifications", [])}, update, self._show_error)

        def update(data: dict) -> None:
            nonlocal status
            status = data.get("status", {}).get("automation", {}) if isinstance(data.get("status"), dict) else {}
            rules[:] = list(data.get("rules") or [])
            notifications[:] = list(data.get("notifications") or [])
            mode_var.set(str(status.get("mode") or "OFF"))
            pause_var.set("REANUDAR" if status.get("paused") else "PAUSAR")
            status_var.set(f"Modo: {mode_var.get()} | {'PAUSADO' if status.get('paused') else 'ACTIVO'}")
            render()

        def apply_mode() -> None:
            self._run(lambda: self.api.set_automation_mode(mode_var.get()), refresh, self._show_error)

        def toggle_pause() -> None:
            paused = bool(status.get("paused"))
            self._run(lambda: self.api.pause_automation(not paused), refresh, self._show_error)

        def toggle_rule() -> None:
            indexes = rules_list.curselection()
            if not indexes or indexes[0] >= len(rules):
                return
            item = rules[indexes[0]]
            self._run(lambda: self.api.set_rule_enabled(str(item.get("rule_id")), not bool(item.get("enabled"))), refresh, self._show_error)

        def dismiss_notification() -> None:
            indexes = notes_list.curselection()
            if not indexes or indexes[0] >= len(notifications):
                return
            item = notifications[indexes[0]]
            self._run(lambda: self.api.dismiss_notification(str(item.get("notification_id"))), refresh, self._show_error)

        ttk.Button(controls, text="Aplicar modo", style="Accent.TButton", command=apply_mode).pack(side="left", padx=(0, 8))
        ttk.Button(controls, textvariable=pause_var, style="Tool.TButton", command=toggle_pause).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Activar/desactivar regla", style="Tool.TButton", command=toggle_rule).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Actualizar", style="Tool.TButton", command=refresh).pack(side="right")
        ttk.Label(window, text="REGLAS", style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 4))
        ttk.Label(window, text="NOTIFICACIONES PENDIENTES", style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 4))
        ttk.Button(window, text="Marcar notificación seleccionada como leída", style="Tool.TButton", command=dismiss_notification).pack(anchor="e", padx=16, pady=(0, 14))
        render()

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
        if self._generation_busy:
            self._set_generation_busy(False)
            self.generation_var.set("Error")

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
