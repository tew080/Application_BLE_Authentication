import 'dart:math';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:mailer/mailer.dart';
import 'package:mailer/smtp_server.dart';

import '../services/authentication_service.dart';
import '../services/logdebug_service.dart';
import '../services/firestore_service.dart';
import 'bleadvertise_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _studentIdCtrl = TextEditingController();
  final _otpCtrl = TextEditingController();

  // 🟢 แก้ไข 1: เปลี่ยนมาใช้ GoogleSignIn.instance แทน
  final GoogleSignIn _googleSignIn = GoogleSignIn.instance;
  // เพิ่มตัวแปรเช็คว่า Initialize แล้วหรือยัง
  bool _isGoogleSignInInitialized = false;

  String error = '';
  bool loading = false;
  bool _isOtpSent = false;
  String _targetEmail = '';

  final String systemEmail = 'thammarat.tew@gmail.com';
  final String systemAppPassword = 'bbdg gzjl hqfg oczk';

  // --------------------------------------------------------
  // 1. ฟังก์ชันเลือกอีเมลจากเครื่อง และส่ง OTP
  // --------------------------------------------------------
  Future<void> _pickEmailAndSendOtp() async {
    final studentId = _studentIdCtrl.text.trim();
    if (studentId.isEmpty) {
      setState(() => error = '*กรุณากรอกรหัสนักศึกษา*');
      return;
    }

    setState(() {
      loading = true;
      error = '';
    });

    try {
      final doc = await FirestoreService().getUser(studentId);
      if (!doc.exists) {
        setState(() {
          error = 'ไม่พบรหัสนักศึกษานี้ในระบบ';
          loading = false;
        });
        return;
      }

      // 🟢 แก้ไข 2: ต้องสั่ง Initialize 1 ครั้งก่อนดึงหน้าต่างอีเมล (กฎใหม่ของ v7+)
      if (!_isGoogleSignInInitialized) {
        await _googleSignIn.initialize();
        _isGoogleSignInInitialized = true;
      }

      // 🟢 แก้ไข 3: เปลี่ยนจาก signIn() เป็น authenticate() และใช้ try-catch ดักเมื่อผู้ใช้กดยกเลิก
      GoogleSignInAccount? account;
      try {
        account = await _googleSignIn.authenticate(scopeHint: ['email']);
      } catch (e) {
        // ผู้ใช้กดยกเลิกหน้าต่างเลือกอีเมล
        setState(() => loading = false);
        return;
      }

      if (account == null) {
        setState(() => loading = false);
        return;
      }

      final String selectedEmail = account.email;
      log("ผู้ใช้เลือกอีเมล: $selectedEmail");

      // ผูกอีเมลที่เลือกเข้ากับรหัสนักศึกษาใน Firestore
      await FirestoreService().updateUser(studentId, {'email': selectedEmail});

      // สั่ง SignOut เพื่อให้รอบหน้ากดเลือกบัญชีใหม่ได้
      await _googleSignIn.signOut();

      // สร้างรหัส OTP สุ่ม 6 หลัก
      String otp = (Random().nextInt(900000) + 100000).toString();

      // 🟢 เพิ่มส่วนนี้: กำหนดเวลาหมดอายุ (เช่น 5 นาทีจากเวลาปัจจุบัน)
      int expiryTime = DateTime.now()
          .add(const Duration(minutes: 1))
          .millisecondsSinceEpoch;

      // 🟢 แก้ไขส่วนนี้: บันทึก OTP และ otp_expiry ลง Firestore
      await FirestoreService().updateUser(studentId, {
        'current_otp': otp,
        'otp_expiry': expiryTime,
      });

      // สั่งส่งอีเมลแจ้ง OTP
      final smtpServer = gmail(systemEmail, systemAppPassword);
      final message = Message()
        ..from = Address(systemEmail, 'ระบบเข้าสู่ระบบ BLE')
        ..recipients.add(selectedEmail)
        ..subject = 'รหัส OTP ของคุณคือ: $otp'
        ..html =
            """
                <div style="font-family: sans-serif; padding: 20px;">
                  <h2>รหัสยืนยันตัวตน (OTP)</h2>
                  <p>รหัสสำหรับเข้าสู่ระบบของคุณคือ:</p>
                  <h1 style="color: #2196F3; font-size: 32px; letter-spacing: 5px;">$otp</h1>
                  <p style="color: #888;">กรุณานำรหัสนี้ไปกรอกในแอปพลิเคชัน</p>
                  <p style="color: red; font-weight: bold;">*รหัสนี้มีอายุการใช้งาน 1 นาที*</p>
                </div>
              """;

      await send(message, smtpServer);

      setState(() {
        _isOtpSent = true;
        _targetEmail = selectedEmail;
        loading = false;
      });
      log("ส่ง OTP: $otp ไปที่ $_targetEmail สำเร็จแล้ว");
    } catch (e) {
      log("Error pick email or send OTP: $e");
      setState(() {
        error = 'เกิดข้อผิดพลาด: $e';
        loading = false;
      });
      // ป้องกันการค้างของ Session เผื่อเกิด Error
      try {
        await _googleSignIn.signOut();
      } catch (_) {}
    }
  }

  // --------------------------------------------------------
  // 2. ฟังก์ชันตรวจสอบรหัส OTP ที่ผู้ใช้กรอก
  // --------------------------------------------------------
  Future<void> _verifyOtp() async {
    final studentId = _studentIdCtrl.text.trim();
    final inputOtp = _otpCtrl.text.trim();

    if (inputOtp.isEmpty || inputOtp.length != 6) {
      setState(() => error = '*กรุณากรอกรหัส OTP 6 หลักให้ครบถ้วน*');
      return;
    }

    setState(() {
      loading = true;
      error = '';
    });

    try {
      final doc = await FirestoreService().getUser(studentId);
      final data = doc.data() as Map<String, dynamic>?;

      // ดึงข้อมูล OTP และ เวลาหมดอายุ
      final savedOtp = data != null && data.containsKey('current_otp')
          ? data['current_otp'].toString()
          : '';

      // 🟢 ดึงเวลาหมดอายุออกมา (ถ้าไม่มีให้เป็น 0)
      final expiryTime = data != null && data.containsKey('otp_expiry')
          ? data['otp_expiry'] as int
          : 0;

      if (inputOtp == savedOtp && savedOtp.isNotEmpty) {
        // 🟢 เพิ่มส่วนนี้: ตรวจสอบเวลาหมดอายุ
        if (DateTime.now().millisecondsSinceEpoch > expiryTime) {
          setState(() {
            error = 'รหัส OTP หมดอายุแล้ว กรุณาขอรหัสใหม่อีกครั้ง';
            loading = false;
          });
          // เคลียร์ OTP ที่หมดอายุทิ้งเพื่อความปลอดภัย
          await FirestoreService().updateUser(studentId, {
            'current_otp': '',
            'otp_expiry': 0,
          });
          return;
        }

        // 🟢 แก้ไขส่วนนี้: เคลียร์ทั้ง OTP และเวลาทิ้งเมื่อใช้สำเร็จแล้ว
        await FirestoreService().updateUser(studentId, {
          'current_otp': '',
          'otp_expiry': 0,
        });

        bool isSuccess = await AuthenticationService.login(studentId);

        if (isSuccess && mounted) {
          log("OTP ถูกต้อง เข้าสู่ระบบสำเร็จ!");
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => AdvertisePage(studentId: studentId),
            ),
          );
        } else {
          setState(() {
            error = 'ระบบฐานข้อมูลขัดข้อง (ไม่สามารถเข้าสู่ระบบได้)';
            loading = false;
          });
        }
      } else {
        setState(() {
          error = 'รหัส OTP ไม่ถูกต้อง กรุณาลองใหม่';
          loading = false;
        });
      }
    } catch (e) {
      log("Error verifying OTP: $e");
      setState(() {
        error = 'เกิดข้อผิดพลาดในการตรวจสอบข้อมูล';
        loading = false;
      });
    }
  }

  // --------------------------------------------------------
  // ส่วนแสดงผล UI (ยังคงเหมือนเดิมทั้งหมด)
  // --------------------------------------------------------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('เข้าสู่ระบบ'),
        backgroundColor: Colors.blue,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            Icon(
              _isOtpSent ? Icons.mark_email_read : Icons.account_circle,
              size: 80,
              color: _isOtpSent ? Colors.green : Colors.blue,
            ),
            const SizedBox(height: 30),

            TextField(
              controller: _studentIdCtrl,
              enabled: !_isOtpSent,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'รหัสนักศึกษา',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.person),
              ),
            ),
            const SizedBox(height: 20),

            if (_isOtpSent) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Text(
                  'ส่งรหัส OTP 6 หลักไปที่:\n$_targetEmail\nกรุณาตรวจสอบในกล่องจดหมายของคุณ',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.green,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _otpCtrl,
                keyboardType: TextInputType.number,
                maxLength: 6,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 24, letterSpacing: 8),
                decoration: const InputDecoration(
                  labelText: 'รหัส OTP 6 หลัก',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.password),
                ),
              ),
              TextButton(
                onPressed: () {
                  setState(() {
                    _isOtpSent = false;
                    _otpCtrl.clear();
                    error = '';
                  });
                },
                child: const Text(
                  'เปลี่ยนรหัสนักศึกษา / เปลี่ยนอีเมล',
                  style: TextStyle(color: Colors.grey),
                ),
              ),
            ],

            if (error.isNotEmpty) ...[
              Text(
                error,
                style: const TextStyle(
                  color: Colors.red,
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 10),
            ],

            const SizedBox(height: 20),

            ElevatedButton.icon(
              onPressed: loading
                  ? null
                  : (_isOtpSent ? _verifyOtp : _pickEmailAndSendOtp),
              icon: loading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2,
                      ),
                    )
                  : Icon(_isOtpSent ? Icons.login : Icons.email),
              label: Text(
                _isOtpSent
                    ? 'ยืนยัน OTP เพื่อเข้าสู่ระบบ'
                    : 'เลือกอีเมลในเครื่องเพื่อรับรหัส',
                style: const TextStyle(fontSize: 16),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: _isOtpSent ? Colors.green : Colors.blue,
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 55),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _studentIdCtrl.dispose();
    _otpCtrl.dispose();
    super.dispose();
  }
}
