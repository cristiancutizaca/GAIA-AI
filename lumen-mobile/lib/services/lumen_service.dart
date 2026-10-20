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
  String lastHostVersion = '';
  String deviceId = 'android';
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

  Map<String, dynamic> _requestEnvelope(String channel, String message) => {
    'schema_version': '1',
    'request_id': DateTime.now().microsecondsSinceEpoch.toRadixString(16),
    'session_id': sessionId,
    'channel': channel,
    'requesting_device': deviceId,
    'target_host': '',
    'timestamp': DateTime.now().toUtc().toIso8601String(),
    'protocol_version': '1.0-RC6',
    'text': message.length > 12000 ? message.substring(0, 12000) : message,
  };

  void _requireDeviceToken() {
    if (secret.trim().isEmpty) {
      throw Exception('Configura un token de dispositivo; el secreto maestro no se usa en Android.');
    }
  }

  /// Parses the one-shot QR/deep-link payload produced by the PC pairing flow.
  /// It contains no long-lived token: only pairing id, short-lived code and Core URL.
  static Map<String, String> parsePairingUri(String raw) {
    final value = raw.trim();
    if (value.isEmpty) throw const FormatException('URI de pairing vacío.');
    final parsed = Uri.tryParse(value);
    if (parsed == null || parsed.scheme.toLowerCase() != 'gaia' || parsed.host.toLowerCase() != 'pair') {
      throw const FormatException('El QR no contiene un URI gaia://pair válido.');
    }
    final pairingId = (parsed.queryParameters['id'] ?? parsed.queryParameters['pairing_id'] ?? '').trim();
    final code = (parsed.queryParameters['code'] ?? '').trim();
    final rawUrl = (parsed.queryParameters['url'] ?? parsed.queryParameters['server'] ?? '').trim();
    final server = Uri.tryParse(rawUrl);
    final validServer = server != null &&
        {'http', 'https'}.contains(server.scheme.toLowerCase()) &&
        server.host.isNotEmpty &&
        server.userInfo.isEmpty &&
        server.fragment.isEmpty;
    if (pairingId.isEmpty || code.isEmpty || !validServer) {
      throw const FormatException('El QR no contiene todos los datos seguros de pairing.');
    }
    return {
      'url': rawUrl.replaceFirst(RegExp(r'\/$'), ''),
      'pairing_id': pairingId,
      'code': code,
    };
  }

  Future<void> loadSavedConfig() async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = prefs.getString('gaia_base_url') ?? baseUrl;
    sessionId = prefs.getString('gaia_session_id') ?? sessionId;
    deviceId = prefs.getString('gaia_device_id') ?? deviceId;
    final secureToken = await _secureStorage.read(key: 'gaia_device_token');
    final legacyToken = prefs.getString('gaia_secret');
    secret = secureToken ?? legacyToken ?? secret;
    if (secureToken == null && legacyToken != null && legacyToken.trim().isNotEmpty) {
      await _secureStorage.write(key: 'gaia_device_token', value: legacyToken.trim());
      await prefs.remove('gaia_secret');
    }
  }

  Future<void> clearSavedConfig() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('gaia_base_url');
    await prefs.remove('gaia_session_id');
    await prefs.remove('gaia_device_id');
    await prefs.remove('gaia_secret');
    await _secureStorage.delete(key: 'gaia_device_token');
    secret = '';
    sessionId = '';
    deviceId = 'android';
  }

  Future<void> saveConfig({required String url, required String token, String? pairedDeviceId}) async {
    baseUrl = url.trim().replaceFirst(RegExp(r'\/$'), '');
    secret = token.trim();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('gaia_base_url', baseUrl);
    if (pairedDeviceId != null && pairedDeviceId.trim().isNotEmpty) {
      deviceId = pairedDeviceId.trim();
      await prefs.setString('gaia_device_id', deviceId);
    }
    await _secureStorage.write(key: 'gaia_device_token', value: secret);
    await prefs.remove('gaia_secret');
  }

  Future<void> _saveSession() async {
    final prefs = await SharedPreferences.getInstance();
    if (sessionId.isNotEmpty) await prefs.setString('gaia_session_id', sessionId);
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
        'device': deviceId,
        'profile': profile,
        'channel': 'android_text',
        'request_envelope': _requestEnvelope('android_text', message),
        // Android does not authoritatively know the PC foreground window.
        if (context != null) 'context': context,
      }),
    ).timeout(const Duration(seconds: 620));

    if (response.statusCode != 200) {
      throw Exception(_error('Chat', response.statusCode, response.body));
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    sessionId = data['session_id'] ?? sessionId;
    await _saveSession();
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
              'device': deviceId,

      'profile': profile,
      'channel': 'android_text',
      'request_envelope': _requestEnvelope('android_text', message),
      // Android does not authoritatively know the PC foreground window.
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
            await _saveSession();
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
      Uri.parse('$baseUrl/api/chat/voice?session_id=$sessionId&device=$deviceId'),
    );
    request.headers['Authorization'] = 'Bearer $secret';
    request.fields['channel'] = 'android_voice';
    request.fields['request_envelope'] = jsonEncode(_requestEnvelope('android_voice', ''));
    request.fields['desktop_snapshot'] = jsonEncode({});
    request.files.add(await http.MultipartFile.fromPath('audio', audioPath));
    final streamedResponse = await request.send().timeout(const Duration(seconds: 620));
    final response = await http.Response.fromStream(streamedResponse);
    if (response.statusCode != 200) throw Exception(_error('Voz', response.statusCode, response.body));
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    sessionId = data['session_id'] ?? sessionId;
    await _saveSession();
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

  Future<String> downloadCapture(String captureId) async {
    _requireDeviceToken();
    final candidate = captureId.trim();
    if (!RegExp(r'^cap_[A-Za-z0-9_-]{20,80}$').hasMatch(candidate)) {
      throw const FormatException('capture_id inválido.');
    }
    final response = await http.get(Uri.parse('$baseUrl/api/captures/$candidate'), headers: {'Authorization': 'Bearer $secret'});
    if (response.statusCode != 200) throw Exception(_error('Captura', response.statusCode, response.body));
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/$candidate.png');
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

  // === Acciones remotas: Android solicita y aprueba; el PC host ejecuta ===
  Future<Map<String, dynamic>> approveAction(String actionId, String actionSessionId, {String? decision}) async {
    _requireDeviceToken();
    final response = await http.post(
      Uri.parse('$baseUrl/api/actions/approve'),
      headers: _headers,
      body: jsonEncode({'action_id': actionId, 'session_id': actionSessionId, if (decision != null) 'decision': decision}),
    );
    if (response.statusCode != 200) throw Exception(_error('Aprobación', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> rejectAction(String actionId, String actionSessionId) async {
    _requireDeviceToken();
    final response = await http.post(
      Uri.parse('$baseUrl/api/actions/reject'),
      headers: _headers,
      body: jsonEncode({'action_id': actionId, 'session_id': actionSessionId}),
    );
    if (response.statusCode != 200) throw Exception(_error('Rechazo', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> getActionControl() async {
    _requireDeviceToken();
    final response = await http.get(Uri.parse('$baseUrl/api/actions/control'), headers: _headers);
    if (response.statusCode != 200) throw Exception(_error('Control de acciones', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> negotiateFeatures(Map<String, String> features, {bool requestRemoteActions = false}) async {
    _requireDeviceToken();
    final response = await http.post(
      Uri.parse('$baseUrl/api/devices/negotiate'),
      headers: _headers,
      body: jsonEncode({'features': features, 'request_remote_actions': requestRemoteActions}),
    );
    if (response.statusCode != 200) throw Exception(_error('Negociación', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> completePairing(String pairingId, String code, Map<String, String> features) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/pairing/complete'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'pairing_id': pairingId, 'code': code, 'features': features}),
    );
    if (response.statusCode != 200) throw Exception(_error('Pairing', response.statusCode, response.body));
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final pairedToken = data['token']?.toString() ?? '';
    final pairedDevice = data['device_id']?.toString() ?? '';
    if (pairedToken.isEmpty || pairedDevice.isEmpty) throw Exception('Pairing no devolvió onboarding completo.');
    await saveConfig(url: baseUrl, token: pairedToken, pairedDeviceId: pairedDevice);
    return data;
  }

  Future<Map<String, dynamic>> getRemoteHostStatus() async {
    _requireDeviceToken();
    final response = await http.get(Uri.parse('$baseUrl/api/action-host/status'), headers: _headers);
    if (response.statusCode != 200) throw Exception(_error('Estado del PC Action Host', response.statusCode, response.body));
    return jsonDecode(response.body);
  }

  // === Automatizaciones v0.9.0 ===
  Future<Map<String, dynamic>> getAutomationStatus() async {
    _requireDeviceToken();
    final response = await http.get(Uri.parse('$baseUrl/api/automation/status'), headers: _headers);
    if (response.statusCode != 200) throw Exception(_error('Automatizaciones', response.statusCode, response.body));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getAutomations() async {
    _requireDeviceToken();
    final response = await http.get(Uri.parse('$baseUrl/api/automations'), headers: _headers);
    if (response.statusCode != 200) throw Exception(_error('Reglas', response.statusCode, response.body));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getNotifications() async {
    _requireDeviceToken();
    final response = await http.get(Uri.parse('$baseUrl/api/notifications'), headers: _headers);
    if (response.statusCode != 200) throw Exception(_error('Notificaciones', response.statusCode, response.body));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> pauseAutomation(bool paused) async {
    _requireDeviceToken();
    final response = await http.post(Uri.parse('$baseUrl/api/automation/pause?paused=$paused'), headers: _headers);
    if (response.statusCode != 200) throw Exception(_error('Pausa de automatizaciones', response.statusCode, response.body));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> setAutomationMode(String mode) async {
    _requireDeviceToken();
    final response = await http.post(Uri.parse('$baseUrl/api/automation/mode'), headers: _headers, body: jsonEncode({'mode': mode}));
    if (response.statusCode != 200) throw Exception(_error('Modo de automatización', response.statusCode, response.body));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateNotification(String id, {bool? read, bool? dismissed}) async {
    _requireDeviceToken();
    final response = await http.patch(Uri.parse('$baseUrl/api/notifications/$id'), headers: _headers, body: jsonEncode({if (read != null) 'read': read, if (dismissed != null) 'dismissed': dismissed}));
    if (response.statusCode != 200) throw Exception(_error('Notificación', response.statusCode, response.body));
    return jsonDecode(response.body) as Map<String, dynamic>;
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
      if (response.statusCode == 401) {
        await clearSavedConfig();
        return false;
      }
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
