/*import 'package:ulid/ulid.dart';

void main() {
  print(Ulid());
  print(Ulid().toUuid());
  }*/
/*
import 'package:nanoid/nanoid.dart';

void main() {
  var id = nanoid();
  print(id);

  var custom_length_id = nanoid(6);
  print(custom_length_id);
  }*/

import 'dart:math';

String getHex(int len) {
  // สร้างตัวสุ่มแบบ Secure เตรียมไว้
  final random = Random.secure();

  // สร้าง List ตามจำนวน len -> สุ่มเลข 0-15 -> แปลงเป็นฐาน 16 -> ต่อข้อความ
  return List.generate(len, (index) {
    return random.nextInt(16).toRadixString(16);
  }).join();
}

void main() {
  print(getHex(17)); // ตัวอย่างผลลัพธ์: "a3f190bc42d1"
}
