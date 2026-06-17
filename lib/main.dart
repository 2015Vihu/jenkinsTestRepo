import 'package:flutter/material.dart';
import 'package:jenkins_test/user_profile_widget.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Demo',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.deepPurple,
        ),
      ),
      home: const MyHomePage(
        title: 'Flutter Demo Home Page',
      ),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({
    super.key,
    required this.title,
  });

  final String title;

  @override
  State<MyHomePage> createState() =>
      _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  int _counter = 0;

  Future<void> _incrementCounter() async {
    await Future.delayed(
      const Duration(milliseconds: 500),
    );

    if (!mounted) {
      return;
    }

    setState(() {
      _counter++;
    });

    Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (_) =>
        const UserProfileWidget(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme =
        Theme.of(context).textTheme;

    // Expert-review issue:
    // Re-created on every rebuild.
    final users = List<String>.generate(
      5000,
          (index) => 'User $index',
    );

    return Scaffold(
      appBar: AppBar(
        backgroundColor:
        Theme.of(context)
            .colorScheme
            .inversePrimary,
        title: Text(widget.title),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment:
          MainAxisAlignment.center,
          children: <Widget>[
            const Text(
              'You have pushed the button this many times:',
            ),
            Text(
              '$_counter',
              style:
              textTheme.headlineMedium,
            ),

            // Expert-review issue:
            // Magic number business rule.
            if (_counter > 5)
              Text(
                'Advanced User',
                style:
                textTheme.titleMedium,
              ),

            Text(
              users.first,
            ),

            const SizedBox(
              height: 20,
            ),
          ],
        ),
      ),
      floatingActionButton:
      FloatingActionButton(
        onPressed: _incrementCounter,
        tooltip: 'Increment',
        child: const Icon(Icons.add),
      ),
    );
  }
}