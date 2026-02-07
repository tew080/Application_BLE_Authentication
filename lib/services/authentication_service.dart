// นำเข้า FirestoreService เพื่อดึงข้อมูล User
import 'firestore_service.dart';

// นำเข้า LogdebugService
import '../services/logdebug_service.dart';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthenticationService {
  static const storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  // ฟังก์ชันสำหรับเข้าสู่ระบบ (Login)
  // รับค่า studentId และ password เข้ามา
  // คืนค่าเป็น Future<bool> (จริง/เท็จ)
  //static Future<bool> login(String studentId, String password) async {
  static Future<bool> login(String studentId) async {
    // สร้าง Instance ของ FirestoreService เพื่อใช้งาน
    final FirestoreService firestoreService = FirestoreService();

    // เรียกดึงข้อมูล User จาก Firestore ตาม studentId
    final doc = await firestoreService.getUser(studentId);

    // ตรวจสอบว่ามีเอกสาร (Document) นี้อยู่ในฐานข้อมูลหรือไม่
    if (!doc.exists) {
      // ถ้าไม่มีข้อมูล ให้คืนค่า false (Login ไม่สำเร็จ)
      return false;
    } else {
      // ถ้ามีข้อมูล ให้ บันทึกข้อมูลลง Storage และคืนค่า true (Login สำเร็จ)
      await storage.write(key: 'my_student_id', value: studentId);
      log("LOGIN studentId='$studentId'");
      return true;
    }

    /*log("LOGIN studentId='$studentId'");
    //log("PASSWORD from input='$password'");
    log("DB PASSWORD = ${doc['password']}");*/

    // ตรวจสอบรหัสผ่าน:
    // แปลงรหัสผ่านจาก DB เป็น String และเปรียบเทียบกับ password ที่กรอกมา
    /*if (doc['password'].toString() == password) {
      // ถ้าตรงกัน คืนค่า true (Login สำเร็จ)
      return true;
    } else {
      // ถ้าไม่ตรงกัน คืนค่า false
      return false;
    }*/
  }
}
