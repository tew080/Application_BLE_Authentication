import 'dart:async';
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
  bool _isChangingEmail = false;
  String _targetEmail = '';

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
  // ฟังก์ชันขอรหัส OTP ใหม่
  // --------------------------------------------------------
  Future<void> _resendOtp() async {
    if (_resendCountdown > 0) return;

    final studentId = _studentIdCtrl.text.trim();
    setState(() {
      loading = true;
      error = '';
    });

    try {
      String otp = (Random().nextInt(900000) + 100000).toString();
      int expiryTime = DateTime.now()
          .add(const Duration(minutes: 1))
          .millisecondsSinceEpoch;

      await FirestoreService().updateUser(studentId, {
        'current_otp': otp,
        'otp_expiry': expiryTime,
      });

      String subject = _isChangingEmail
          ? 'รหัส OTP ใหม่ สำหรับเปลี่ยนอีเมล: $otp'
          : 'รหัส OTP ใหม่ของคุณคือ: $otp';

      final smtpServer = gmail(systemEmail, systemAppPassword);
      final message = Message()
        ..from = Address(systemEmail, 'ระบบเข้าสู่ระบบ BLE')
        ..recipients.add(_targetEmail)
        ..subject = subject
        ..html =
            """
          <div style="font-family: sans-serif; padding: 20px;">
            <h2>รหัสยืนยันตัวตน (OTP) ใหม่</h2>
            <p>รหัสสำหรับยืนยันการทำรายการของคุณคือ:</p>
            <h1 style="color: #2196F3; font-size: 32px; letter-spacing: 5px;">$otp</h1>
            <p style="color: #888;">กรุณานำรหัสนี้ไปกรอกในแอปพลิเคชัน</p>
            <p style="color: red; font-weight: bold;">*รหัสนี้มีอายุการใช้งาน 1 นาที*</p>
          </div>
        """;

      await send(message, smtpServer);

      setState(() {
        loading = false;
        error = '';
      });

      log("ส่ง OTP ใหม่: $otp ไปที่ $_targetEmail สำเร็จแล้ว");
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
  // 1. ฟังก์ชันเลือกอีเมลจากเครื่อง และส่ง OTP (Login ปกติ)
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

      final data = doc.data() as Map<String, dynamic>?;
      final registeredEmail = data != null && data.containsKey('email')
          ? data['email'].toString().trim()
          : '';

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

      final String selectedEmail = account.email.trim();

      if (registeredEmail.isNotEmpty && registeredEmail != selectedEmail) {
        setState(() {
          error =
              'รหัสนักศึกษานี้ผูกกับอีเมล:\n$registeredEmail\nหากต้องการเปลี่ยน ให้กดปุ่ม "ต้องการเปลี่ยนอีเมลที่ผูกไว้" ด้านล่าง';
          loading = false;
        });
        await _googleSignIn.signOut();
        return;
      }

      if (registeredEmail.isEmpty) {
        await FirestoreService().updateUser(studentId, {
          'email': selectedEmail,
        });
      }

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
        _isChangingEmail = false;
        _targetEmail = selectedEmail;
        loading = false;
      });

      _startResendTimer();
    } catch (e) {
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
  // 2. ฟังก์ชันร้องขอเปลี่ยนอีเมล (ส่ง OTP ไปยังอีเมลเดิม)
  // --------------------------------------------------------
  Future<void> _requestEmailChange() async {
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

      final data = doc.data() as Map<String, dynamic>?;
      final registeredEmail = data != null && data.containsKey('email')
          ? data['email'].toString().trim()
          : '';

      if (registeredEmail.isEmpty) {
        setState(() {
          error =
              'รหัสนักศึกษานี้ยีงไม่ได้ผูกกับอีเมลใดๆ\nสามารถกดล็อคอินปกติเพื่อผูกอีเมลได้เลย';
          loading = false;
        });
        return;
      }

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
        ..recipients.add(registeredEmail)
        ..subject = 'รหัส OTP สำหรับเปลี่ยนอีเมล: $otp'
        ..html =
            """
          <div style="font-family: sans-serif; padding: 20px;">
            <h2>รหัสยืนยันตัวตน (OTP)</h2>
            <p>มีการร้องขอเพื่อ <b>เปลี่ยนอีเมล</b> ที่ผูกกับบัญชีของคุณ</p>
            <p>รหัสสำหรับยืนยันคือ:</p>
            <h1 style="color: #ff5722; font-size: 32px; letter-spacing: 5px;">$otp</h1>
            <p style="color: #888;">หากคุณไม่ได้ทำรายการนี้ กรุณาเพิกเฉยต่ออีเมลฉบับนี้</p>
            <p style="color: red; font-weight: bold;">*รหัสนี้มีอายุการใช้งาน 1 นาที*</p>
          </div>
        """;

      await send(message, smtpServer);

      setState(() {
        _isOtpSent = true;
        _isChangingEmail = true;
        _targetEmail = registeredEmail;
        loading = false;
      });

      _startResendTimer();
    } catch (e) {
      setState(() {
        error = 'เกิดข้อผิดพลาดในการส่ง OTP: $e';
        loading = false;
      });
    }
  }

  // --------------------------------------------------------
  // 3. ฟังก์ชันตรวจสอบรหัส OTP และบังคับเลือกอีเมลใหม่
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
            error = 'รหัส OTP หมดอายุแล้ว กรุณากดขอรหัสใหม่อีกครั้ง';
            loading = false;
          });
          await FirestoreService().updateUser(studentId, {
            'current_otp': '',
            'otp_expiry': 0,
          });
          return;
        }

        // ==========================================
        // 🟢 กรณีอยู่ในโหมด "เปลี่ยนอีเมล"
        // ==========================================
        if (_isChangingEmail) {
          // 1. ล้างค่า OTP ก่อน แต่ยัง "ไม่ลบอีเมลเดิม"
          await FirestoreService().updateUser(studentId, {
            'current_otp': '',
            'otp_expiry': 0,
          });

          // 2. บังคับ SignOut Google Session เก่าทิ้ง
          if (!_isGoogleSignInInitialized) {
            await _googleSignIn.initialize();
            _isGoogleSignInInitialized = true;
          }
          try {
            await _googleSignIn.signOut();
          } catch (_) {}

          // 3. เด้งหน้าต่างบังคับให้เลือก Google Account ทันที
          GoogleSignInAccount? account;
          try {
            account = await _googleSignIn.authenticate(scopeHint: ['email']);
          } catch (e) {
            setState(() => loading = false);
            return;
          }

          // 4. ถ้าผู้ใช้กดยกเลิก ไม่เลือกอีเมล (ปิดหน้าต่างไป)
          if (account == null) {
            setState(() {
              error = 'คุณยกเลิกการเลือกอีเมลใหม่ (อีเมลเดิมยังคงอยู่)';
              _isOtpSent = false;
              _isChangingEmail = false;
              _otpCtrl.clear();
              _resendTimer?.cancel();
              loading = false;
            });
            return; // 🛑 หยุดการทำงาน อีเมลเก่ายังปลอดภัย
          }

          // 5. ถ้าเลือกอีเมลสำเร็จ นำอีเมลใหม่มาอัปเดตทับ
          final String newSelectedEmail = account.email.trim();

          await FirestoreService().updateUser(studentId, {
            'email': newSelectedEmail,
          });

          // สั่ง SignOut อีกรอบเพื่อเคลียร์แคชสำหรับการล็อคอินครั้งต่อไป
          await _googleSignIn.signOut();

          // 6. กลับไปหน้าแรก พร้อมแจ้งเตือนว่าสำเร็จ
          setState(() {
            _isOtpSent = false;
            _isChangingEmail = false;
            _otpCtrl.clear();
            _resendTimer?.cancel();
            loading = false;
            error = '';
          });

          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  '✅ เปลี่ยนเป็นอีเมล $newSelectedEmail สำเร็จ! กรุณาเข้าสู่ระบบ',
                ),
                backgroundColor: Colors.green,
                duration: const Duration(seconds: 4),
              ),
            );
          }
        }
        // ==========================================
        // 🟢 กรณีอยู่ในโหมด "เข้าสู่ระบบปกติ"
        // ==========================================
        else {
          await FirestoreService().updateUser(studentId, {
            'current_otp': '',
            'otp_expiry': 0,
          });

          bool isSuccess = await AuthenticationService.login(studentId);

          if (isSuccess && mounted) {
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
        }
      } else {
        setState(() {
          error = 'รหัส OTP ไม่ถูกต้อง กรุณาลองใหม่';
          loading = false;
        });
      }
    } catch (e) {
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
        title: Text(
          _isChangingEmail && _isOtpSent
              ? 'ยืนยันเพื่อเปลี่ยนอีเมล'
              : 'เข้าสู่ระบบ',
        ),
        backgroundColor: _isChangingEmail && _isOtpSent
            ? Colors.orange
            : Colors.blue,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            Icon(
              _isOtpSent ? Icons.mark_email_read : Icons.account_circle,
              size: 80,
              color: _isOtpSent
                  ? (_isChangingEmail ? Colors.orange : Colors.green)
                  : Colors.blue,
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
                  color: _isChangingEmail
                      ? Colors.orange.shade50
                      : Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: _isChangingEmail
                        ? Colors.orange.shade200
                        : Colors.green.shade200,
                  ),
                ),
                child: Text(
                  'ส่งรหัส OTP 6 หลักไปที่:\n$_targetEmail\nกรุณาตรวจสอบในกล่องจดหมายของคุณ',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: _isChangingEmail
                        ? Colors.orange.shade800
                        : Colors.green,
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
                decoration: InputDecoration(
                  labelText: 'รหัส OTP 6 หลัก',
                  border: const OutlineInputBorder(),
                  prefixIcon: const Icon(Icons.password),
                  focusedBorder: OutlineInputBorder(
                    borderSide: BorderSide(
                      color: _isChangingEmail ? Colors.orange : Colors.blue,
                      width: 2.0,
                    ),
                  ),
                ),
              ),

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
                    _isChangingEmail = false;
                    _otpCtrl.clear();
                    error = '';
                    _resendTimer?.cancel();
                  });
                },
                child: const Text(
                  'ยกเลิก',
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
                  : Icon(_isOtpSent ? Icons.check_circle : Icons.email),
              label: Text(
                _isOtpSent
                    ? (_isChangingEmail
                          ? 'ยืนยัน OTP เพื่อเลือกอีเมลใหม่'
                          : 'ยืนยัน OTP เพื่อเข้าสู่ระบบ')
                    : 'เลือกอีเมลในเครื่องเพื่อรับรหัส',
                style: const TextStyle(fontSize: 16),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: _isOtpSent
                    ? (_isChangingEmail ? Colors.orange : Colors.green)
                    : Colors.blue,
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 55),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),

            if (!_isOtpSent) ...[
              const SizedBox(height: 10),
              TextButton(
                onPressed: loading ? null : _requestEmailChange,
                child: const Text(
                  'ต้องการเปลี่ยนอีเมลที่ผูกไว้?',
                  style: TextStyle(
                    color: Colors.redAccent,
                    decoration: TextDecoration.underline,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _resendTimer?.cancel();
    _studentIdCtrl.dispose();
    _otpCtrl.dispose();
    super.dispose();
  }
}
