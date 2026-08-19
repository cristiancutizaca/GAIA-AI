import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class LumenService {
  String baseUrl;
  String secret;
  String sessionId = '';
  String activeRequestId = '';
  final String device = 'android';
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();

  LumenService({
    this.baseUrl = 'http://127.0.0.1:8090',
    this.secret = '',
  });

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $secret',
    'Content-Type': 'application/json',
  };

  String _error(String operation, int status, String body) {
    if (status == 401) return '$operation: token de dispositivo ausente, inválido, expirado o revocado.';
    if (status == 403) return '$operation: token válido, pero sin capability autorizada para esta operación.';
    return '$operation $status: ${body.length > 300 ? body.substring(0, 300) : body}';
  }

  void _requireDeviceToken() {
    if (secret.trim().isEmpty) {
      throw Exception('Configura un token de dispositivo; el secreto maestro no se usa en Android.');
    }
  }

  Future<void> loadSavedConfig() async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = prefs.getString('gaia_base_url') ?? baseUrl;
    final secureToken = await _secureStorage.read(key: 'gaia_device_token');
    final legacyToken = prefs.getString('gaia_secret');
    secret = secureToken ?? legacyToken ?? secret;
    if (secureToken == null && legacyToken != null && legacyToken.trim().isNotEmpty) {
      await _secureStorage.write(key: 'gaia_device_token', value: legacyToken.trim());
      await prefs.remove('gaia_secret');
    }
  }

  Future<void> saveConfig({required String url, required String token}) async {
    baseUrl = url.trim().replaceFirst(RegExp(r'\/$'), '');
    secret = token.trim();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('gaia_base_url', baseUrl);
    await _secureStorage.write(key: 'gaia_device_token', value: secret);
    await prefs.remove('gaia_secret');
  }

  // === Chat compatible ===
  Future<Map<String, dynamic>> sendMessage(String message, {String profile = 'auto', int? context}) async {
    _requireDeviceToken();
    final response = await http.post(
      Uri.parse('$baseUrl/api/chat'),
      headers: _headers,
      body: jsonEncode({
        'message': message,
        'session_id': sessionId,
        'device': device,
        'profile': profile,
        if (context != null) 'context': context,
      }),
    ).timeout(const Duration(seconds: 620));

    if (response.statusCode != 200) {
      throw Exception(_error('Chat', response.statusCode, response.body));
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    sessionId = data['session_id'] ?? sessionId;
    return data;
  }

  // === SSE ===
  Stream<Map<String, dynamic>> streamMessage(String message, {String profile = 'auto', int? context}) async* {
    _requireDeviceToken();
    final request = http.Request('POST', Uri.parse('$baseUrl/api/assistant/stream'));
    request.headers.addAll(_headers);
    request.body = jsonEncode({
      'message': message,
      'session_id': sessionId,
      'device': device,
      'profile': profile,
      if (context != null) 'context': context,
    });
    final client = http.Client();
    try {
      final response = await client.send(request).timeout(const Duration(seconds: 620));
      if (response.statusCode != 200) {
        throw Exception(_error('Streaming', response.statusCode, await response.stream.bytesToString()));
      }
      String event = '';
      await for (final line in response.stream.transform(utf8.decoder).transform(const LineSplitter())) {
        if (line.startsWith('event: ')) {
          event = line.substring(7).trim();
        } else if (line.startsWith('data: ')) {
          final data = jsonDecode(line.substring(6)) as Map<String, dynamic>;
          data['event'] = event;
          if (event == 'meta') {
            sessionId = data['session_id'] ?? sessionId;
            activeRequestId = data['request_id'] ?? activeRequestId;
          }
          yield data;
          if (event == 'done' || event == 'error' || event == 'cancelled') break;
        }
      }
    } finally {
      client.close();
    }
  }

  Future<Map<String, dynamic>> cancelGeneration() async {
    if (activeRequestId.isEmpty) return {'status': 'no_active_request'};
    final response = await http.post(
      Uri.parse('$baseUrl/api/assistant/cancel'),
      headers: _headers,
      body: jsonEncode({'request_id': activeRequestId}),
    );
    if (response.statusCode != 200) throw Exception('Cancelación falló');
    return jsonDecode(response.body);
  }

  // === Chat por voz ===
  Future<Map<String, dynamic>> sendVoice(String audioPath) async {
    _requireDeviceToken();
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/chat/voice?session_id=$sessionId&device=$device'),
    );
    request.headers['Authorization'] = 'Bearer $secret';
    request.files.add(await http.MultipartFile.fromPath('audio', audioPath));
    final streamedResponse = await request.send().timeout(const Duration(seconds: 620));
    final response = await http.Response.fromStream(streamedResponse);
    if (response.statusCode != 200) throw Exception(_error('Voz', response.statusCode, response.body));
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    sessionId = data['session_id'] ?? sessionId;
    return data;
  }

  // === TTS ===
  Future<String> getAudioResponse(String text) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/voice/tts'),
      headers: _headers,
      body: jsonEncode({'text': text}),
    ).timeout(const Duration(seconds: 90));
    if (response.statusCode != 200) throw Exception(_error('TTS', response.statusCode, response.body));
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/gaia_response.mp3');
    await file.writeAsBytes(response.bodyBytes);
    return file.path;
  }

  Future<String> downloadAudio(String audioUrl) async {
    final response = await http.get(Uri.parse('$baseUrl$audioUrl'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Audio ${response.statusCode}');
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/gaia_voice.mp3');
    await file.writeAsBytes(response.bodyBytes);
    return file.path;
  }

  // === Estado, memoria y backup ===
  Future<Map<String, dynamic>> getDiagnostics() async {
    final response = await http.get(Uri.parse('$baseUrl/api/diagnostics'), headers: _headers).timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) throw Exception(_error('Diagnóstico', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> getStatus() async {
    final response = await http.get(Uri.parse('$baseUrl/api/status'), headers: _headers).timeout(const Duration(seconds: 10));
    if (response.statusCode != 200) throw Exception(_error('Estado', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> getVaultStatus() async {
    final response = await http.get(Uri.parse('$baseUrl/api/vault/status'), headers: _headers);
    if (response.statusCode != 200) throw Exception(_error('Vault', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> createBrainBackup() async {
    final response = await http.post(Uri.parse('$baseUrl/api/backup/brain'), headers: _headers).timeout(const Duration(seconds: 60));
    if (response.statusCode != 200) throw Exception(_error('Brain Backup', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>?> checkProactive() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/proactive/check'), headers: _headers);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (data['has_message'] == true) return data;
      }
    } catch (_) {}
    return null;
  }

  Future<Map<String, dynamic>> getProfile() async {
    final response = await http.get(Uri.parse('$baseUrl/api/profile'), headers: _headers);
    if (response.statusCode != 200) throw Exception(_error('Perfil', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<void> setPreference(String key, String value) async {
    final response = await http.post(Uri.parse('$baseUrl/api/memory/preference'), headers: _headers, body: jsonEncode({'key': key, 'value': value}));
    if (response.statusCode >= 300) throw Exception('Preferencia ${response.statusCode}');
  }

  Future<bool> testConnection() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/status'), headers: _headers).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
