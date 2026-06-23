# config.py

class Config:
    TARGET_UUID = None
    COMPANY_ID = None
    RSSI_THRESHOLD = -66 # ระยะประมาณ 1 เมตร
    UNLOCK_DELAY = 3

    FB_KEY_PATH = "key/studentdata-37c33-firebase-adminsdk-fbsvc-aa56be95e5.json"
    COLLECTION_STUDENT = "student"
    COLLECTION_CONFIG = "connect"
    FIELD_NAME = "key"

    WEBHOOK_URL = "https://script.google.com/macros/s/AKfycby5j_3NJ2qOUZcS8NI0QnVRDwPnIsVYegPluqrKuOQb2A5lXXuwAyYKQvZmekHdJP8a5Q/exec"
    LOG_FILE = "system_log/log.txt"
    DASHBOARD_DIR_JS = "dashboard/dashboard_data.js"
    DASHBOARD_DIR_HTML = "dashboard/dashboard.html"
