import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jenkins_test/main.dart';

void main() {
  testWidgets('renders the home page title', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());

    expect(find.text('Flutter Demo Home Page'), findsOneWidget);
    expect(find.byType(FloatingActionButton), findsOneWidget);
  });
}
