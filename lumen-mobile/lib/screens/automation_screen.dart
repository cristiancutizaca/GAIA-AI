import 'package:flutter/material.dart';
import '../services/lumen_service.dart';

class AutomationScreen extends StatefulWidget {
  final LumenService lumen;
  const AutomationScreen({super.key, required this.lumen});

  @override
  State<AutomationScreen> createState() => _AutomationScreenState();
}

class _AutomationScreenState extends State<AutomationScreen> {
  Map<String, dynamic>? _status;
  List<dynamic> _rules = [];
  List<dynamic> _notifications = [];
  bool _loading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = ''; });
    try {
      final values = await Future.wait([
        widget.lumen.getAutomationStatus(),
        widget.lumen.getAutomations(),
        widget.lumen.getNotifications(),
      ]);
      if (!mounted) return;
      setState(() {
        _status = values[0];
        _rules = (values[1]['automations'] as List<dynamic>?) ?? [];
        _notifications = (values[2]['notifications'] as List<dynamic>?) ?? [];
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() { _loading = false; _error = error.toString(); });
    }
  }

  Future<void> _dismiss(String id) async {
    try {
      await widget.lumen.updateNotification(id, read: true, dismissed: true);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final automation = _status?['automation'] as Map<String, dynamic>? ?? {};
    final paused = automation['paused'] == true;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Automatizaciones', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error.isNotEmpty) _errorCard(_error),
                  _statusCard(automation, paused),
                  const SizedBox(height: 20),
                  _sectionTitle('REGLAS DE ESTE DISPOSITIVO'),
                  if (_rules.isEmpty) _empty('No hay reglas visibles para este dispositivo.'),
                  ..._rules.map((rule) => _ruleCard(rule as Map<String, dynamic>)),
                  const SizedBox(height: 20),
                  _sectionTitle('NOTIFICACIONES'),
                  if (_notifications.isEmpty) _empty('No hay notificaciones pendientes.'),
                  ..._notifications.map((note) => _notificationCard(note as Map<String, dynamic>)),
                ],
              ),
            ),
    );
  }

  Widget _statusCard(Map<String, dynamic> automation, bool paused) => Card(
    color: const Color(0xFF161625),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('Modo ${automation['mode'] ?? 'OFF'}', style: const TextStyle(color: Color(0xFFb388ff), fontWeight: FontWeight.w700)),
          Icon(paused ? Icons.pause_circle : Icons.play_circle, color: paused ? const Color(0xFFff6b9d) : const Color(0xFFb388ff)),
        ]),
        const SizedBox(height: 8),
        Text(paused ? 'Kill switch activo: no se ejecutan rutinas.' : 'Las reglas seguras pueden encolarse para el PC Action Host.', style: const TextStyle(color: Color(0xFF9e9bb0))),
        const SizedBox(height: 12),
        Text("Kill switch: ${paused ? 'activo en el Core' : 'inactivo'}. El control maestro permanece en el PC.", style: const TextStyle(color: Color(0xFF9e9bb0))),
      ]),
    ),
  );

  Widget _ruleCard(Map<String, dynamic> rule) => ListTile(
    contentPadding: const EdgeInsets.symmetric(horizontal: 8),
    leading: Icon(rule['enabled'] == true ? Icons.check_circle : Icons.pause_circle, color: rule['enabled'] == true ? const Color(0xFFb388ff) : Colors.grey),
    title: Text('${rule['name'] ?? 'Regla'}', style: const TextStyle(color: Colors.white)),
    subtitle: Text(rule['enabled'] == true ? 'Activa · ${rule['trigger']?['event_type'] ?? 'evento'}' : 'Desactivada', style: const TextStyle(color: Color(0xFF9e9bb0))),
  );

  Widget _notificationCard(Map<String, dynamic> note) => Card(
    color: const Color(0xFF161625),
    child: ListTile(
      title: Text('${note['title'] ?? 'GAIA'}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
      subtitle: Text('${note['message'] ?? ''}', style: const TextStyle(color: Color(0xFF9e9bb0))),
      trailing: IconButton(onPressed: () => _dismiss('${note['notification_id'] ?? ''}'), icon: const Icon(Icons.done, color: Color(0xFFb388ff))),
    ),
  );

  Widget _errorCard(String message) => Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(message, style: const TextStyle(color: Color(0xFFff6b9d))));
  Widget _empty(String message) => Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(message, style: const TextStyle(color: Color(0xFF9e9bb0))));
  Widget _sectionTitle(String title) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Text(title, style: const TextStyle(color: Color(0xFFb388ff), fontSize: 13, fontWeight: FontWeight.w700, letterSpacing: 1)));
}
