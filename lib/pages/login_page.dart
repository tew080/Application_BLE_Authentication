import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../services/authentication_service.dart';
import '../services/logdebug_service.dart';
import '../services/firestore_service.dart'; // 新增
import 'bleadvertise_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _studentIdCtrl = TextEditingController();
  final _smsCodeCtrl = TextEditingController();

  String error = '';
  bool loading = false;
  bool _isOtpSent = false; // สถานะแสดงฟิลด์ OTP
  String _verificationId = ''; // เก็บ verificationId จาก Firebase
  String _currentPhone = ''; // เบอร์ที่ดึงจาก Firestore

  // ตรวจสอบ studentId และดึงเบอร์โทรศัพท์จาก Firestore
  Future<void> _sendOtp() async {
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
      // ดึงข้อมูล student จาก Firestore
      final doc = await FirestoreService().getUser(studentId);
      if (!doc.exists) {
        setState(() {
          error = '*ไม่พบรหัสนักศึกษาในระบบ*';
          loading = false;
        });
        return;
      }

      final phone = doc['phone'] as String?;
      if (phone == null || phone.isEmpty) {
        setState(() {
          error = '*ไม่พบเบอร์โทรศัพท์ที่ลงทะเบียนไว้*';
          loading = false;
        });
        return;
      }

      _currentPhone = phone;

      // เริ่มส่ง OTP
      await FirebaseAuth.instance.verifyPhoneNumber(
        phoneNumber: phone,
        verificationCompleted: (PhoneAuthCredential credential) async {
          // กรณีกรอกอัตโนมัติ (rare) ให้ยืนยันทันที
          await _signInWithCredential(credential, studentId);
        },
        verificationFailed: (FirebaseAuthException e) {
          setState(() {
            error = 'ส่ง OTP ไม่สำเร็จ: ${e.message}';
            loading = false;
          });
        },
        codeSent: (String verificationId, int? resendToken) {
          setState(() {
            _verificationId = verificationId;
            _isOtpSent = true;
            loading = false;
          });
        },
        codeAutoRetrievalTimeout: (String verificationId) {
          _verificationId = verificationId;
        },
      );
    } catch (e) {
      setState(() {
        error = 'เกิดข้อผิดพลาด: $e';
        loading = false;
      });
    }
  }

  // ยืนยัน OTP และเข้าสู่ระบบ
  Future<void> _verifyOtp() async {
    final smsCode = _smsCodeCtrl.text.trim();
    if (smsCode.isEmpty || _verificationId.isEmpty) {
      setState(() => error = '*กรอกรหัส OTP*');
      return;
    }

    setState(() {
      loading = true;
      error = '';
    });

    try {
      final credential = PhoneAuthProvider.credential(
        verificationId: _verificationId,
        smsCode: smsCode,
      );
      await _signInWithCredential(credential, _studentIdCtrl.text.trim());
    } catch (e) {
      setState(() {
        error = 'รหัส OTP ไม่ถูกต้อง';
        loading = false;
      });
    }
  }

  // หลังจากยืนยัน OTP สำเร็จ เรียก AuthenticationService.login
  Future<void> _signInWithCredential(
    PhoneAuthCredential credential,
    String studentId,
  ) async {
    try {
      // ถ้ายังไม่ได้ sign-in ด้วย Firebase Auth (optional)
      await FirebaseAuth.instance.signInWithCredential(credential);

      // เรียก login เดิม (ตรวจสอบ device, loginStatus, studentSecretKey)
      final bool ok = await AuthenticationService.login(studentId);
      if (!ok) {
        setState(() {
          error = '*ไม่สามารถเข้าสู่ระบบ โปรดลองอีกครั้ง*';
          loading = false;
        });
        return;
      }

      // ไปหน้า Advertise
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => AdvertisePage(studentId: studentId)),
      );
    } catch (e) {
      setState(() {
        error = 'ยืนยัน OTP ไม่สำเร็จ: $e';
        loading = false;
      });
    }
  }

  // กลับไปแก้ไข studentId
  void _resetOtpStep() {
    setState(() {
      _isOtpSent = false;
      _verificationId = '';
      _smsCodeCtrl.clear();
      error = '';
    });
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
            // ช่องกรอกรหัสนักศึกษา (disable ขณะกำลังส่ง OTP หรือกำลังยืนยัน)
            TextField(
              controller: _studentIdCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'รหัสนักศึกษา'),
              enabled: !_isOtpSent && !loading,
            ),
            const SizedBox(height: 20),

            // ถ้าส่ง OTP แล้ว จะแสดงช่องกรอกรหัส OTP และเบอร์ที่ส่งไป
            if (_isOtpSent) ...[
              Text(
                'ส่งรหัส OTP ไปยัง $_currentPhone',
                style: const TextStyle(fontSize: 14, color: Colors.grey),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _smsCodeCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'รหัส OTP 6 หลัก'),
                enabled: !loading,
              ),
              const SizedBox(height: 10),
              TextButton(
                onPressed: loading ? null : _resetOtpStep,
                child: const Text('เปลี่ยนรหัสนักศึกษา'),
              ),
            ],

            // แสดง error
            if (error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  error,
                  style: const TextStyle(
                    color: Colors.red,
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),

            const SizedBox(height: 20),

            // ปุ่มหลัก: เปลี่ยนข้อความตามสถานะ
            ElevatedButton(
              onPressed: loading ? null : (_isOtpSent ? _verifyOtp : _sendOtp),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blue,
                foregroundColor: Colors.white,
                minimumSize: const Size(200, 50),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(30),
                ),
              ),
              child: Text(
                loading
                    ? 'กำลังดำเนินการ...'
                    : (_isOtpSent ? 'ยืนยัน OTP' : 'ขอรหัส OTP'),
                style: const TextStyle(fontSize: 16),
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
    _smsCodeCtrl.dispose();
    super.dispose();
  }
}
