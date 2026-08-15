import 'package:flutter/material.dart';
import 'screens/chat_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  runApp(const LumenApp());
}

class LumenApp extends StatelessWidget {
  const LumenApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'LUMEN',
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
      home: const ChatScreen(),
    );
  }
}
