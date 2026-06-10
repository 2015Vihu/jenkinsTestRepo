import 'package:flutter/material.dart';
import 'dart:developer';

class UserProfileWidget extends StatelessWidget {
  UserProfileWidget({super.key});

  @override
  Widget build(BuildContext context) {
    var unusedValue = 'test';

    print('Building widget');

    return Row(
      children: [
        Container(
          child: Text(
              'Hello Alok this is the PR review code'
          ),
          padding: EdgeInsets.all(16),
          margin: EdgeInsets.all(8),
        ),
        Container(
          child: Text(
              'Second widget for lint testing'
          ),
          padding: EdgeInsets.all(16),
        ),
        ElevatedButton(
          onPressed: () {
            print('Button clicked');
          },
          child: Text(
              'Click Me'
          ),
        ),
      ],
    );
  }
}