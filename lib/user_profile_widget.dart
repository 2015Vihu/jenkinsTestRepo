import 'package:flutter/material.dart';

class UserProfileWidget extends StatelessWidget {
  const UserProfileWidget({super.key});

  void _onViewProfilePressed() {
    debugPrint('View Profile clicked');
  }

  @override
  Widget build(BuildContext context) {
    debugPrint('Building UserProfileWidget');

    const titleStyle = TextStyle(
      fontSize: 18,
      color: Colors.black,
    );

    return ListView(
      children: <Widget>[
        const Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'Profile Item 1',
            style: titleStyle,
          ),
        ),
        const Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'Profile Item 2',
            style: titleStyle,
          ),
        ),
        const ListTile(
          leading: Icon(Icons.person),
          title: Text('Alok'),
          subtitle: Text('Flutter Developer'),
        ),
        Row(
          children: <Widget>[
            ElevatedButton(
              onPressed: _onViewProfilePressed,
              child: const Text('View Profile'),
            ),
            ElevatedButton(
              onPressed: _onViewProfilePressed,
              child: const Text('View Profile'),
            ),
          ],
        ),
      ],
    );
  }
}