import 'package:flutter/material.dart';

// นำเข้า FirestoreService เพื่อดึงข้อมูล User
import 'firestore_service.dart';

class AuthenticationService {
  // ฟังก์ชันสำหรับเข้าสู่ระบบ (Login)
  // รับค่า studentId และ password เข้ามา
  // คืนค่าเป็น Future<bool> (จริง/เท็จ)
  static Future<bool> login(String studentId, String password) async {
    // สร้าง Instance ของ FirestoreService เพื่อใช้งาน
    final FirestoreService firestoreService = FirestoreService();

    // เรียกดึงข้อมูล User จาก Firestore ตาม studentId
    final doc = await firestoreService.getUser(studentId);

    // ตรวจสอบว่ามีเอกสาร (Document) นี้อยู่ในฐานข้อมูลหรือไม่
    if (!doc.exists) {
      // ถ้าไม่มีข้อมูล ให้คืนค่า false (Login ไม่สำเร็จ)
      return false;
    }

    debugPrint("[DEBUG] LOGIN studentId='$studentId'");
    debugPrint("[DEBUG] PASSWORD from input='$password'");

    debugPrint("[DEBUG] DB PASSWORD = ${doc['password']}");

    // ตรวจสอบรหัสผ่าน:
    // แปลงรหัสผ่านจาก DB เป็น String และเปรียบเทียบกับ password ที่กรอกมา
    if (doc['password'].toString() == password) {
      // ถ้าตรงกัน คืนค่า true (Login สำเร็จ)
      return true;
    } else {
      // ถ้าไม่ตรงกัน คืนค่า false
      return false;
    }
  }
}
