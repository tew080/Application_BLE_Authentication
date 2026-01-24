import 'package:flutter/foundation.dart';

void log(String massag) {
  // จะทำงานเมื่ออยู่ในหมด debug เท่านั้น (kDebugMode)
  if (kDebugMode) {
    debugPrint("[LOG DEBUG]: ${massag}");
  }
}
