import 'package:flutter_test/flutter_test.dart';
import 'package:lumen_mobile/main.dart';

void main() {
  testWidgets('GAIA root widget is buildable', (WidgetTester tester) async {
    await tester.pumpWidget(const LumenApp());
    expect(find.byType(LumenApp), findsOneWidget);
  });
}
