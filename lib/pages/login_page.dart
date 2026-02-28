import 'package:flutter/material.dart';

// นำเข้า AuthenticationService
import '../services/authentication_service.dart';

// นำเข้า LogdebugService
import '../services/logdebug_service.dart';

// นำเข้าหน้า BleAdvertisePage
import 'bleadvertise_page.dart';

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

  void _checkLoginState() async {
    if (studentIdCtrl.text.isEmpty) {
      setState(() {
        error = '*กรุณากรอกข้อมูลให้ครบถ้วน*';
      });
      // จบการทำงานทันทีถ้าข้อมูลว่าง
      return;
    }

    setState(() {
      // ให้เซ็ตตัวแปร loading = true เพื่อป้องกันการกดปุ่ม Login ซ้ำ
      loading = true;
      // ให้เซ็ตตัวแปร error = '' เพื่อเคลียร์ข้อความ error ที่แสดง
      error = '';
    });

    // ดึงค่าจากช่องกรอก และลบช่องว่าง (Whitespace) ออกทั้งหมด
    final String studentId = studentIdCtrl.text.replaceAll(RegExp(r'\s+'), '');

    final bool ok = await AuthenticationService.login(studentId);
    if (ok == true) {
      log("Login Successfully Status = $ok");
      // เปลี่ยนหน้าไปที่ AdvertisePage และปิดหน้า Login ทิ้ง (Back ไม่ได้)
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) {
            return AdvertisePage(studentId: studentId);
          },
        ),
      );
      // จบการทำงาน
      return;
    }

    /*  mounted T/F from class State
     -  ถ้า (!mounted) แปลว่า "ถ้าหน้าจอนี้ไม่อยู่แล้ว"
     - ให้จบการทำงานตรงนี้เลย ไม่ต้องทำบรรทัดล่างต่อ
    */
    if (!mounted) {
      log('Login Page $mounted');
      return;
    }

    setState(() {
      // ให้เซ็ตตัวแปร loading = false เพื่อที่อนุญาตให้กดปุ่ม Login อีกครั้ง
      loading = false;
      /*
      - ให้แสดง '*ข้อมูลไม่ถูกต้อง*'
      - และให้เคลียร์ค่าใน TextField ทั้งหมด
      */
      error = '*ข้อมูลไม่ถูกต้อง*';
      studentIdCtrl.clear();
    });
    log('Loading Status $loading');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('เข้าสู่ระบบ')),
      body: Padding(
        padding: const EdgeInsets.all(64),
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
              style: const TextStyle(
                color: Colors.black,
                // กำหนดขนาดของตัวอักษร
                fontSize: 18,
                // กำหนดระยะห่างระหว่างตัวอักษร
                letterSpacing: 1.5,
              ),
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
            const SizedBox(height: 10),
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
                  fontSize: 18,
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
