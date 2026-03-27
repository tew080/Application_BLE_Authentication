import 'package:flutter/material.dart';
import 'pages/login_page.dart';
// นำเข้าไลบรารี Firebase Core เพื่อเริ่มต้นใช้งาน Firebase
import 'package:firebase_core/firebase_core.dart';
// นำเข้าไลบรารี Flutter Secure Storage เพื่ออ่านข้อมูลที่จัดเก็บในเครื่อง
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
// นำเข้าหน้า BleAdvertisePage
import '../pages/bleadvertise_page.dart';
// นำเข้า LogdebugService
import '../services/logdebug_service.dart';
// นำเข้า GenerateKeyService สำหรับการสร้างคีย์
import '../services/generatekey_service.dart';

/*
- async เริ่มต้นการทำงานของ funtion ที่เรียกใช้ใน main
- โดยที่ไม่ต้องรอให้เริ่มต้นการทำงานของ funtion ที่เรียกใช้ใน main ใช้เสร็จก่อน
- ก็สามารถทำอย่างอื่นได้
*/
void main() async {
  // ตรวจสอบให้แน่ใจว่า Widget Binding ถูกสร้างขึ้นแล้ว ก่อนที่จะเรียกใช้ Code ที่เป็น Async
  WidgetsFlutterBinding.ensureInitialized();

  // สร้าง FlutterSecureStorage เพื่ออ่านข้อมูลที่จัดเก็บในเครื่อง
  const storage = FlutterSecureStorage(
    // encryptedSharedPreferences = true เพื่อเข้ารหัสข้อมูลที่จัดเก็บในเครื่อง
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  // เริ่มต้นการทำงานของ Firebase (เชื่อมต่อกับโปรเจกต์)
  await Firebase.initializeApp();

  log('Creating new key...');
  String newKey = generateKey(8, "key");
  await storage.write(key: 'my_secret_key', value: newKey);
  log('newKey :$newKey');

  // ตรวจสอบว่ามี student_id อยู่ในเครื่องหรือไม่
  String? studentIDCheck = await storage.read(key: 'student_id');

  // รันแอปพลิเคชัน
  runApp(MyApp(startPage: studentIDCheck));
}

// Widget หลักของแอปพลิเคชัน (Root Widget)
class MyApp extends StatelessWidget {
  final String? startPage; // รับค่า studentId ที่เช็คมา
  const MyApp({super.key, this.startPage});
  // ส่วนของการสร้าง UI
  @override
  Widget build(BuildContext context) {
    // สร้าง MaterialApp เพื่อกำหนดโครงสร้างแอป
    return MaterialApp(
      theme: ThemeData(
        primarySwatch: Colors.blue,
        // กำหนดฟอนต์
        fontFamily: 'Google Sans',
      ),
      // กำหนดหน้าเริ่มต้นของแอปพลิเคชัน
      // ถ้ามี ID ให้ไปหน้า Advertise เลย, ถ้าไม่มีให้ไป Login
      home: startPage != null
          ? AdvertisePage(studentId: startPage!)
          : const LoginPage(),
    ); // End MaterialApp
  } // End Widget build
} // End Widget MyApp
