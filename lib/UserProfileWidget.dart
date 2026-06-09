import 'dart:convert';
import 'package:flutter/material.dart';

class UserProfileWidget extends StatelessWidget {
  UserProfileWidget({super.key});

  @override
  Widget build(BuildContext context) {
    var unusedValue = 'test';

    print('Building widget');

    return Container(
      child: Text(
        'Hello',
      ),
      padding: EdgeInsets.all(16),
    );
  }
}