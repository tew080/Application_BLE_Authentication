// นำเข้าเพื่อใช้ MethodChannel
import 'package:flutter/services.dart';
// นำเข้าตัวช่วยแปลง String เป็น Hex
import '../utils/converter_utils.dart';
// นำเข้า LogdebugService
import '../services/logdebug_service.dart';

// คลาสสำหรับจัดการ Bluetooth Low Energy (BLE) ผ่าน Native Code
class BleService {
  // สร้างช่องทางสื่อสาร (Channel) ชื่อ 'ble_advertiser' ให้ตรงกับฝั่ง Android (Native Code)
  static const MethodChannel channel = MethodChannel('ble_advertiser');

  // รับค่า bleKey ที่ต้องการส่ง
  static Future<void> startAdvertising(String bleKey) async {
    // ตั้งค่า Advertising Package
    String uuID = '0000feaa-0000-1000-8000-00805f9b34fb';
    int companyID = 0xFFFF;
    bool devicename = false;
    bool connectable = false;
    bool txpowerlevel = false;

    // แสดง Log ค่า Key ก่อนทำการเข้ารหัส
    log("Key BLE Before Encode = $bleKey");

    // ตรวจสอบว่า Key เป็นค่าว่างหรือไม่
    if (bleKey.isEmpty) {
      // ถ้าว่าง ให้จบการทำงานทันที
      return;
    }

    // แปลง String Key ให้เป็น Hex String โดยใช้ Converter
    final String hexData = stringToAsciiHex(bleKey);

    // แสดง Log ค่า Key หลังเข้ารหัสแล้ว
    log("Key BLE After Encode = $hexData");

    // ส่งคำสั่งไปยัง Native Android ผ่าน MethodChannel
    await channel.invokeMethod('startAdvertising', {
      // UUID ของ Service ที่ต้องการส่ง (ต้องตรงกับตัวรับ)
      'uuid': uuID,
      // Company ID (ใช้ 0xFFFF สำหรับการทดสอบ)
      'companyId': companyID,
      // ข้อมูล Data ที่แปลงเป็น Hex แล้ว
      'data': hexData,
      // ส่งชื่ออุปกรณ์
      'devicename': devicename,
      // กำหนดว่าไม่ต้องให้ใครมาเชื่อมต่อ (Connectable = false)
      'connectable': connectable,
      // ส่งค่าความแรงสัญญาน tx power
      'txpowerlevel': txpowerlevel,
    });
  }

  // ฟังก์ชันสำหรับรอฟัง Callback จาก Native ว่าเริ่มส่งสัญญาณสำเร็จแล้ว
  static void listenAdvertisingStarted(VoidCallback onStarted) {
    // ตั้งค่า Handler เพื่อรอรับการเรียกกลับจาก Native
    channel.setMethodCallHandler((call) async {
      // ตรวจสอบชื่อ Method ที่ Native ส่งมา
      if (call.method == 'onAdvertisingStarted') {
        // ถ้าชื่อตรงกัน ให้เรียกฟังก์ชัน onStarted() ที่ UI ส่งมา
        onStarted();
      }
    });
  }

  static Future<void> stopAdvertising() async {
    // ส่งคำสั่ง stop ไปยัง Native Android
    await channel.invokeMethod('stopAdvertising');
  }
}
