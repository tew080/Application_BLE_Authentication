// นำเข้า FirestoreService เพื่อดึงข้อมูล User
import 'firestore_service.dart';

// นำเข้าไลบรารี Flutter Secure Storage เพื่อจัดเก็บข้อมูลในเครื่อง
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthenticationService {
  // ฟังก์ชันสำหรับเข้าสู่ระบบ (Login)
  // รับค่า studentId และ password เข้ามา
  // คืนค่าเป็น Future<bool> (จริง/เท็จ)
  //static Future<bool> login(String studentId, String password) async {
  static Future<bool> login(String studentId) async {
    // สร้าง FlutterSecureStorage เพื่อจัดเก็บข้อมูลในเครื่อง
    const storage = FlutterSecureStorage(
      // encryptedSharedPreferences = true เพื่อเข้ารหัสข้อมูลที่จัดเก็บในเครื่อง
      aOptions: AndroidOptions(encryptedSharedPreferences: true),
    );

    // สร้าง Instance ของ FirestoreService เพื่อใช้งาน
    final FirestoreService firestoreService = FirestoreService();

    // เรียกดึงข้อมูล User จาก Firestore ตาม studentId
    final doc = await firestoreService.getUser(studentId);

    // ตรวจสอบว่ามีเอกสาร (Document) นี้อยู่ในฐานข้อมูลหรือไม่
    if (!doc.exists) {
      // ถ้าไม่มีข้อมูล ให้คืนค่า false (Login ไม่สำเร็จ)
      return false;
    }

    // ถ้ามีข้อมูล ให้เขียน studentId ลงใน Storage
    await storage.write(key: 'student_id', value: studentId);
    return true;
  }
}
