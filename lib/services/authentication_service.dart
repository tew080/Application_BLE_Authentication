// นำเข้า FirestoreService เพื่อดึงข้อมูล User
import 'firestore_service.dart';
// นำเข้า LogdebugService
import '../services/logdebug_service.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
//import 'package:shared_preferences/shared_preferences.dart';
import 'package:device_marketing_names/device_marketing_names.dart';

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
    final deviceNames = DeviceMarketingNames();
    String singleDeviceName = "Unknown";
    singleDeviceName = await deviceNames.getSingleName();

    String? studentSecretKey = await storage.read(key: 'student_secret_key');
    String? firstRun = await storage.read(key: 'firstRun');
    String setStatusfirstRun = 'isfirstRun';

    // เรียกดึงข้อมูล User จาก Firestore ตาม studentId
    final doc = await firestoreService.getUser(studentId);

    if (!doc.exists) {
      return false;
    }

    if (firstRun != 'isfirstRun') {
      await storage.write(key: 'firstRun', value: setStatusfirstRun);
      log("StudentSecretKey = $studentSecretKey");
      log("FirstRun = $firstRun");
    }

    if (firstRun != 'isfirstRun' && doc['loginStatus'] != 'true') {
      await FirestoreService().updateUser(studentId, {
        'studentSecretKey': studentSecretKey,
        'loginStatus': 'true',
        'device': singleDeviceName,
      });
      // ถ้ามีข้อมูล ให้ บันทึกข้อมูลลง Storage และคืนค่า true (Login สำเร็จ)
      await storage.write(key: 'my_student_id', value: studentId);
      log("Device name = $singleDeviceName");
      log("StudentSecretKey = $studentSecretKey");
      log("LOGIN studentId='$studentId'");
      log("IF 1");
      return true;
    }

    if (doc['device'] == singleDeviceName && doc['loginStatus'] == 'true') {
      // ถ้ามีข้อมูล ให้ บันทึกข้อมูลลง Storage และคืนค่า true (Login สำเร็จ)
      await storage.write(key: 'my_student_id', value: studentId);
      await FirestoreService().updateUser(studentId, {
        'studentSecretKey': studentSecretKey,
        'loginStatus': 'true',
        'device': singleDeviceName,
      });
      log("Device name = $singleDeviceName");
      log("StudentSecretKey = $studentSecretKey");
      log("LOGIN studentId='$studentId'");
      log("IF 2");
      return true;
    }

    // ตรวจสอบว่ามีเอกสาร (Document) นี้อยู่ในฐานข้อมูลหรือไม่
    if (doc['loginStatus'] == 'true' ||
        doc['studentSecretKey'] != studentSecretKey) {
      // ถ้าไม่มีข้อมูล ให้คืนค่า false (Login ไม่สำเร็จ)
      log("IF 3");
      return false;
    } else {
      // ถ้ามีข้อมูล ให้ บันทึกข้อมูลลง Storage และคืนค่า true (Login สำเร็จ)
      await storage.write(key: 'my_student_id', value: studentId);
      await FirestoreService().updateUser(studentId, {
        'loginStatus': 'true',
        'device': singleDeviceName,
      });
      log("FirstRun = $firstRun");
      log("Device name = $singleDeviceName");
      log("StudentSecretKey = $studentSecretKey");
      log("LOGIN studentId='$studentId'");
      log("ESLE");
      return true;
    }
  }
}
