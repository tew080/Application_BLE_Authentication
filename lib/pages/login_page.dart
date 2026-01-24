import 'package:flutter/material.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() {
    return _LoginPageState();
  }
}

class _LoginPageState extends State<LoginPage> {
  // กำหนดค่าเริ่มต้นให้กับตัวแปร error เป็น ค่าว่าง
  String error = '';
  // กำหนดค่าเริ่มต้นให้กับตัวแปร loading เป็น false
  bool loading = false;

  // รับค่าจาก รหัสนักศึกษาจาก TextField
  final studentIdCtrl = TextEditingController();
  // รับค่าจาก รหัส TextField
  final passwordCtrl = TextEditingController();

  void _checkLoginState() async {
    setState(() {
      // ให้เซ็ตตัวแปร loading = true เพื่อป้องกันการกดปุ่ม Login ซ้ำ
      loading = true;
      // ให้เซ็ตตัวแปร error = '' เพื่อเคลียร์ข้อความ error ที่แสดง
      error = '';
    });

    setState(() {
      // ให้เซ็ตตัวแปร loading = false เพื่อที่อนุญาตให้กดปุ่ม Login อีกครั้ง
      loading = false;
      /*
      - ให้แสดง '*ข้อมูลไม่ถูกต้อง*'
      - และให้เคลียร์ค่าใน TextField ทั้งหมด
      */
      error = '*ข้อมูลไม่ถูกต้อง*';
      studentIdCtrl.clear();
      passwordCtrl.clear();
    });
    debugPrint('Login Page ${loading}');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('เข้าสู่ระบบ')),
      body: Padding(
        padding: const EdgeInsets.all(44),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // TextField (), สร้างช่องรับค่าข้อมูล
            TextField(
              // ให้ TextField รับค่าจาก studentIdCtrl
              controller: studentIdCtrl,
              // รับค่าเป็นตัวเลขเท่านั้น
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'รหัสนักศึกษา'),
            ),
            const SizedBox(height: 12),
            TextField(
              // ให้ TextField รับค่าจาก passwordCtrl
              controller: passwordCtrl,
              // ซ้อนข้อความที่รับเข้ามา
              obscureText: true,
              decoration: const InputDecoration(labelText: 'รหัสผ่าน'),
            ),
            const SizedBox(height: 20),
            // ถ้า ค่าในตัวแปล error ไม่เป็นค่าว่าง แสดงว่ามีข้อผิดพลาด จาก setState();
            if (error.isNotEmpty)
              Text(
                error,
                style: const TextStyle(
                  color: Colors.red,
                  // กำหนดขนาดของตัวอักษร
                  fontSize: 16,
                  // กำหนดความหนาของตัวอักษร
                  fontWeight: FontWeight.bold,
                  // กำหนดระยะห่างระหว่างตัวอักษร
                  letterSpacing: 1,
                ),
              ),
            ElevatedButton(
              /*
              - ถ้าตัวแปร loading เป็น true ให้ปุ่มไม่สามารถกดได้
              - แต่ถ้าตัวแปร loading เป็น false ให้ปุ่มสามารถกดได้
              */
              onPressed: loading ? null : _checkLoginState,
              // กำหนดสไตล์ของปุ่ม
              style: ElevatedButton.styleFrom(
                // สีพื้นหลังของปุ่ม
                backgroundColor: Colors.blue,
                // สีเบื้องหน้าของปุ่ม
                foregroundColor: Colors.white,
                // กำหนดขนาดของปุ่ม
                minimumSize: Size(200, 50),
                shape: RoundedRectangleBorder(
                  // กำหนดขอบของปุ่ม
                  //side: BorderSide(color: Colors.indigoAccent, width: 2),
                  // กำหนดความโค้งของขอบปุ่ม
                  borderRadius: BorderRadius.circular(30.0),
                ),
              ),
              child: const Text(
                'ลงชื่อเข้าใช้',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  letterSpacing: 1,
                ), // End TextStyle
              ), // End Text
            ), // End ElevatedButton
          ], // End Row
        ), // End Column
      ), // End Container
    ); // End Scaffold
  } // End Widget build
} // End Class LoginPage
