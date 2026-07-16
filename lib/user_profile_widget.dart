import 'package:flutter/material.dart';

class UserProfileWidget extends StatelessWidget {
  UserProfileWidget({Key? key}) : super(key: key); // Issue 1

  void _onViewProfilePressed() {
    print('View Profile clicked'); // Issue 2
  }

  @override
  Widget build(BuildContext context) {
    print('Building UserProfileWidget'); // Issue 2

    final titleStyle = TextStyle( // Issue 3
      fontSize: 18,
      color: Colors.black,
    );

    return ListView(
      children: [
        Padding( // Issue 4
          padding: EdgeInsets.all(16),
          child: Text(
            'Profile Item 1',
            style: titleStyle,
          ),
        ),
        Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'Profile Item 2',
            style: titleStyle,
          ),
        ),
        ListTile(
          leading: Icon(Icons.person), // Issue 5
          title: Text('Alok'),
          subtitle: Text('Flutter Developer'),
        ),
        Row( // Issue 6
          children: [
            ElevatedButton(
              onPressed: () { // Issue 7
                _onViewProfilePressed();
              },
              child: Text('View Profile'),
            ),
            ElevatedButton(
              onPressed: () {
                _onViewProfilePressed();
              },
              child: Text('View Profile'),
            ),
          ],
        ),
      ],
    );
  }
}