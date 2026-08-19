import 'package:flutter/material.dart';
import '../services/lumen_service.dart';

class SettingsScreen extends StatefulWidget {
  final LumenService lumen;
  const SettingsScreen({super.key, required this.lumen});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlController = TextEditingController();
  final _tokenController = TextEditingController();
  final _nameController = TextEditingController();
  bool _testing = false;
  String _testResult = '';
  Map<String, dynamic>? _status;
  Map<String, dynamic>? _profile;

  @override
  void initState() {
    super.initState();
    _urlController.text = widget.lumen.baseUrl;
    _tokenController.text = widget.lumen.secret;
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final status = await widget.lumen.getStatus();
      setState(() => _status = status);

      final profile = await widget.lumen.getProfile();
      setState(() => _profile = profile);
    } catch (_) {}
  }

  Future<void> _testConnection() async {
    setState(() { _testing = true; _testResult = ''; });
    widget.lumen.baseUrl = _urlController.text.trim();
    widget.lumen.secret = _tokenController.text.trim();

    final ok = await widget.lumen.testConnection();
    setState(() {
      _testing = false;
      _testResult = ok ? '✓ Conectado' : '✗ No se pudo conectar';
    });
  }

  Future<void> _saveName() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) return;
    try {
      await widget.lumen.setPreference('user_name', name);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('GAIA te conocerá como "$name"')),
      );
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Configuración', style: TextStyle(fontWeight: FontWeight.w700)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context, true),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _sectionTitle('CONEXIÓN'),
          _inputField('URL del Core', _urlController, 'http://192.168.1.100:8090'),
          const SizedBox(height: 8),
          _inputField('Token de dispositivo', _tokenController, 'gaia-device-token'),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: ElevatedButton(
                  onPressed: _testing ? null : _testConnection,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF7c4dff),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: _testing
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Text('Probar conexión', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                ),
              ),
            ],
          ),
          if (_testResult.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_testResult, style: TextStyle(
                color: _testResult.contains('✓') ? const Color(0xFFb388ff) : const Color(0xFFff6b9d),
                fontSize: 14,
              )),
            ),

          const SizedBox(height: 24),
          _sectionTitle('IDENTIDAD'),
          _inputField('Tu nombre', _nameController, '¿Cómo te llamas?'),
          const SizedBox(height: 8),
          ElevatedButton(
            onPressed: _saveName,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1e1e32),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('Guardar nombre', style: TextStyle(color: Color(0xFFb388ff))),
          ),

          if (_status != null) ...[
            const SizedBox(height: 24),
            _sectionTitle('ESTADO DE GAIA'),
            _infoRow('LLM', '${_status!['llm']?['backend']} (${_status!['llm']?['status']})'),
            _infoRow('Modelo', '${_status!['llm']?['model']}'),
            _infoRow('Mensajes', '${_status!['memory']?['total_messages']}'),
            _infoRow('Hechos', '${_status!['memory']?['total_facts']}'),
            _infoRow('Sesiones', '${_status!['memory']?['total_sessions']}'),
          ],

          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: OutlinedButton(
              onPressed: () async {
                try {
                  final diagnostic = await widget.lumen.getDiagnostics();
                  if (!mounted) return;
                  showDialog<void>(context: context, builder: (_) => AlertDialog(title: const Text('Diagnóstico GAIA'), content: SingleChildScrollView(child: Text(diagnostic.toString())), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cerrar'))]));
                } catch (_) {}
              },
              child: const Text('Ver diagnóstico seguro'),
            ),
          ),

          if (_profile != null && _profile!.isNotEmpty) ...[
            const SizedBox(height: 24),
            _sectionTitle('LO QUE GAIA SABE DE TI'),
            ..._profile!.entries.map((e) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 8, bottom: 4),
                  child: Text(e.key.toUpperCase(),
                    style: const TextStyle(color: Color(0xFF7c4dff), fontSize: 11, fontWeight: FontWeight.w700)),
                ),
                ...((e.value as List).map((fact) => Padding(
                  padding: const EdgeInsets.only(left: 8, bottom: 2),
                  child: Text('• $fact', style: const TextStyle(color: Color(0xFF9e9bb0), fontSize: 13)),
                ))),
              ],
            )),
          ],

          const SizedBox(height: 40),
          Center(
            child: Text('GAIA móvil v0.5.0 (prototipo; validar en Android físico)', style: TextStyle(color: Colors.grey[700], fontSize: 12)),
          ),
        ],
      ),
    );
  }

  Widget _sectionTitle(String title) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Text(title, style: const TextStyle(
      color: Color(0xFFb388ff), fontSize: 13, fontWeight: FontWeight.w700, letterSpacing: 1,
    )),
  );

  Widget _inputField(String label, TextEditingController ctrl, String hint) => TextField(
    controller: ctrl,
    style: const TextStyle(color: Colors.white, fontSize: 15),
    decoration: InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(color: Color(0xFF9e9bb0)),
      hintText: hint,
      hintStyle: TextStyle(color: Colors.grey[700]),
      filled: true,
      fillColor: const Color(0xFF161625),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),
  );

  Widget _infoRow(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: Color(0xFF9e9bb0), fontSize: 14)),
        Text(value, style: const TextStyle(color: Colors.white, fontSize: 14)),
      ],
    ),
  );
}
