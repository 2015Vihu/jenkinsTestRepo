import 'package:flutter/material.dart';
import 'dart:developer';

class UserProfileWidget extends StatelessWidget {
  UserProfileWidget({super.key});

  @override
  Widget build(BuildContext context) {
    print('Building ListView');

    return ListView(
      children: [
        Container(child: Text('Profile Item 1'), padding: EdgeInsets.all(16)),
        Container(child: Text('Profile Item 2'), padding: EdgeInsets.all(16)),
        ListTile(
          leading: Icon(Icons.person),
          title: Text('Alok'),
          subtitle: Text('Flutter Developer'),
        ),
        Row(
          children: [
            ElevatedButton(
              onPressed: () {
                print('Button clicked');
              },
              child: Text('View Profile'),
            ),
            ElevatedButton(
              onPressed: () {
                print('Button clicked');
              },
              child: Text('View Profile'),
            ),
          ],
        ),
      ],
    );
  }
}
