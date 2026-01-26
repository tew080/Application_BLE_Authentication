// นำเข้าเพื่อใช้ Timer และ StreamSubscription
import 'dart:async';
// นำเข้า Material UI
import 'package:flutter/material.dart';
// นำเข้า FirestoreService
import '../services/firestore_service.dart';
// นำเข้าหน้า Login
import 'login_page.dart';
// นำเข้า bleadvertise service
import '../services/bleadvertise_service.dart';
// นำเข้า LogdebugService
import '../services/logdebug_service.dart';

class AdvertisePage extends StatefulWidget {
  // รับรหัสนักศึกษาเข้ามา
  final String studentId;

  const AdvertisePage({super.key, required this.studentId});

  @override
  State<AdvertisePage> createState() {
    return _AdvertisePageState();
  }
}

class _AdvertisePageState extends State<AdvertisePage> {
  // สถานะว่ากำลังส่งสัญญาณอยู่หรือไม่
  bool advertising = false;
  // เก็บ Key ปัจจุบัน
  String currentKey = "";

  // ตัวแปรเช็คว่าเป็นครั้งแรกที่โหลดหรือไม่ (สำหรับ Auto Start)
  bool _isFirstLoad = true;
  // ตัวจัดการการดักฟังข้อมูล Firestore
  StreamSubscription? _userSubscription;

  // Timer สำหรับ Burst Mode
  Timer? _bleRefreshTimer;
  // เวลาเปิดสัญญาณ (5 วินาที)
  static const Duration _burstOn = Duration(seconds: 5);
  // เวลาพักสัญญาณ (4 วินาที)
  static const Duration _burstOff = Duration(seconds: 4);

  @override
  void initState() {
    super.initState();

    // ดักฟัง Callback จาก Native เมื่อเริ่มส่งสัญญาณสำเร็จ
    BleService.listenAdvertisingStarted(() {
      // ถ้าหน้าจอยังแสดงอยู่ ให้เปลี่ยนสถานะ advertising เป็น true
      if (mounted) {
        setState(() {
          advertising = true;
        });
      }
    });

    // เริ่มดักฟังข้อมูล User จาก Firebase
    _subscribeToUserStream();
  }

  // ข้อมูล User แบบ Real-time
  void _subscribeToUserStream() {
    _userSubscription = FirestoreService()
        .getUserStream(widget.studentId)
        .listen((snapshot) {
          // ถ้าไม่มีข้อมูล ให้จบการทำงาน
          if (!snapshot.exists) {
            return;
          }

          // แปลงข้อมูลเป็น Map
          final data = snapshot.data() as Map<String, dynamic>;

          // ดึง Key จากฟิลด์ 'key' หรือ 'ble_key'
          final String newKey =
              data['key']?.toString() ?? data['ble_key']?.toString() ?? "";

          // ถ้า Key ว่างเปล่า ให้จบการทำงาน
          if (newKey.isEmpty) {
            return;
          }

          // อัปเดต Key ในหน้าจอ
          if (mounted) {
            setState(() {
              currentKey = newKey;
            });
          }

          // ตรวจสอบ Logic Auto Start
          if (_isFirstLoad) {
            // ถ้าเป็นครั้งแรก ให้เริ่มส่งสัญญาณทันที (Auto Start)
            _isFirstLoad = false;
            startBurstAdvertising(newKey);
          } else if (advertising && newKey != currentKey) {
            // ถ้ากำลังทำงานอยู่ แต่ Key เปลี่ยน ให้เริ่มใหม่ด้วย Key ใหม่
            debugPrint("Key changed! Restarting BLE...");
            startBurstAdvertising(newKey);
          }
        });
  }

  Future<void> logout() async {
    _bleRefreshTimer?.cancel();
    // หยุดส่งสัญญาณ Bluetooth ทันที (สำคัญมาก)
    await BleService.stopAdvertising();
    log("Stop Advertising");

    // ยกเลิกการดักฟัง Database
    _userSubscription?.cancel();
    log("Cancel Database");

    // กลับไปหน้า Login และล้าง Stack เดิมทิ้ง (กด Back กลับมาไม่ได้)
    if (mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const LoginPage()),
      );
    }
  }

  // เริ่มส่งสัญญาณแบบ Burst Mode (เปิด-ปิด สลับกัน)
  Future<void> startBurstAdvertising(String key) async {
    log("**** StartBurstAdvertising ****");

    // ยกเลิก Timer ตัวเก่าก่อน (ป้องกันการทำงานซ้อน)
    _bleRefreshTimer?.cancel();
    log("StopRefreshTimer");

    // สั่งเริ่มส่งสัญญาณครั้งแรกทันที
    await BleService.startAdvertising(key);
    log("Auto StartAdvertising");

    // อัปเดตสถานะ UI
    if (mounted) {
      setState(() {
        advertising = true;
      });
    }
    log("State Advertising = $advertising");

    // ตั้ง Timer ให้ทำงานวนลูป
    _bleRefreshTimer = Timer.periodic(_burstOn + _burstOff, (timer) async {
      log("[DEBUG] Reset BLE =$timer");

      // สั่งเริ่มส่ง
      await BleService.startAdvertising(key);
      log("StartAdvertising");

      // รอเวลาพัก
      await Future.delayed(_burstOff);
      log("Delayed =$_burstOff");

      // สั่งหยุดส่ง
      await BleService.stopAdvertising();
      log("StopAdvertising");
    });
  }

  // ฟังก์ชันหยุดการทำงาน (Manual Stop)
  Future<void> stop() async {
    // ยกเลิก Timer
    _bleRefreshTimer?.cancel();
    log("StopRefreshTimer");

    // สั่งหยุด BLE
    await BleService.stopAdvertising();
    log("Stop Advertising");

    // อัปเดตสถานะ UI
    if (mounted) {
      setState(() {
        advertising = false;
      });
    }
    log("State Advertising = $advertising");
  }

  @override
  void dispose() {
    // คืนทรัพยากรเมื่อปิดหน้านี้
    // ป้องกัน Memory Leak แต่สำหรับการ Logout จะจัดการใน func logout() อีกที
    _userSubscription?.cancel();
    _bleRefreshTimer?.cancel();
    BleService.stopAdvertising();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Student ID: ${widget.studentId}'),
        actions: [
          // ปุ่ม Logout มุมขวาบน
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'ออกจากระบบ',
            onPressed: () {
              // แสดง Dialog ยืนยันการออก
              showDialog(
                context: context,
                builder: (context) {
                  return AlertDialog(
                    title: const Text('ยืนยันการออก'),
                    content: const Text(
                      'คุณต้องการหยุดส่งสัญญาณและออกจากระบบหรือไม่?',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () {
                          Navigator.pop(context); // ปิด Dialog
                        },
                        child: const Text('ยกเลิก'),
                      ),
                      TextButton(
                        onPressed: () {
                          Navigator.pop(context); // ปิด Dialog
                          logout(); // เรียกฟังก์ชัน Logout
                        },
                        child: const Text(
                          'ออกจากระบบ',
                          style: TextStyle(color: Colors.red),
                        ),
                      ),
                    ],
                  );
                },
              );
            },
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // เช็คสถานะการส่งสัญญาณเพื่อแสดง UI ที่เหมาะสม
            if (advertising) ...[
              // แสดง Animation วงกลม
              const SizedBox(height: 20),
              // แสดง Key
              Text(
                'กำลังส่งสัญญาณ...\nKey: $currentKey',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 18, color: Colors.green),
              ),
              const SizedBox(height: 10),
              const Text(
                "(ระบบซิงค์ข้อมูลอัตโนมัติ)",
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
            ] else ...[
              // แสดงไอคอนหยุด
              const Icon(
                Icons.bluetooth_disabled,
                size: 100,
                color: Colors.grey,
              ),
              const SizedBox(height: 20),
              const Text('ยังไม่เริ่มทำงาน'),
              if (currentKey.isNotEmpty) Text('Key ล่าสุด: $currentKey'),
            ],
            const SizedBox(height: 40),
            // ปุ่ม Start/Stop
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: advertising ? Colors.red : Colors.blue,
                padding: const EdgeInsets.symmetric(
                  horizontal: 30,
                  vertical: 15,
                ),
              ),
              onPressed: () {
                // สลับสถานะการทำงาน
                if (advertising) {
                  stop();
                } else {
                  startBurstAdvertising(currentKey);
                }
              },
              child: Text(
                advertising ? 'หยุดส่งสัญญาณ' : 'เริ่มส่งสัญญาณ',
                style: const TextStyle(fontSize: 16, color: Colors.white),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
