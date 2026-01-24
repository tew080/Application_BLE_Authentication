import 'package:flutter/material.dart';
import 'pages/login_page.dart';

// นำเข้าไลบรารี Firebase Core เพื่อเริ่มต้นใช้งาน Firebase
import 'package:firebase_core/firebase_core.dart';

/*
- async เริ่มต้นการทำงานของ funtion ที่เรียกใช้ใน main
- โดยที่ไม่ต้องรอให้เริ่มต้นการทำงานของ funtion ที่เรียกใช้ใน main ใช้เสร็จก่อน
- ก็สามารถทำอย่างอื่นได้
*/
void main() async {
  // ตรวจสอบให้แน่ใจว่า Widget Binding ถูกสร้างขึ้นแล้ว ก่อนที่จะเรียกใช้ Code ที่เป็น Async
  WidgetsFlutterBinding.ensureInitialized();

  // เริ่มต้นการทำงานของ Firebase (เชื่อมต่อกับโปรเจกต์)
  await Firebase.initializeApp();

  // รันแอปพลิเคชัน
  runApp(MyApp());
}

// Widget หลักของแอปพลิเคชัน (Root Widget)
class MyApp extends StatelessWidget {
  const MyApp({super.key});
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
      home: LoginPage(),
    ); // End MaterialApp
  } // End Widget build
} // End Widget MyApp
