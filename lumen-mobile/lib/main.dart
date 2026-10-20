import 'package:flutter/material.dart';
import 'screens/chat_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/pairing_screen.dart';
import 'services/lumen_service.dart';

void main() {
  runApp(const LumenApp());
}

class LumenApp extends StatelessWidget {
  const LumenApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GAIA',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0a0a12),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFb388ff),
          secondary: Color(0xFF7c4dff),
          surface: Color(0xFF161625),
          error: Color(0xFFff6b9d),
        ),
        fontFamily: 'System',
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF0f0f1a),
          elevation: 0,
        ),
      ),
      home: const BootstrapScreen(),
    );
  }
}


class BootstrapScreen extends StatefulWidget {
  const BootstrapScreen({super.key});

  @override
  State<BootstrapScreen> createState() => _BootstrapScreenState();
}

class _BootstrapScreenState extends State<BootstrapScreen> {
  final LumenService _lumen = LumenService();
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    await _lumen.loadSavedConfig();
    if (!mounted) return;
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (_lumen.secret.trim().isEmpty) return PairingScreen(lumen: _lumen);
    return ChatScreen(lumen: _lumen);
  }
}
