// นำเข้า FirestoreService เพื่อดึงข้อมูล User
import 'firestore_service.dart';

// นำเข้าไลบรารี Flutter Secure Storage เพื่อจัดเก็บข้อมูลในเครื่อง
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

// นำเข้า LogdebugService
import '../services/logdebug_service.dart';

class AuthenticationService {
  // สร้าง FlutterSecureStorage เพื่อจัดเก็บข้อมูลในเครื่อง
  static const storage = FlutterSecureStorage(
    // encryptedSharedPreferences = true เพื่อเข้ารหัสข้อมูลที่จัดเก็บในเครื่อง
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
  }
}
