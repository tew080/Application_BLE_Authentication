// ฟังก์ชันแปลง String เป็น ASCII Hex String
// ตัวอย่าง: "ABC" -> "414243"
String stringToAsciiHex(String input) {
  // 1. input.codeUnits: แปลงตัวอักษรเป็นรหัส ASCII (List<int>)
  // 2. map(...): วนลูปแปลงรหัส ASCII แต่ละตัวเป็นฐาน 16 (String)
  // 3. join(): นำ String ทั้งหมดมาต่อกัน
  return input.codeUnits.map((unit) {
    return unit.toRadixString(16);
  }).join();
}
