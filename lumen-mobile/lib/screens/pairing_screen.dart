import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../services/lumen_service.dart';
import 'chat_screen.dart';

class PairingScreen extends StatefulWidget {
  final LumenService lumen;
  const PairingScreen({super.key, required this.lumen});

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _urlController = TextEditingController(text: 'http://127.0.0.1:8090');
  final _pairingController = TextEditingController();
  final _codeController = TextEditingController();
  bool _busy = false;
  String _message = '';

  @override
  void dispose() {
    _urlController.dispose();
    _pairingController.dispose();
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _complete() async {
    final url = _urlController.text.trim();
    final pairingId = _pairingController.text.trim();
    final code = _codeController.text.trim();
    if (url.isEmpty || pairingId.isEmpty || code.isEmpty) {
      setState(() => _message = 'Introduce la dirección del Core, pairing ID y código de un solo uso.');
      return;
    }
    setState(() {
      _busy = true;
      _message = '';
    });
    try {
      widget.lumen.baseUrl = url.replaceFirst(RegExp(r'\/$'), '');
      final data = await widget.lumen.completePairing(pairingId, code, const {
        'chat': '1',
        'actions_request': '1',
        'streaming': '1',
        'voice': '1',
        'proactive_read': '1',
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Dispositivo ${data['device_id']} conectado. Token guardado en almacenamiento seguro.')));
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => ChatScreen(lumen: widget.lumen)));
    } catch (error) {
      if (mounted) setState(() => _message = 'No se pudo completar el pairing: $error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _applyPairingUri(String payload) {
    try {
      final parsed = LumenService.parsePairingUri(payload);
      if (!mounted) return;
      setState(() {
        _urlController.text = parsed['url']!;
        _pairingController.text = parsed['pairing_id']!;
        _codeController.text = parsed['code']!;
        _message = 'QR válido. Verifica el servidor y pulsa “Completar pairing”.';
      });
    } catch (error) {
      if (mounted) setState(() => _message = 'QR inválido: $error');
    }
  }

  Future<void> _scanQr() async {
    final payload = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (_) => const _PairingQrScanner()),
    );
    if (payload != null && payload.trim().isNotEmpty) _applyPairingUri(payload);
  }

  Future<void> _pasteQr() async {
    final controller = TextEditingController();
    final payload = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Pegar URI de pairing'),
        content: TextField(
          controller: controller,
          autofocus: true,
          minLines: 2,
          maxLines: 5,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(
            labelText: 'URI gaia://pair',
            hintText: 'gaia://pair?id=...&code=...&url=http%3A%2F%2F...',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, controller.text.trim()), child: const Text('Aplicar')),
        ],
      ),
    );
    controller.dispose();
    if (payload != null && payload.trim().isNotEmpty) _applyPairingUri(payload);
  }

  Future<void> _manualToken() async {
    final tokenController = TextEditingController();
    final token = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Modo avanzado'),
        content: TextField(controller: tokenController, obscureText: true, decoration: const InputDecoration(labelText: 'Token de dispositivo')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, tokenController.text.trim()), child: const Text('Guardar')),
        ],
      ),
    );
    tokenController.dispose();
    if (token == null || token.isEmpty) return;
    await widget.lumen.saveConfig(url: _urlController.text.trim(), token: token, pairedDeviceId: 'android');
    if (!mounted) return;
    Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => ChatScreen(lumen: widget.lumen)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Conectar a GAIA', style: TextStyle(fontWeight: FontWeight.w700))),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Icon(Icons.devices_other, color: Color(0xFFb388ff), size: 64),
          const SizedBox(height: 16),
          const Text('Empareja este Android con tu PC', textAlign: TextAlign.center, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text('Desde GAIA en el PC crea una sesión de pairing. Escanea el QR o pega su URI; el pairing es temporal, de un solo uso y no contiene el token permanente.', textAlign: TextAlign.center, style: TextStyle(color: Color(0xFF9e9bb0))),
          const SizedBox(height: 24),
          _field('Dirección del Core', _urlController, 'http://192.168.1.20:8090'),
          const SizedBox(height: 12),
          _field('Pairing ID', _pairingController, 'Identificador de la sesión'),
          const SizedBox(height: 12),
          _field('Código de un solo uso', _codeController, 'Código temporal', obscure: true),
          const SizedBox(height: 18),
          FilledButton.icon(onPressed: _busy ? null : _complete, icon: _busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.link), label: const Text('Completar pairing')),
          const SizedBox(height: 10),
          OutlinedButton.icon(onPressed: _busy ? null : _scanQr, icon: const Icon(Icons.qr_code_scanner), label: const Text('Escanear QR')),
          TextButton.icon(onPressed: _busy ? null : _pasteQr, icon: const Icon(Icons.content_paste), label: const Text('Pegar URI manualmente')),
          const Text('El lector usa la cámara del dispositivo. Si no puedes conceder cámara, pega el URI copiado desde el PC.', textAlign: TextAlign.center, style: TextStyle(color: Color(0xFF77748b), fontSize: 12)),
          TextButton(onPressed: _busy ? null : _manualToken, child: const Text('Modo avanzado: introducir token manualmente')),
          if (_message.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_message, style: const TextStyle(color: Color(0xFFff6b9d)))),
        ],
      ),
    );
  }

  Widget _field(String label, TextEditingController controller, String hint, {bool obscure = false}) => TextField(
    controller: controller,
    obscureText: obscure,
    style: const TextStyle(color: Colors.white),
    decoration: InputDecoration(labelText: label, hintText: hint, filled: true, fillColor: const Color(0xFF161625), border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none)),
  );
}

class _PairingQrScanner extends StatefulWidget {
  const _PairingQrScanner();

  @override
  State<_PairingQrScanner> createState() => _PairingQrScannerState();
}

class _PairingQrScannerState extends State<_PairingQrScanner> {
  final MobileScannerController _controller = MobileScannerController();
  bool _completed = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_completed) return;
    for (final barcode in capture.barcodes) {
      final raw = barcode.rawValue?.trim() ?? '';
      if (raw.startsWith('gaia://pair')) {
        _completed = true;
        Navigator.pop(context, raw);
        return;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Escanear QR de GAIA')),
      body: Stack(
        fit: StackFit.expand,
        children: [
          MobileScanner(controller: _controller, onDetect: _onDetect),
          Center(child: Container(width: 260, height: 180, decoration: BoxDecoration(border: Border.all(color: Colors.white, width: 3), borderRadius: BorderRadius.circular(16)))),
          Positioned(bottom: 32, left: 20, right: 20, child: FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar'))),
        ],
      ),
    );
  }
}
