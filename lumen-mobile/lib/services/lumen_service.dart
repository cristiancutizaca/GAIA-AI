import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class LumenService {
  String baseUrl;
  String secret;
  String sessionId = '';
  final String device = 'android';

  LumenService({
    this.baseUrl = 'http://192.168.1.100:8090',
    this.secret = 'lumen-dev-key',
  });

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $secret',
    'Content-Type': 'application/json',
  };

  // === Chat por texto ===
  Future<Map<String, dynamic>> sendMessage(String message) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/chat'),
      headers: _headers,
      body: jsonEncode({
        'message': message,
        'session_id': sessionId,
        'device': device,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Error ${response.statusCode}: ${response.body}');
    }

    final data = jsonDecode(response.body);
    sessionId = data['session_id'] ?? sessionId;
    return data;
  }

  // === Chat por voz ===
  Future<Map<String, dynamic>> sendVoice(String audioPath) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/chat/voice?session_id=$sessionId&device=$device'),
    );
    request.headers['Authorization'] = 'Bearer $secret';
    request.files.add(await http.MultipartFile.fromPath('audio', audioPath));

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode != 200) {
      throw Exception('Error ${response.statusCode}: ${response.body}');
    }

    final data = jsonDecode(response.body);
    sessionId = data['session_id'] ?? sessionId;
    return data;
  }

  // === TTS ===
  Future<String> getAudioResponse(String text) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/voice/tts'),
      headers: _headers,
      body: jsonEncode({'text': text}),
    );

    if (response.statusCode != 200) throw Exception('TTS failed');

    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/lumen_response.mp3');
    await file.writeAsBytes(response.bodyBytes);
    return file.path;
  }

  // === Audio de respuesta ===
  Future<String> downloadAudio(String audioUrl) async {
    final response = await http.get(
      Uri.parse('$baseUrl$audioUrl'),
      headers: _headers,
    );

    if (response.statusCode != 200) throw Exception('Audio download failed');

    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/lumen_voice.mp3');
    await file.writeAsBytes(response.bodyBytes);
    return file.path;
  }

  // === Estado ===
  Future<Map<String, dynamic>> getStatus() async {
    final response = await http.get(Uri.parse('$baseUrl/api/status'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Status failed');
    return jsonDecode(response.body);
  }

  // === Proactivo ===
  Future<Map<String, dynamic>?> checkProactive() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/proactive/check'),
        headers: _headers,
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['has_message'] == true) return data;
      }
    } catch (_) {}
    return null;
  }

  // === Perfil ===
  Future<Map<String, dynamic>> getProfile() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/profile'),
      headers: _headers,
    );
    if (response.statusCode != 200) throw Exception('Profile failed');
    return jsonDecode(response.body);
  }

  // === Preferencias ===
  Future<void> setPreference(String key, String value) async {
    await http.post(
      Uri.parse('$baseUrl/api/memory/preference'),
      headers: _headers,
      body: jsonEncode({'key': key, 'value': value}),
    );
  }

  // === Test conexión ===
  Future<bool> testConnection() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/status'), headers: _headers)
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
