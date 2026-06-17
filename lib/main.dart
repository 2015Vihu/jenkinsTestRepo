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
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  int _counter = 0;

  // Review Issue #1:
  // Controller is never disposed.
  final TextEditingController _controller =
  TextEditingController();

  Future<void> _incrementCounter() async {
    debugPrint('Counter value before increment: $_counter');

    // Review Issue #2:
    // Artificial async gap.
    await Future.delayed(
      const Duration(seconds: 2),
    );

    // Review Issue #3:
    // Missing mounted check after async call.
    setState(() {
      _counter++;
    });

    // Review Issue #4:
    // Redundant rebuild.
    setState(() {});

    // Review Issue #5:
    // Navigation happens on every click,
    // creating an ever-growing navigation stack.
    Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (context) => const UserProfileWidget(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    // Review Issue #6:
    // Expensive allocation on every rebuild.
    final users = List.generate(
      10000,
          (index) => 'User $index',
    );

    return Scaffold(
      appBar: AppBar(
        backgroundColor:
        Theme.of(context).colorScheme.inversePrimary,
        title: Text(widget.title),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment:
          MainAxisAlignment.center,
          children: <Widget>[
            // Review Issue #7:
            // Missing const.
            Text(
              'You have pushed the button this many times:',
            ),

            TextField(
              controller: _controller,
              decoration: const InputDecoration(
                hintText: 'Enter name',
              ),
            ),

            Text(
              '$_counter',
              style: textTheme.headlineMedium,
            ),

            const SizedBox(height: 20),

            // Review Issue #8:
            // Magic number business rule.
            if (_counter > 5)
              Text(
                'Power User',
                style: textTheme.titleMedium,
              ),

            Text(
              users.first,
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