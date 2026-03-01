import 'dart:math';

String generateKey(int len, String type) {
  // สร้างตัวสุ่มแบบ Secure เตรียมไว้
  final random = Random.secure();
  // สร้าง List ตามจำนวน len -> สุ่มเลข 0-15 -> แปลงเป็นฐาน 16 -> ต่อข้อความ
  return List.generate(len, (index) {
    if (type == "key") {
      return random.nextInt(16).toRadixString(16);
    } else if (type == "otp") {
      return random.nextInt(10).toString();
    } else {
      return 0;
    }
  }).join();
}
