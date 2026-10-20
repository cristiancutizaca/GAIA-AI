import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:audioplayers/audioplayers.dart';
import '../services/lumen_service.dart';
import 'settings_screen.dart';
import 'pairing_screen.dart';

class ChatMessage {
  String text;
  final bool isUser;
  final DateTime timestamp;
  final String? audioUrl;

  ChatMessage({
    required this.text,
    required this.isUser,
    DateTime? timestamp,
    this.audioUrl,
  }) : timestamp = timestamp ?? DateTime.now();
}

class ChatScreen extends StatefulWidget {
  final LumenService? lumen;
  const ChatScreen({super.key, this.lumen});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late final LumenService _lumen;
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final List<ChatMessage> _messages = [];

  bool _isLoading = false;
  bool _isConnected = false;
  bool _autoVoice = true;
  bool _isRecording = false;
  String _recordPath = '';
  final AudioRecorder _recorder = AudioRecorder();
  String _profile = 'auto';
  Timer? _proactiveTimer;
  Timer? _reconnectTimer;
  int _reconnectAttempt = 0;

  @override
  void initState() {
    super.initState();
    _lumen = widget.lumen ?? LumenService();
    _initialize();
  }

  Future<void> _initialize() async {
    await _lumen.loadSavedConfig();
    if (!mounted) return;
    await _checkConnection();
    _startProactiveCheck();
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _audioPlayer.dispose();
    _recorder.dispose();
    _proactiveTimer?.cancel();
    _reconnectTimer?.cancel();
    super.dispose();
  }

  Future<void> _checkConnection() async {
    final connected = await _lumen.testConnection();
    if (!mounted) return;
    setState(() => _isConnected = connected);
    if (connected) {
      _reconnectAttempt = 0;
      _reconnectTimer?.cancel();
    }

    if (!connected && _lumen.secret.trim().isEmpty) {
      _addMessage(ChatMessage(
        text: 'El token expiró o fue revocado. Te devuelvo al pairing para conectar de nuevo sin reutilizar el secreto anterior.',
        isUser: false,
      ));
      await Future<void>.delayed(const Duration(milliseconds: 250));
      if (mounted) Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => PairingScreen(lumen: _lumen)));
      return;
    }
    if (!connected) {
      _addMessage(ChatMessage(
        text: 'No puedo conectar con el Core. Verifica que esté corriendo y la IP sea correcta.',
        isUser: false,
      ));
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (!mounted || _reconnectAttempt >= 4 || (_reconnectTimer?.isActive ?? false)) return;
    final attempt = _reconnectAttempt++;
    final baseSeconds = (5 * (1 << attempt)).clamp(5, 60).toInt();
    final jitterMs = DateTime.now().millisecond % 750;
    _reconnectTimer = Timer(Duration(seconds: baseSeconds, milliseconds: jitterMs), () {
      if (mounted) _checkConnection();
    });
  }

  void _startProactiveCheck() {
    _proactiveTimer = Timer.periodic(
      const Duration(minutes: 5),
      (_) => _checkProactive(),
    );
  }

  Future<void> _checkProactive() async {
    try {
      final data = await _lumen.checkProactive();
      if (data != null && data['message'] != null) {
        _addMessage(ChatMessage(text: data['message'], isUser: false));
        if (_autoVoice) {
          await _playVoice(data['message']);
        }
      }
    } catch (_) {}
  }

  void _addMessage(ChatMessage msg) {
    setState(() => _messages.add(msg));
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isLoading) return;

    _textController.clear();
    _addMessage(ChatMessage(text: text, isUser: true));
    final assistant = ChatMessage(text: '', isUser: false);
    _addMessage(assistant);
    setState(() => _isLoading = true);
    final buffer = StringBuffer();
    String? pendingActionId;
    String? pendingActionSessionId;
    String? pendingActionPreview;
    Map<String, dynamic>? pendingPermissionOptions;
    List<Map<String, dynamic>> pendingPermissionEntries = <Map<String, dynamic>>[];
    bool pendingRequiresConfirmation = true;
    String pendingTargetHost = 'pc-main';

    try {
      await for (final event in _lumen.streamMessage(text, profile: _profile)) {
        final type = event['event'];
        if (type == 'token') {
          buffer.write(event['text'] ?? '');
          setState(() => assistant.text = buffer.toString());
        } else if (type == 'action') {
          final preview = event['preview'] ?? 'Acción validada pendiente de ejecución en el dispositivo correspondiente.';
          pendingActionId = event['action_id']?.toString();
          pendingActionSessionId = event['session_id']?.toString() ?? _lumen.sessionId;
          pendingActionPreview = preview.toString();
          pendingPermissionOptions = event['confirmation_options'] is Map ? Map<String, dynamic>.from(event['confirmation_options']) : null;
          pendingPermissionEntries = event['permission_entries'] is List
              ? (event['permission_entries'] as List).whereType<Map>().map((entry) => Map<String, dynamic>.from(entry)).toList()
              : <Map<String, dynamic>>[];
          pendingRequiresConfirmation = event['confirmation_required'] != false;
          pendingTargetHost = event['target_host']?.toString() ?? 'pc-main';
          buffer.write(preview);
          setState(() => assistant.text = buffer.toString());
        } else if (type == 'error' || type == 'cancelled') {
          buffer.write(event['detail'] ?? 'Generación cancelada.');
          setState(() => assistant.text = buffer.toString());
        }
      }
      if (assistant.text.trim().isEmpty) {
        setState(() => assistant.text = 'GAIA no devolvió texto visible.');
      }
      if (pendingActionId != null && pendingActionSessionId != null && mounted) {
        await _handleRemoteAction(assistant, pendingActionId!, pendingActionSessionId!, pendingActionPreview ?? assistant.text, pendingPermissionOptions ?? const {}, permissionEntries: pendingPermissionEntries, requiresConfirmation: pendingRequiresConfirmation, targetHost: pendingTargetHost);
      }
      if (_autoVoice && assistant.text.trim().isNotEmpty) {
        await _playVoice(assistant.text);
      }
    } catch (e) {
      setState(() => assistant.text = 'No pude conectar con GAIA. El Core puede seguir funcionando; revisa la red LAN y el token.');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _handleRemoteAction(ChatMessage assistant, String actionId, String actionSessionId, String preview, Map<String, dynamic> options, {List<Map<String, dynamic>> permissionEntries = const <Map<String, dynamic>>[], required bool requiresConfirmation, required String targetHost}) async {
    if (!requiresConfirmation) {
      if (mounted) setState(() => assistant.text = '${assistant.text}\n\nEjecutando en $targetHost; el resultado llegará como VerifiedActionResult.');
      return;
    }
    await _confirmRemoteAction(assistant, actionId, actionSessionId, preview, options, permissionEntries);
  }

  Future<void> _confirmRemoteAction(ChatMessage assistant, String actionId, String actionSessionId, String preview, Map<String, dynamic> options, List<Map<String, dynamic>> permissionEntries) async {
    final scopeText = permissionEntries.map((entry) {
      final description = entry['human_scope_description']?.toString() ?? 'Scope estructurado';
      final scope = entry['resource_scope']?.toString() ?? 'no resuelto';
      return '$description [$scope]';
    }).join('\n');
    final decision = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Permiso para acción remota'),
        content: Text('$preview\n\n${scopeText.isEmpty ? 'El Core no entregó un scope persistente; solo se permite confirmación puntual.' : 'Scopes autorizados por Core:\n$scopeText'}\n\nEl PC Action Host ejecutará la capability y devolverá un resultado verificado. Android no concede comandos arbitrarios.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, 'CANCEL'), child: const Text('Cancelar')),
          if (options['allow_always'] == true) TextButton(onPressed: () => Navigator.pop(dialogContext, 'ALWAYS_ALLOW'), child: const Text('Permitir siempre')),
          if (options['allow_once'] != false) FilledButton(onPressed: () => Navigator.pop(dialogContext, 'ALLOW_ONCE'), child: const Text('Permitir una vez')),
          if (options['allow_always'] != true && options['allow_once'] == false) FilledButton(onPressed: () => Navigator.pop(dialogContext, 'CONFIRM_ONCE'), child: const Text('Confirmar')),
        ],
      ),
    ) ?? 'CANCEL';
    final approved = decision != 'CANCEL';
    try {
      final result = approved
          ? await _lumen.approveAction(actionId, actionSessionId, decision: decision == 'ALLOW_ONCE' || decision == 'ALWAYS_ALLOW' ? decision : null)
          : await _lumen.rejectAction(actionId, actionSessionId);
      if (!mounted) return;
      setState(() => assistant.text = '${assistant.text}\n\n${approved ? 'Aprobada para el PC Action Host (${decision == 'ALWAYS_ALLOW' ? 'permitir siempre' : decision == 'ALLOW_ONCE' ? 'una vez' : 'confirmación puntual'}).' : 'Rechazada; no se ejecutará.'}');
      if (approved && result['status'] != 'approved') {
        setState(() => assistant.text = '${assistant.text}\nLa aprobación no quedó registrada.');
      }
    } catch (_) {
      if (mounted) setState(() => assistant.text = '${assistant.text}\nNo pude registrar la decisión remota.');
    }
  }

  Future<void> _startRecording() async {
    if (_isLoading || _isRecording) return;
    final permission = await Permission.microphone.request();
    if (!permission.isGranted) {
      if (mounted) _addMessage(ChatMessage(text: 'Necesito permiso de micrófono para el push-to-talk; no activo escucha continua.', isUser: false));
      return;
    }
    final directory = await getTemporaryDirectory();
    _recordPath = '${directory.path}/gaia_ptt_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _recorder.start(const RecordConfig(encoder: AudioEncoder.aacLc, numChannels: 1, sampleRate: 16000, bitRate: 64000), path: _recordPath);
    if (mounted) setState(() => _isRecording = true);
  }

  Future<void> _stopRecording() async {
    if (!_isRecording) return;
    if (mounted) setState(() => _isRecording = false);
    final path = await _recorder.stop();
    if (path == null || path.isEmpty) return;
    try {
      final data = await _lumen.sendVoice(path);
      final userText = data['user_text']?.toString() ?? '';
      final responseText = (data['response']?.toString().trim().isNotEmpty == true) ? data['response'].toString() : (data['preview']?.toString() ?? 'GAIA no devolvió texto visible.');
      if (userText.isNotEmpty) _addMessage(ChatMessage(text: userText, isUser: true));
      final assistant = ChatMessage(text: responseText, isUser: false);
      _addMessage(assistant);
      final actionId = data['action_id']?.toString();
      final actionSessionId = data['session_id']?.toString() ?? _lumen.sessionId;
      if (data['kind'] == 'action' && actionId != null && actionSessionId.isNotEmpty && mounted) {
        final options = data['confirmation_options'] is Map ? Map<String, dynamic>.from(data['confirmation_options']) : <String, dynamic>{};
        final entries = data['permission_entries'] is List
            ? (data['permission_entries'] as List).whereType<Map>().map((entry) => Map<String, dynamic>.from(entry)).toList()
            : <Map<String, dynamic>>[];
        await _handleRemoteAction(assistant, actionId, actionSessionId, data['preview']?.toString() ?? responseText, options, permissionEntries: entries, requiresConfirmation: data['confirmation_required'] != false, targetHost: data['target_host']?.toString() ?? 'pc-main');
      }
      final audioUrl = data['audio_url']?.toString();
      if (_autoVoice && audioUrl != null && audioUrl.isNotEmpty) {
        final audioPath = await _lumen.downloadAudio(audioUrl);
        await _audioPlayer.play(DeviceFileSource(audioPath));
      } else if (_autoVoice && responseText.isNotEmpty && data['kind'] == 'chat') {
        await _playVoice(responseText);
      }
    } catch (error) {
      if (mounted) _addMessage(ChatMessage(text: 'Voz no disponible: $error', isUser: false));
    } finally {
      await File(path).delete().catchError((_) {});
    }
  }

  Future<void> _playVoice(String text) async {
    try {
      final audioPath = await _lumen.getAudioResponse(text);
      await _audioPlayer.play(DeviceFileSource(audioPath));
    } catch (_) {}
  }

  void _openSettings() async {
    final result = await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => SettingsScreen(lumen: _lumen),
      ),
    );
    if (result == true) {
      _checkConnection();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFF0f0f1a),
                border: Border(
                  bottom: BorderSide(
                    color: const Color(0xFFb388ff).withOpacity(0.15),
                  ),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    width: 36, height: 36,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: const LinearGradient(
                        colors: [Color(0xFF7c4dff), Color(0xFFb388ff)],
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: const Color(0xFFb388ff).withOpacity(0.3),
                          blurRadius: 8,
                        ),
                      ],
                    ),
                    child: const Center(
                      child: Text('L', style: TextStyle(
                        color: Colors.white, fontWeight: FontWeight.w800, fontSize: 18,
                      )),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('GAIA', style: TextStyle(
                          color: Colors.white, fontWeight: FontWeight.w700, fontSize: 18,
                          letterSpacing: 1.5,
                        )),
                        Text(
                          _isConnected ? 'En línea' : 'Sin conexión',
                          style: TextStyle(
                            color: _isConnected
                                ? const Color(0xFFb388ff)
                                : const Color(0xFFff6b9d),
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  DropdownButton<String>(
                    value: _profile,
                    dropdownColor: const Color(0xFF1b1a2a),
                    underline: const SizedBox.shrink(),
                    style: const TextStyle(color: Color(0xFFb388ff), fontSize: 12),
                    items: const [
                      DropdownMenuItem(value: 'auto', child: Text('AUTO')),
                      DropdownMenuItem(value: 'fast', child: Text('FAST')),
                      DropdownMenuItem(value: 'normal', child: Text('NORMAL')),
                      DropdownMenuItem(value: 'reasoning', child: Text('REASONING')),
                      DropdownMenuItem(value: 'code', child: Text('CODE')),
                    ],
                    onChanged: (value) => setState(() => _profile = value ?? 'auto'),
                  ),
                  // Toggle voz
                  IconButton(
                    icon: Icon(
                      _autoVoice ? Icons.volume_up : Icons.volume_off,
                      color: _autoVoice ? const Color(0xFFb388ff) : Colors.grey,
                    ),
                    onPressed: () => setState(() => _autoVoice = !_autoVoice),
                  ),
                  IconButton(
                    icon: const Icon(Icons.settings, color: Color(0xFF9e9bb0)),
                    onPressed: _openSettings,
                  ),
                ],
              ),
            ),

            // Messages
            Expanded(
              child: _messages.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            width: 80, height: 80,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: const LinearGradient(
                                colors: [Color(0xFF7c4dff), Color(0xFFb388ff), Color(0xFFea80fc)],
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFFb388ff).withOpacity(0.3),
                                  blurRadius: 20,
                                ),
                              ],
                            ),
                            child: const Center(
                              child: Text('L', style: TextStyle(
                                color: Colors.white, fontWeight: FontWeight.w800, fontSize: 36,
                              )),
                            ),
                          ),
                          const SizedBox(height: 20),
                          const Text('GAIA', style: TextStyle(
                            color: Colors.white, fontSize: 28, fontWeight: FontWeight.w800,
                            letterSpacing: 3,
                          )),
                          const SizedBox(height: 8),
                          Text(
                            '¿Qué quieres?',
                            style: TextStyle(color: Colors.grey[500], fontSize: 14),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) {
                        final msg = _messages[index];
                        return _buildMessageBubble(msg);
                      },
                    ),
            ),

            // Loading indicator
            if (_isLoading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: SizedBox(
                  width: 24, height: 24,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Color(0xFFb388ff),
                  ),
                ),
              ),

            // Input
            Container(
              padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
              decoration: BoxDecoration(
                color: const Color(0xFF0f0f1a),
                border: Border(
                  top: BorderSide(
                    color: const Color(0xFFb388ff).withOpacity(0.1),
                  ),
                ),
              ),
              child: Row(
                children: [
                  GestureDetector(
                    onLongPressStart: (_) => _startRecording(),
                    onLongPressEnd: (_) => _stopRecording(),
                    child: Container(
                      decoration: BoxDecoration(shape: BoxShape.circle, color: _isRecording ? const Color(0xFFff6b9d) : const Color(0xFF1e1e32)),
                      child: IconButton(icon: Icon(_isRecording ? Icons.mic : Icons.mic_none, color: Colors.white), onPressed: _isRecording ? _stopRecording : _startRecording, tooltip: 'Mantén pulsado para hablar'),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      style: const TextStyle(color: Colors.white, fontSize: 15),
                      decoration: InputDecoration(
                        hintText: 'Escribe algo...',
                        hintStyle: TextStyle(color: Colors.grey[600]),
                        filled: true,
                        fillColor: const Color(0xFF161625),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide: BorderSide.none,
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 18, vertical: 12,
                        ),
                      ),
                      onSubmitted: (_) => _sendMessage(),
                      textInputAction: TextInputAction.send,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: [Color(0xFF7c4dff), Color(0xFFb388ff)],
                      ),
                    ),
                    child: IconButton(
                      icon: const Icon(Icons.send, color: Colors.white, size: 20),
                      onPressed: _isLoading ? null : _sendMessage,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageBubble(ChatMessage msg) {
    return Align(
      alignment: msg.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        decoration: BoxDecoration(
          color: msg.isUser
              ? const Color(0xFF7c4dff)
              : const Color(0xFF1e1e32),
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(msg.isUser ? 18 : 4),
            bottomRight: Radius.circular(msg.isUser ? 4 : 18),
          ),
          border: msg.isUser
              ? null
              : Border.all(color: const Color(0xFFb388ff).withOpacity(0.1)),
        ),
        child: Text(
          msg.text,
          style: TextStyle(
            color: msg.isUser ? Colors.white : const Color(0xFFf0eef6),
            fontSize: 15,
            height: 1.4,
          ),
        ),
      ),
    );
  }
}
