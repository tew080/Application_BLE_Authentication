// นำเข้า FirestoreService เพื่อดึงข้อมูล User
import 'firestore_service.dart';
// นำเข้า LogdebugService
import '../services/logdebug_service.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AuthenticationService {
  //เข้ารหัสข้อมูลที่บันทึกในเครื่อง encryptedSharedPreferences = true (เพื่อให้อ่านข้อมูลที่เข้ารหัสได้)
  static const storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  // ฟังก์ชันสำหรับเข้าสู่ระบบ (Login)
  // รับค่า studentId และ password เข้ามา
  // คืนค่าเป็น Future<bool> (จริง/เท็จ)
  static Future<bool> login(String studentId) async {
    // สร้าง Instance ของ FirestoreService เพื่อใช้งาน
    final FirestoreService firestoreService = FirestoreService();
    String? studentSecretKey = await storage.read(key: 'student_secret_key');
    SharedPreferences prefs = await SharedPreferences.getInstance();

    // เช็คว่าเคยรันหรือยัง (ถ้าไม่เคย จะได้ค่า false)
    bool isFirstRun = prefs.getBool('isFirstRun') ?? true;
    log("First Run Ststus ='$isFirstRun'");
    if (isFirstRun) {
      await FirestoreService().updateUser(studentId, {
        'studentSecretKey': studentSecretKey,
      });
      log("First Run Set studentSecretKey = $studentSecretKey");
      // บันทึกว่าเคยรันแล้ว
      await prefs.setBool('isFirstRun', false);
    }

    // เรียกดึงข้อมูล User จาก Firestore ตาม studentId
    final doc = await firestoreService.getUser(studentId);
    // ตรวจสอบว่ามีเอกสาร (Document) นี้อยู่ในฐานข้อมูลหรือไม่
    if (!doc.exists ||
        doc['loginStatus'] == 'true' ||
        doc['studentSecretKey'] != studentSecretKey) {
      // ถ้าไม่มีข้อมูล ให้คืนค่า false (Login ไม่สำเร็จ)
      log("studentSecretKey = $studentSecretKey");
      return false;
    } else {
      // ถ้ามีข้อมูล ให้ บันทึกข้อมูลลง Storage และคืนค่า true (Login สำเร็จ)
      await storage.write(key: 'my_student_id', value: studentId);
      await FirestoreService().updateUser(studentId, {'loginStatus': 'true'});
      log("LOGIN studentId='$studentId'");
      return true;
    }
  }
}
