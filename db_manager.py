# db_manager.py
import csv
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

import firebase_admin
import requests
from firebase_admin import credentials as fb_credentials
from firebase_admin import firestore

import shared_state
from config import Config
from dashboard import update_dashboard_data_file
from logger import log


def init_firebase():
    try:
        if not firebase_admin._apps:
            cred = fb_credentials.Certificate(Config.FB_KEY_PATH)
            firebase_admin.initialize_app(cred)
        shared_state.db = firestore.client()
        fetch_ble_config()
        shared_state.db.collection(Config.COLLECTION_STUDENT).on_snapshot(
            on_snapshot_update
        )
        log("- Firebase Connected & Syncing...")
    except Exception as e:
        log(f"❌ Firebase Init Error: {e}")
        exit(1)


def fetch_ble_config():
    try:
        config_ref = (
            shared_state.db.collection(Config.COLLECTION_CONFIG)
            .document("advertisingPackage")
            .get()
        )
        if config_ref.exists:
            data = config_ref.to_dict()
            Config.TARGET_UUID = str(data.get("uuid", "")).lower()
            comp_id = data.get("companyID")
            if isinstance(comp_id, str):
                Config.COMPANY_ID = int(comp_id, 16)
            else:
                Config.COMPANY_ID = int(comp_id)
            log(
                f"- Config Loaded -> UUID: {Config.TARGET_UUID}, CompanyID: {hex(Config.COMPANY_ID)}"
            )
    except Exception as e:
        log(f"❌ Fetch Config Error: {e}")


def on_snapshot_update(col_snapshot, changes, read_time):
    try:
        new_keys = {}
        for doc in col_snapshot:
            data = doc.to_dict()
            key = str(data.get(Config.FIELD_NAME, "")).strip()
            if key:
                new_keys[key] = {
                    "doc_id": doc.id,
                    "first_name": data.get("first_name", "ไม่ระบุ"),
                    "last_name": data.get("last_name", ""),
                    "last_status": data.get("last_status", "Clock-OUT"),
                    "last_update_date": data.get("last_update_date", ""),
                }
        shared_state.valid_keys = new_keys
        log(
            f"- Database Updated: Loaded {len(shared_state.valid_keys)} student keys into memory."
        )
    except Exception as e:
        log(f"❌ Firebase Update Error: {e}")


def sync_record_attendance(doc_id):
    now = datetime.now()
    today_date = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    student_ref = shared_state.db.collection(Config.COLLECTION_STUDENT).document(doc_id)
    student_doc = student_ref.get()

    prefix = ""
    first_name = "ไม่ระบุ"
    last_name = ""
    faculty = "ไม่ระบุ"
    branch = "ไม่ระบุ"
    last_status = "Clock-OUT"
    last_update_date = ""

    if student_doc.exists:
        student_data = student_doc.to_dict()
        prefix = student_data.get("prefix", "")
        first_name = student_data.get("first_name", "ไม่ระบุ")
        last_name = student_data.get("last_name", "")
        faculty = student_data.get("faculty", "ไม่ระบุ")
        branch = student_data.get("branch", "ไม่ระบุ")
        last_status = student_data.get("last_status", "Clock-OUT")
        last_update_date = student_data.get("last_update_date", "")

    is_first_visit_today = False

    if last_update_date != today_date:
        new_status = "Clock-IN"
        is_first_visit_today = True
    else:
        if last_status == "Clock-OUT":
            new_status = "Clock-IN"
        else:
            new_status = "Clock-OUT"

    student_ref.set(
        {"last_status": new_status, "last_update_date": today_date}, merge=True
    )

    log_doc_id = f"{today_date}_{time_str.replace(':', '')}_{doc_id}"
    # หมายเหตุ: Firestore ไม่มี schema ตายตัว collection "attendance_logs" จะถูก
    # สร้างขึ้นเองโดยอัตโนมัติทันทีที่มีการ .set() เอกสารแรกลงไป ไม่ต้องสร้างล่วงหน้า
    log_ref = shared_state.db.collection(Config.COLLECTION_ATTENDANCE).document(log_doc_id)

    log_ref.set(
        {
            "student_id": doc_id,
            "prefix": prefix,
            "first_name": first_name,
            "last_name": last_name,
            "faculty": faculty,
            "branch": branch,
            "date": today_date,
            "time": time_str,
            "action": new_status,
            "is_first_visit": is_first_visit_today,
        }
    )

    log(f"- Firebase Updated: [{new_status}] User: {doc_id}")

    update_dashboard_data_file()


def import_csv_to_firebase():
    if shared_state.db is None:
        messagebox.showerror("Error", "Firebase is not connected yet. Please wait.")
        return

    file_path = filedialog.askopenfilename(
        title="นำเข้าไฟล์ CSV",
        filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*")),
    )

    if not file_path:
        return

    try:
        log("- Loading existing records from Firebase...")
        existing_docs_stream = shared_state.db.collection(
            Config.COLLECTION_STUDENT
        ).stream()

        existing_data = {}
        for doc in existing_docs_stream:
            doc_info = doc.to_dict()
            if doc_info is not None:
                existing_data[doc.id.strip()] = doc_info

        with open(file_path, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            headers = [str(h).strip() for h in reader.fieldnames if h]
            if "student_id" not in headers:
                messagebox.showerror(
                    "Format Error", "CSV must contain a 'student_id' column."
                )
                return

            batch = shared_state.db.batch()
            count_added, count_updated, count_skipped, operations_in_batch = 0, 0, 0, 0

            for row in reader:
                clean_row = {}
                for k, v in row.items():
                    if k:
                        clean_key = str(k).strip()
                        clean_val = str(v).strip() if v else ""
                        if clean_val.startswith('="') and clean_val.endswith('"'):
                            clean_val = clean_val[2:-1]
                        elif (
                            clean_val == '=""' or clean_val == '""' or clean_val == "="
                        ):
                            clean_val = ""
                        clean_row[clean_key] = clean_val

                doc_id = clean_row.get("student_id", "")
                if not doc_id:
                    continue

                student_data = {}
                for key, val_str in clean_row.items():
                    if key == "student_id":
                        continue
                    if key in ["current_otp", "otp_expiry"]:
                        student_data[key] = int(val_str) if val_str.isdigit() else 0
                    elif key == "loginStatus":
                        student_data[key] = True if val_str.lower() == "true" else False
                    else:
                        student_data[key] = val_str

                if not student_data:
                    count_skipped += 1
                    continue

                doc_ref = shared_state.db.collection(
                    Config.COLLECTION_STUDENT
                ).document(doc_id)

                if doc_id in existing_data:
                    db_record = existing_data[doc_id]
                    fields_to_update = {}

                    for k, new_v in student_data.items():
                        db_val = db_record.get(k)
                        if db_val is None or str(db_val).strip() in [
                            "",
                            "ไม่ระบุ",
                            "-",
                            "None",
                            "null",
                        ]:
                            if str(new_v).strip() != "":
                                fields_to_update[k] = new_v

                    if fields_to_update:
                        batch.set(doc_ref, fields_to_update, merge=True)
                        existing_data[doc_id].update(fields_to_update)
                        count_updated += 1
                        operations_in_batch += 1
                    else:
                        count_skipped += 1
                else:
                    batch.set(doc_ref, student_data)
                    existing_data[doc_id] = student_data
                    count_added += 1
                    operations_in_batch += 1

                if operations_in_batch >= 400:
                    batch.commit()
                    batch = shared_state.db.batch()
                    operations_in_batch = 0

            if operations_in_batch > 0:
                batch.commit()

            messagebox.showinfo(
                "Import Summary",
                f"- นำเข้าข้อมูลสำเร็จ\nเพิ่มใหม่: {count_added} คน\nอัปเดต: {count_updated} คน",
            )

    except Exception as e:
        log(f"❌ CSV Import Error: {e}")
        messagebox.showerror("Import Error", f"- นำเข้าข้อมูลจาก CSV ไม่สำเร็จ:\n{str(e)}")

def import_attendance_csv_to_firebase():
    """นำเข้าข้อมูล Attendance Logs จากไฟล์ CSV เข้า collection 'attendance_logs'
    (ประยุกต์จาก import_csv_to_firebase ที่ใช้กับ collection student)"""

    if shared_state.db is None:
        messagebox.showerror("Error", "Firebase is not connected yet. Please wait.")
        return

    file_path = filedialog.askopenfilename(
        title="นำเข้าไฟล์ CSV (Attendance Logs)",
        filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*")),
    )

    if not file_path:
        return

    try:
        log("- Loading existing attendance log IDs from Firebase...")
        # attendance_logs อาจมีจำนวนเอกสารมาก จึงดึงมาแค่ field เดียว (ไม่ใช่ทั้ง document)
        # เพื่อเช็คว่า doc_id ไหนมีอยู่แล้ว โดยไม่ต้องโหลดข้อมูลทั้งหมดมาเก็บใน memory
        # หมายเหตุ: attendance_logs เป็นคนละ collection กับ student แยกขาดจากกันโดยสิ้นเชิง
        # ไม่มีการรวม/แก้ทับข้อมูลข้ามกัน และไม่ต้องสร้าง collection ล่วงหน้า เพราะ Firestore
        # จะสร้าง collection นี้ให้อัตโนมัติทันทีที่มีการเขียนเอกสารแรกลงไป (ด้านล่าง)
        # ถ้ายังไม่เคยมีเอกสารเลย .stream() จะคืนค่าว่างเปล่า ไม่ error
        existing_ids = set()
        existing_docs_stream = (
            shared_state.db.collection(Config.COLLECTION_ATTENDANCE)
            .select(["student_id"])
            .stream()
        )
        for doc in existing_docs_stream:
            existing_ids.add(doc.id)

        with open(file_path, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            headers = [str(h).strip() for h in reader.fieldnames if h]
            required_cols = {"student_id", "date", "time"}
            if not required_cols.issubset(set(headers)):
                messagebox.showerror(
                    "Format Error",
                    "CSV must contain 'student_id', 'date' and 'time' columns.",
                )
                return

            batch = shared_state.db.batch()
            count_added, count_skipped, operations_in_batch = 0, 0, 0

            for row in reader:
                clean_row = {}
                for k, v in row.items():
                    if k:
                        clean_key = str(k).strip()
                        clean_val = str(v).strip() if v else ""
                        if clean_val.startswith('="') and clean_val.endswith('"'):
                            clean_val = clean_val[2:-1]
                        elif (
                            clean_val == '=""' or clean_val == '""' or clean_val == "="
                        ):
                            clean_val = ""
                        clean_row[clean_key] = clean_val

                student_id = clean_row.get("student_id", "")
                date_str = clean_row.get("date", "")
                time_str = clean_row.get("time", "")

                # ข้ามแถวที่ข้อมูลจำเป็นไม่ครบ
                if not student_id or not date_str or not time_str:
                    count_skipped += 1
                    continue

                # ใช้ doc_id จาก CSV ถ้ามี ไม่งั้นสร้างในรูปแบบเดียวกับ sync_record_attendance
                # เช่น 2026-03-27_121453_6604341001104
                doc_id = clean_row.get("doc_id", "").strip()
                if not doc_id:
                    doc_id = f"{date_str}_{time_str.replace(':', '')}_{student_id}"

                # attendance log เป็นข้อมูล event ที่ไม่ควรถูกแก้ทับ -> ถ้ามีอยู่แล้วให้ข้าม
                if doc_id in existing_ids:
                    count_skipped += 1
                    continue

                log_data = {}
                for key, val_str in clean_row.items():
                    if key == "doc_id":
                        continue
                    if key == "is_first_visit":
                        log_data[key] = val_str.strip().lower() == "true"
                    else:
                        log_data[key] = val_str

                # .document(doc_id).set(...) จะสร้างทั้ง collection (ถ้ายังไม่มี) และเอกสารนี้
                # ให้อัตโนมัติในคำสั่งเดียว ไม่ต้องเช็คหรือสร้าง collection แยกต่างหาก
                doc_ref = shared_state.db.collection(Config.COLLECTION_ATTENDANCE).document(doc_id)
                batch.set(doc_ref, log_data)
                existing_ids.add(doc_id)
                count_added += 1
                operations_in_batch += 1

                if operations_in_batch >= 400:
                    batch.commit()
                    batch = shared_state.db.batch()
                    operations_in_batch = 0

            if operations_in_batch > 0:
                batch.commit()

            messagebox.showinfo(
                "Import Summary",
                f"- นำเข้า Attendance Logs สำเร็จ\nเพิ่มใหม่: {count_added} รายการ\nข้าม (ซ้ำ/ข้อมูลไม่ครบ): {count_skipped} รายการ",
            )

    except Exception as e:
        log(f"❌ Attendance Log CSV Import Error: {e}")
        messagebox.showerror(
            "Import Error", f"- นำเข้าข้อมูล Attendance Logs จาก CSV ไม่สำเร็จ:\n{str(e)}"
        )


def get_student_by_id(student_id):
    """ฟังก์ชันสำหรับดึงข้อมูลนักศึกษาจาก Firestore ด้วยรหัส นศ."""
    if shared_state.db is None:
        return None
    try:
        # ใช้รหัส นศ เป็น Document ID ในการค้นหา
        doc_ref = shared_state.db.collection(Config.COLLECTION_STUDENT).document(student_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        log(f"❌ Error fetching student: {e}")
        return None

def update_student_data(student_id, update_data):
    """ฟังก์ชันสำหรับบันทึกข้อมูลที่แก้ไขแล้วทับลงไปใน Firestore"""
    if shared_state.db is None:
        return False
    try:
        doc_ref = shared_state.db.collection(Config.COLLECTION_STUDENT).document(student_id)
        doc_ref.set(update_data, merge=True)
        log(f"- Successfully updated student ID: {student_id}")
        return True
    except Exception as e:
        log(f"❌ Error updating student: {e}")
        return False