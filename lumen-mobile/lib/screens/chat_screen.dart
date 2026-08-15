import 'dart:async';
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import '../services/lumen_service.dart';
import 'settings_screen.dart';

class ChatMessage {
  final String text;
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
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final LumenService _lumen = LumenService();
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final List<ChatMessage> _messages = [];

  bool _isLoading = false;
  bool _isConnected = false;
  bool _autoVoice = true;
  Timer? _proactiveTimer;

  @override
  void initState() {
    super.initState();
    _checkConnection();
    _startProactiveCheck();
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _audioPlayer.dispose();
    _proactiveTimer?.cancel();
    super.dispose();
  }

  Future<void> _checkConnection() async {
    final connected = await _lumen.testConnection();
    setState(() => _isConnected = connected);

    if (!connected) {
      _addMessage(ChatMessage(
        text: 'No puedo conectar con el Core. Verifica que esté corriendo y la IP sea correcta.',
        isUser: false,
      ));
    }
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
    setState(() => _isLoading = true);

    try {
      final data = await _lumen.sendMessage(text);
      final response = data['response'] ?? '...';
      _addMessage(ChatMessage(text: response, isUser: false));

      if (_autoVoice) {
        await _playVoice(response);
      }
    } catch (e) {
      _addMessage(ChatMessage(
        text: 'Error de conexión. ¿El Core sigue vivo?',
        isUser: false,
      ));
    } finally {
      setState(() => _isLoading = false);
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
                        const Text('LUMEN', style: TextStyle(
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
                          const Text('LUMEN', style: TextStyle(
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
