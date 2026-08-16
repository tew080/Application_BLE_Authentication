import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:internet_connection_checker_plus/internet_connection_checker_plus.dart';

class NetworkService {
  //สำหรับฟังการเปลี่ยนแปลงสถานะแบบ Real-time
  static Stream<bool> get onConnectivityChanged {
    return InternetConnection().onStatusChange.map(
      (status) => status == InternetStatus.connected,
    );
  }
}