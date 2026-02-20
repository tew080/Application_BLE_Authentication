import 'dart:async'; // 🟢 เพิ่ม import สำหรับใช้งาน Timer
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

  final GoogleSignIn _googleSignIn = GoogleSignIn.instance;
  bool _isGoogleSignInInitialized = false;

  String error = '';
  bool loading = false;
  bool _isOtpSent = false;
  String _targetEmail = '';

  // 🟢 ตัวแปรสำหรับจัดการเวลาหน่วง 30 วินาที
  Timer? _resendTimer;
  int _resendCountdown = 0;

  final String systemEmail = 'thammarat.tew@gmail.com';
  final String systemAppPassword = 'bbdg gzjl hqfg oczk';

  // --------------------------------------------------------
  // ฟังก์ชันเริ่มนับเวลาถอยหลัง 30 วินาที
  // --------------------------------------------------------
  void _startResendTimer() {
    setState(() => _resendCountdown = 30);
    _resendTimer?.cancel();
    _resendTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_resendCountdown > 0) {
        setState(() => _resendCountdown--);
      } else {
        timer.cancel();
      }
    });
  }

  // --------------------------------------------------------
  // ฟังก์ชันขอรหัส OTP ใหม่ (ส่งไปอีเมลเดิม)
  // --------------------------------------------------------
  Future<void> _resendOtp() async {
    if (_resendCountdown > 0)
      return; // ป้องกันการกดซ้ำถ้าระบบยังนับเวลาไม่เสร็จ

    final studentId = _studentIdCtrl.text.trim();
    setState(() {
      loading = true;
      error = '';
    });

    try {
      // สร้างรหัส OTP สุ่ม 6 หลัก
      String otp = (Random().nextInt(900000) + 100000).toString();
      int expiryTime = DateTime.now()
          .add(const Duration(minutes: 1))
          .millisecondsSinceEpoch;

      // บันทึก OTP และเวลาหมดอายุลง Firestore
      await FirestoreService().updateUser(studentId, {
        'current_otp': otp,
        'otp_expiry': expiryTime,
      });

      // สั่งส่งอีเมลแจ้ง OTP
      final smtpServer = gmail(systemEmail, systemAppPassword);
      final message = Message()
        ..from = Address(systemEmail, 'ระบบเข้าสู่ระบบ BLE')
        ..recipients.add(_targetEmail)
        ..subject = 'รหัส OTP ใหม่ของคุณคือ: $otp'
        ..html =
            """
          <div style="font-family: sans-serif; padding: 20px;">
            <h2>รหัสยืนยันตัวตน (OTP) ใหม่</h2>
            <p>รหัสสำหรับเข้าสู่ระบบของคุณคือ:</p>
            <h1 style="color: #2196F3; font-size: 32px; letter-spacing: 5px;">$otp</h1>
            <p style="color: #888;">กรุณานำรหัสนี้ไปกรอกในแอปพลิเคชัน</p>
            <p style="color: red; font-weight: bold;">*รหัสนี้มีอายุการใช้งาน 1 นาที*</p>
          </div>
        """;

      await send(message, smtpServer);

      setState(() {
        loading = false;
        error = ''; // เคลียร์ข้อความ Error ทิ้งเมื่อส่งใหม่สำเร็จ
      });

      log("ส่ง OTP ใหม่: $otp ไปที่ $_targetEmail สำเร็จแล้ว");

      // เริ่มนับเวลาถอยหลัง 30 วินาทีใหม่
      _startResendTimer();
    } catch (e) {
      log("Error resend OTP: $e");
      setState(() {
        error = 'เกิดข้อผิดพลาดในการส่ง OTP ใหม่: $e';
        loading = false;
      });
    }
  }

  // --------------------------------------------------------
  // 1. ฟังก์ชันเลือกอีเมลจากเครื่อง และส่ง OTP ครั้งแรก
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

      if (!_isGoogleSignInInitialized) {
        await _googleSignIn.initialize();
        _isGoogleSignInInitialized = true;
      }

      GoogleSignInAccount? account;
      try {
        account = await _googleSignIn.authenticate(scopeHint: ['email']);
      } catch (e) {
        setState(() => loading = false);
        return;
      }

      if (account == null) {
        setState(() => loading = false);
        return;
      }

      final String selectedEmail = account.email;
      log("ผู้ใช้เลือกอีเมล: $selectedEmail");

      await FirestoreService().updateUser(studentId, {'email': selectedEmail});
      await _googleSignIn.signOut();

      String otp = (Random().nextInt(900000) + 100000).toString();
      int expiryTime = DateTime.now()
          .add(const Duration(minutes: 1))
          .millisecondsSinceEpoch;

      await FirestoreService().updateUser(studentId, {
        'current_otp': otp,
        'otp_expiry': expiryTime,
      });

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

      // 🟢 เริ่มนับเวลา 30 วิ ทันทีที่ส่งสำเร็จ
      _startResendTimer();
    } catch (e) {
      log("Error pick email or send OTP: $e");
      setState(() {
        error = 'เกิดข้อผิดพลาด: $e';
        loading = false;
      });
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

      final savedOtp = data != null && data.containsKey('current_otp')
          ? data['current_otp'].toString()
          : '';

      final expiryTime = data != null && data.containsKey('otp_expiry')
          ? data['otp_expiry'] as int
          : 0;

      if (inputOtp == savedOtp && savedOtp.isNotEmpty) {
        if (DateTime.now().millisecondsSinceEpoch > expiryTime) {
          setState(() {
            // 🟢 แจ้งเตือนหมดอายุ แต่ไม่เปลี่ยนหน้า เพื่อให้กดปุ่มส่งใหม่ได้
            error = 'รหัส OTP หมดอายุแล้ว กรุณากดขอรหัสใหม่อีกครั้ง';
            loading = false;
          });
          await FirestoreService().updateUser(studentId, {
            'current_otp': '',
            'otp_expiry': 0,
          });
          return;
        }

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
  // ส่วนแสดงผล UI
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

              // 🟢 ปุ่มขอ OTP ใหม่ พร้อมระบบนับเวลาถอยหลัง
              TextButton.icon(
                onPressed: _resendCountdown > 0 ? null : _resendOtp,
                icon: const Icon(Icons.refresh),
                label: Text(
                  _resendCountdown > 0
                      ? 'ขอรหัส OTP ใหม่ (รอ $_resendCountdown วินาที)'
                      : 'ขอรหัส OTP ใหม่',
                  style: TextStyle(
                    color: _resendCountdown > 0 ? Colors.grey : Colors.blue,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),

              TextButton(
                onPressed: () {
                  setState(() {
                    _isOtpSent = false;
                    _otpCtrl.clear();
                    error = '';
                    _resendTimer?.cancel(); // เคลียร์เวลาถอยหลังถ้ายกเลิก
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

  // 🟢 อย่าลืม Cancel Timer เมื่อปิดหน้า เพื่อป้องกัน Memory Leak
  @override
  void dispose() {
    _resendTimer?.cancel();
    _studentIdCtrl.dispose();
    _otpCtrl.dispose();
    super.dispose();
  }
}
