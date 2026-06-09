import 'dart:convert';
import 'package:flutter/material.dart';

class UserProfileWidget extends StatelessWidget {
  UserProfileWidget({super.key});

  @override
  Widget build(BuildContext context) {
    var unusedValue = 'test';

    print('Building widget');

    return Row(
      children: [
        Container(
          child: Text('Hello Alok this is the PR review code'),
          padding: EdgeInsets.all(16),
        ),
        Container(
          child: Text('Hello Alok this is the PR review code'),
          padding: EdgeInsets.all(16),
        ),
      ],
    );
  }
}
