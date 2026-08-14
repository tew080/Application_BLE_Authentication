import os
import json
import webbrowser
from datetime import datetime, timedelta
from tkinter import messagebox
from google.cloud.firestore_v1.base_query import FieldFilter

from config import Config
import shared_state
from logger import log

def update_dashboard_data_file():
    """ ดึงข้อมูลจาก Firebase มาเซฟเป็นไฟล์ JS เพื่อให้หน้าเว็บดึงไปโชว์แบบ Real-time """
    if shared_state.db is None:
        return

    with shared_state.dashboard_data_lock:
        try:
            today_date = datetime.now().strftime("%Y-%m-%d")
            
            # --- 1. จำกัดช่วงเวลาการดึงข้อมูลเพื่อลดภาระเครื่อง (30 วันย้อนหลัง) ---
            past_date_limit = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            # 2. ดึงข้อมูลรายชื่อนักศึกษาล่วงหน้าเพื่อใช้ทำ Mapping ชื่อ-นามสกุล
            student_info_map = {}
            try:
                students_ref = shared_state.db.collection(Config.COLLECTION_STUDENT).stream()
                for doc in students_ref:
                    sd = doc.to_dict()
                    sid = sd.get("student_id", doc.id)
                    student_info_map[sid] = {
                        "first_name": sd.get("first_name", "ไม่ระบุ"),
                        "last_name": sd.get("last_name", "")
                    }
            except Exception as ex:
                log(f"⚠️ ไม่สามารถดึงรายชื่อนักศึกษาล่วงหน้าได้ : {ex}")

            # 3. ดึงข้อมูล logs เฉพาะช่วงเวลาที่กำหนด
            logs_ref = shared_state.db.collection("attendance_logs")\
                .where(filter=FieldFilter("date", ">=", past_date_limit))\
                .stream()
                
            raw_events = []
            all_logs = []
            latest_clock_in = {}

            for doc in logs_ref:
                d = doc.to_dict()
                action = d.get("action", "")
                s_id = d.get("student_id", "")
                d_date = d.get("date", "")
                d_time = d.get("time", "00:00:00")
                faculty = d.get("faculty", "ไม่ระบุ") if d.get("faculty") else "ไม่ระบุ"
                branch = d.get("branch", "ไม่ระบุ") if d.get("branch") else "ไม่ระบุ"

                if not s_id:
                    continue

                # ดึงชื่อ-นามสกุลจาก Log หรือใช้จาก Student Map
                first_name = d.get("first_name") or student_info_map.get(s_id, {}).get("first_name", "ไม่ระบุ")
                last_name = d.get("last_name") or student_info_map.get(s_id, {}).get("last_name", "")

                raw_events.append({
                    "student_id": s_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "action": action,
                    "date": d_date,
                    "time": d_time,
                    "faculty": faculty,
                    "branch": branch
                })

                if action == "Clock-IN":
                    all_logs.append({
                        "student_id": s_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "date": d_date,
                        "time": d_time,
                        "faculty": faculty,
                        "branch": branch
                    })
                    if d_date == today_date:
                        if s_id not in latest_clock_in or d_time > latest_clock_in.get(s_id, ""):
                            latest_clock_in[s_id] = d_time

            events_by_user_date = {}
            for ev in raw_events:
                key = (ev["student_id"], ev["date"])
                if key not in events_by_user_date:
                    events_by_user_date[key] = []
                events_by_user_date[key].append(ev)

            session_data = []
            for key, events in events_by_user_date.items():
                student_id, d_date = key
                events.sort(key=lambda x: x["time"])

                total_hours_today = 0.0
                in_time = None

                faculty = next((e["faculty"] for e in reversed(events) if e["faculty"] != "ไม่ระบุ"), "ไม่ระบุ")
                branch = next((e["branch"] for e in reversed(events) if e["branch"] != "ไม่ระบุ"), "ไม่ระบุ")
                first_name = next((e["first_name"] for e in reversed(events) if e.get("first_name")), "ไม่ระบุ")
                last_name = next((e["last_name"] for e in reversed(events) if e.get("last_name")), "")

                for ev in events:
                    if ev["action"] == "Clock-IN":
                        if in_time is None:
                            in_time = ev["time"]
                    elif ev["action"] == "Clock-OUT" and in_time is not None:
                        try:
                            t1 = datetime.strptime(in_time, "%H:%M:%S")
                            t2 = datetime.strptime(ev["time"], "%H:%M:%S")
                            duration_hours = (t2 - t1).total_seconds() / 3600.0

                            if duration_hours > 0:
                                total_hours_today += duration_hours
                        except Exception:
                            pass
                        in_time = None

                if total_hours_today > 0:
                    session_data.append({
                        "student_id": student_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "date": d_date,
                        "faculty": faculty,
                        "branch": branch,
                        "total_hours": total_hours_today
                    })

            inside_query = shared_state.db.collection(Config.COLLECTION_STUDENT)\
                .where(filter=FieldFilter("last_status", "==", "Clock-IN"))\
                .stream()

            inside_list = []
            for doc in inside_query:
                d = doc.to_dict()
                if d.get("last_update_date") == today_date:
                    student_id = d.get("student_id", doc.id)
                    time_in = d.get("last_update_time", d.get("time", ""))
                    if not time_in or time_in == "-":
                        time_in = latest_clock_in.get(student_id, "-")

                    inside_list.append({
                        "first_name": d.get("first_name", "ไม่ระบุ"),
                        "last_name": d.get("last_name", ""),
                        "faculty": d.get("faculty", "ไม่ระบุ") if d.get("faculty") else "ไม่ระบุ",
                        "branch": d.get("branch", "ไม่ระบุ") if d.get("branch") else "ไม่ระบุ",
                        "time_in": time_in
                    })

            js_content = f"window.rawData = {json.dumps(all_logs)};\nwindow.insideData = {json.dumps(inside_list)};\nwindow.sessionData = {json.dumps(session_data)};"
            file_path = os.path.join(os.getcwd(), Config.DASHBOARD_DIR_JS)

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as file:
                file.write(js_content)
        except Exception as e:
            log(f"❌ ข้อผิดพลาดในการอัปเดตข้อมูลแดชบอร์ด : {e}")

def show_dashboard_graph():
    if shared_state.db is None:
        messagebox.showerror("ข้อผิดพลาด", "รอสักครู่ ระบบกำลังเชื่อมต่อฐานข้อมูล")
        return

    try:
        log("- กำลังเตรียมแดชบอร์ดระดับพรีเมียม...")
        update_dashboard_data_file()

        html_content = """
        <!DOCTYPE html>
        <html lang="th">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>แดชบอร์ดสถิติการเข้าใช้งาน</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/flatpickr/4.6.13/flatpickr.min.css">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/flatpickr/4.6.13/flatpickr.min.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                body { font-family: 'Sarabun', sans-serif; background-color: #f8fafc; scroll-behavior: smooth; }
                .glass-card { 
                    background: white; 
                    border-radius: 16px; 
                    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.04); 
                    border: 1px solid #f1f5f9; 
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
                }
                .form-select, .form-input {
                    width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px;
                    font-family: 'Sarabun', sans-serif; font-size: 14px; outline: none; transition: all 0.2s; background: #fff;
                }
                .form-select:focus, .form-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1); }
                .form-input:disabled { background-color: #f1f5f9; color: #94a3b8; cursor: not-allowed; }
                .table-container::-webkit-scrollbar { width: 6px; height: 6px; }
                .table-container::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 4px; }
                .fade-in { animation: fadeIn 0.4s ease-in-out; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

                @keyframes targetHighlight {
                    0% { border-color: #f1f5f9; box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.04); }
                    25% { border-color: #3b82f6; box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.4), 0 10px 25px -5px rgba(59, 130, 246, 0.25); }
                    75% { border-color: #3b82f6; box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.4), 0 10px 25px -5px rgba(59, 130, 246, 0.25); }
                    100% { border-color: #f1f5f9; box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.04); }
                }
                .active-target { animation: targetHighlight 2s ease-in-out; position: relative; z-index: 30 !important; }
            </style>
        </head>
        <body class="p-4 md:p-8 text-slate-800">
            <div class="max-w-screen-2xl mx-auto fade-in">

                <!-- Header Section -->
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                    <div>
                        <h1 class="text-3xl font-bold text-slate-900 tracking-tight">แดชบอร์ดสถิติการเข้าใช้งาน</h1>
                        <p class="text-sm text-slate-500 mt-2 flex items-center gap-2 font-medium">
                            <span class="relative flex h-3 w-3">
                              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                              <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                            </span>
                            อัปเดตข้อมูลอัตโนมัติตามเวลาจริง
                        </p>
                    </div>
                    <div class="flex gap-3">
                        <div class="bg-white px-5 py-2 rounded-lg border border-slate-200 shadow-sm flex flex-col justify-center">
                            <p class="text-[10px] text-slate-400 font-bold uppercase tracking-wider">เวลาปัจจุบัน</p>
                            <p id="currentTime" class="text-lg font-bold text-slate-700 leading-none mt-1"></p>
                        </div>
                    </div>
                </div>

                <!-- Main Layout -->
                <div class="flex flex-col lg:flex-row gap-6">
                    
                    <!-- Left Sidebar -->
                    <div class="w-full lg:w-72 shrink-0 flex flex-col gap-6">
                        <div class="glass-card p-6 sticky top-6">
                            <div class="flex items-center gap-2 mb-6">
                                <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path></svg>
                                <h2 class="text-base font-semibold text-slate-700">ตัวกรองข้อมูล</h2>
                            </div>
                            
                            <div class="flex flex-col gap-4">
                                <div>
                                    <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">คณะ</label>
                                    <select id="facFilter" class="form-select"></select>
                                </div>
                                <div>
                                    <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">สาขา</label>
                                    <select id="branchFilter" class="form-select"></select>
                                </div>
                                <div>
                                    <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">ช่วงเวลาด่วน</label>
                                    <select id="presetDateFilter" class="form-select">
                                        <option value="all" selected>ข้อมูลทั้งหมด</option>
                                        <option value="7">7 วันย้อนหลัง</option>
                                        <option value="15">15 วันย้อนหลัง</option>
                                        <option value="30">30 วันย้อนหลัง</option>
                                        <option value="custom">กำหนดเอง</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">วันที่เริ่ม</label>
                                    <input type="text" id="startDate" class="form-input">
                                </div>
                                <div>
                                    <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">วันที่สิ้นสุด</label>
                                    <input type="text" id="endDate" class="form-input">
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Right Main Content -->
                    <div class="flex-1 flex flex-col gap-6 w-full overflow-hidden p-1">
                        
                        <!-- KPI Cards -->
                        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                            
                            <!-- Card 1 -->
                            <div class="glass-card p-6 border-l-4 border-l-emerald-500 relative cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all duration-300" 
                                 onclick="scrollToAndHighlight('liveTableSection')">
                                <h3 class="text-slate-500 font-semibold text-sm mb-1">ผู้ใช้งานในพื้นที่ขณะนี้</h3>
                                <div class="text-4xl font-bold text-slate-800 mt-2"><span id="kpi-inside">0</span> <span class="text-base font-normal text-slate-400">คน</span></div>
                            </div>

                            <!-- Card 2 -->
                            <div class="glass-card p-6 border-l-4 border-l-blue-500 cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all duration-300"
                                 onclick="scrollToAndHighlight('compareChartSection')">
                                <h3 class="text-slate-500 font-semibold text-sm mb-1">จำนวนผู้เข้าใช้บริการรวม</h3>
                                <div class="text-4xl font-bold text-slate-800 mt-2"><span id="kpi-unique-users">0</span> <span class="text-base font-normal text-slate-400">คน</span></div>
                            </div>

                            <!-- Card 3 -->
                            <div class="glass-card p-6 border-l-4 border-l-indigo-500 cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all duration-300"
                                 onclick="scrollToAndHighlight('trendChartSection')">
                                <h3 class="text-slate-500 font-semibold text-sm mb-1">ความถี่การเข้าใช้รวม</h3>
                                <div class="text-4xl font-bold text-slate-800 mt-2"><span id="kpi-total">0</span> <span class="text-base font-normal text-slate-400">ครั้ง</span></div>
                            </div>

                            <!-- Card 4 -->
                            <div class="glass-card p-6 border-l-4 border-l-amber-500 flex flex-col justify-center h-full cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all duration-300"
                                 onclick="scrollToAndHighlight('topRankingsSection')">
                                <div>
                                    <h3 class="text-slate-500 font-semibold text-sm mb-1" id="kpi-top-group-title">กลุ่มที่ใช้งานมากที่สุด</h3>
                                    <div class="text-lg font-bold text-slate-800 mt-1 break-words leading-tight" id="kpi-top-group">-</div>
                                </div>
                                <hr class="my-3 border-slate-100">
                                <div>
                                    <h3 class="text-slate-500 font-semibold text-sm mb-1">ช่วงเวลาหนาแน่นที่สุด</h3>
                                    <div class="text-lg font-bold text-slate-800 mt-1" id="kpi-peak-hour">-</div>
                                </div>
                            </div>
                        </div>

                        <!-- Top 5 Ranking Section -->
                        <div class="glass-card p-6 w-full" id="topRankingsSection">
                            <div class="flex justify-between items-center mb-4">
                                <div>
                                    <h2 class="text-base font-bold text-slate-700 flex items-center gap-2" id="top5Title">
                                        <span>🏆</span> 5 อันดับนักศึกษาเข้าใช้งานสูงสุด (ระดับมหาวิทยาลัย)
                                    </h2>
                                    <p class="text-xs text-slate-500 mt-1" id="top5Subtitle">จัดอันดับจากความถี่การเข้าใช้งานทั้งหมดตามช่วงเวลาที่เลือก</p>
                                </div>
                            </div>
                            <div class="table-container max-h-96 overflow-auto border border-slate-100 rounded-xl">
                                <table class="w-full text-left border-collapse min-w-max">
                                    <thead>
                                        <tr class="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                                            <th class="py-3 px-4 font-bold sticky top-0 bg-slate-50 shadow-sm w-16">อันดับ</th>
                                            <th class="py-3 px-4 font-bold sticky top-0 bg-slate-50 shadow-sm">ชื่อ - นามสกุล</th>
                                            <th class="py-3 px-4 font-bold sticky top-0 bg-slate-50 shadow-sm" id="top5GroupHeader">คณะ</th>
                                            <th class="py-3 px-4 font-bold sticky top-0 bg-slate-50 shadow-sm text-right">เข้าใช้งาน</th>
                                        </tr>
                                    </thead>
                                    <tbody id="top5Body" class="text-sm text-slate-600">
                                        <!-- JS Injected -->
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- Charts Section 1 -->
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="glass-card p-6 w-full" id="trendChartSection">
                                <h2 class="text-base font-bold text-slate-700 mb-2">สถิติการเข้าใช้งานรายวัน</h2>
                                <p class="text-xs text-slate-500 mb-4">เปรียบเทียบความถี่การเข้าใช้ (ครั้ง) และจำนวนผู้ใช้งานจริง (คน)</p>
                                <div class="relative h-72 w-full">
                                    <canvas id="trendChart"></canvas>
                                </div>
                            </div>
                            
                            <div class="glass-card p-6 w-full" id="avgTimeChartSection">
                                <h2 class="text-base font-bold text-slate-700 mb-2" id="avgTimeTitle">เวลาเฉลี่ยในการเข้าใช้พื้นที่</h2>
                                <p class="text-xs text-slate-500 mb-4" id="avgTimeSubtitle">คำนวณจากระยะเวลาที่ใช้งานในแต่ละวัน</p>
                                <div class="relative h-72 w-full">
                                    <canvas id="avgTimeChart"></canvas>
                                    <div id="avgTimeEmptyState" class="hidden absolute inset-0 flex flex-col items-center justify-center text-center px-6">
                                        <p class="text-sm font-semibold text-slate-500 mb-1">ยังไม่มีข้อมูลเวลาเฉลี่ยในช่วงที่เลือก</p>
                                        <p class="text-xs text-slate-400 leading-relaxed max-w-xs">
                                            สาเหตุหลักมักมาจากการที่นักศึกษามีแต่ประวัติ Clock-IN แต่ไม่มีการแตะบัตร Clock-OUT
                                            ทำให้ระบบไม่สามารถนำมาลบกันเพื่อหาระยะเวลาการใช้งานได้
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Charts Section 2 (Combined Chart) -->
                        <div class="grid grid-cols-1 gap-6">
                            <div class="glass-card p-6 w-full" id="compareChartSection">
                                <h2 class="text-base font-bold text-slate-700 mb-2" id="compareTitle">เปรียบเทียบความถี่การเข้าใช้งาน (ครั้ง) และ จำนวนผู้ใช้งาน (คน)</h2>
                                <p class="text-xs text-slate-500 mb-4">แสดงผลเปรียบเทียบเพื่อดูความหนาแน่นของผู้ใช้งาน</p>
                                <div class="relative h-80 w-full">
                                    <canvas id="compareChart"></canvas>
                                </div>
                            </div>
                        </div>

                        <!-- Live User Table -->
                        <div class="glass-card overflow-hidden w-full" id="liveTableSection">
                            <div class="p-6 border-b border-slate-100 flex justify-between items-center bg-white">
                                <h2 class="text-base font-bold text-slate-700 flex items-center gap-2">
                                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                                    รายชื่อผู้ที่กำลังใช้งานอยู่ในปัจจุบัน
                                </h2>
                            </div>
                            <div class="table-container max-h-96 overflow-auto bg-slate-50/50">
                                <table class="w-full text-left border-collapse min-w-max">
                                    <thead>
                                        <tr class="bg-white text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                                            <th class="py-4 px-6 font-bold sticky top-0 bg-white shadow-sm whitespace-nowrap">ลำดับ</th>
                                            <th class="py-4 px-6 font-bold sticky top-0 bg-white shadow-sm whitespace-nowrap">เวลาเข้าล่าสุด</th>
                                            <th class="py-4 px-6 font-bold sticky top-0 bg-white shadow-sm whitespace-nowrap">ชื่อ - นามสกุล</th>
                                            <th class="py-4 px-6 font-bold sticky top-0 bg-white shadow-sm whitespace-nowrap">คณะ</th>
                                            <th class="py-4 px-6 font-bold sticky top-0 bg-white shadow-sm whitespace-nowrap">สาขา</th>
                                        </tr>
                                    </thead>
                                    <tbody id="liveTableBody" class="text-sm text-slate-600">
                                        <!-- Data injected via JS -->
                                    </tbody>
                                </table>
                            </div>
                        </div>

                    </div>
                </div>
            </div>

            <script>
                // --- Helper Function: Smooth Scroll & Glow Highlight ---
                function scrollToAndHighlight(targetId) {
                    const targetEl = document.getElementById(targetId);
                    if (!targetEl) return;

                    targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

                    targetEl.classList.remove('active-target');
                    void targetEl.offsetWidth; // Trigger Reflow
                    targetEl.classList.add('active-target');

                    setTimeout(() => {
                        targetEl.classList.remove('active-target');
                    }, 2000);
                }

                // --- Variables ---
                let lastDataString = "";
                let trendChartInstance = null;
                let avgTimeChartInstance = null;
                let compareChartInstance = null;
                let currentFilteredLogs = [];
                
                const categoricalColors = [
                    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', 
                    '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#64748b',
                    '#6366f1', '#14b8a6', '#eab308', '#d946ef', '#f43f5e'
                ];
                const thaiMonths = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];

                function truncateLabel(label, maxLength = 20) {
                    if (!label) return '';
                    return label.length > maxLength ? label.substring(0, maxLength) + '...' : label;
                }

                // --- UI Elements ---
                const facFilter = document.getElementById('facFilter');
                const branchFilter = document.getElementById('branchFilter');
                const presetDateFilter = document.getElementById('presetDateFilter');

                // --- Time Clock ---
                setInterval(() => {
                    const now = new Date();
                    document.getElementById('currentTime').innerText = now.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second:'2-digit' });
                }, 1000);

                // --- Flatpickr Setup ---
                const dateConfig = {
                    dateFormat: "Y-m-d", altInput: true, altFormat: "custom", maxDate: "today",
                    formatDate: function (date, format) {
                        if (format === "custom") return date.getDate() + ' ' + thaiMonths[date.getMonth()] + ' ' + (date.getFullYear() + 543);
                        return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
                    },
                    onChange: () => { presetDateFilter.value = 'custom'; applyPresetDate(); renderDashboard(); }
                };
                const startPicker = flatpickr("#startDate", dateConfig);
                const endPicker = flatpickr("#endDate", dateConfig);

                // --- Core Logic ---
                function fetchLatestData(isInitial = false) {
                    let script = document.createElement('script');
                    script.src = 'dashboard_data.js?t=' + new Date().getTime();
                    script.onload = function() {
                        const rawData = window.rawData || [];
                        const insideData = window.insideData || [];
                        const sessionData = window.sessionData || [];
                        const newDataString = JSON.stringify(rawData) + JSON.stringify(insideData) + JSON.stringify(sessionData);

                        if (newDataString !== lastDataString) {
                            lastDataString = newDataString;
                            updateFilterDropdowns(isInitial);
                            if (isInitial) applyPresetDate();
                            renderDashboard();
                        }
                        document.body.removeChild(script);
                    };
                    script.onerror = () => document.body.removeChild(script);
                    document.body.appendChild(script);
                }

                function updateFilterDropdowns(isInitial) {
                    const rawData = window.rawData || [];
                    const selFac = facFilter.value || "คณะทั้งหมด";

                    const faculties = ["คณะทั้งหมด", ...[...new Set(rawData.map(d => d.faculty))].sort()];
                    facFilter.innerHTML = faculties.map(f => `<option value="${f}">${f}</option>`).join('');
                    if (faculties.includes(selFac)) facFilter.value = selFac;

                    updateBranchList();
                }

                function updateBranchList() {
                    const rawData = window.rawData || [];
                    const selFac = facFilter.value;
                    const prevBranch = branchFilter.value;

                    let branches = ["สาขาทั้งหมด"];
                    if (selFac !== "คณะทั้งหมด") {
                        const filtered = rawData.filter(d => d.faculty === selFac);
                        branches = [...branches, ...[...new Set(filtered.map(d => d.branch))].sort()];
                    }

                    branchFilter.innerHTML = branches.map(b => `<option value="${b}">${b}</option>`).join('');
                    if (branches.includes(prevBranch)) branchFilter.value = prevBranch;
                }

                function applyPresetDate() {
                    const rawData = window.rawData || [];
                    const preset = presetDateFilter.value;
                    const today = new Date();
                    const todayStr = today.toISOString().split('T')[0];

                    if (preset === 'custom') {
                        startPicker.altInput.disabled = false; endPicker.altInput.disabled = false;
                        return;
                    }

                    startPicker.altInput.disabled = true; endPicker.altInput.disabled = true;

                    if (preset === 'all') {
                        const firstDateStr = rawData.length > 0 ? rawData.reduce((min, p) => p.date < min ? p.date : min, rawData[0].date) : todayStr;
                        startPicker.setDate(firstDateStr);
                    } else {
                        const pastDate = new Date();
                        pastDate.setDate(today.getDate() - parseInt(preset) + 1);
                        startPicker.setDate(pastDate.toISOString().split('T')[0]);
                    }
                    endPicker.setDate(todayStr);
                }

                function calculatePeakHour(logs) {
                    if (logs.length === 0) return "-";
                    let hourCounts = {};
                    logs.forEach(log => {
                        let hour = log.time.split(':')[0];
                        hourCounts[hour] = (hourCounts[hour] || 0) + 1;
                    });

                    let peakHour = Object.keys(hourCounts).reduce((a, b) => hourCounts[a] > hourCounts[b] ? a : b);
                    return `${peakHour}:00 - ${String(parseInt(peakHour)+1).padStart(2, '0')}:00 น.`;
                }

                function calculateTopStudents(logs) {
                    const studentMap = {};
                    logs.forEach(log => {
                        const sid = log.student_id;
                        if (!studentMap[sid]) {
                            studentMap[sid] = {
                                student_id: sid,
                                full_name: (log.first_name !== "ไม่ระบุ" ? log.first_name : "") + " " + (log.last_name || ""),
                                faculty: log.faculty || 'ไม่ระบุ',
                                branch: log.branch || 'ไม่ระบุ',
                                count: 0
                            };
                            if (studentMap[sid].full_name.trim() === "") {
                                studentMap[sid].full_name = sid;
                            }
                        }
                        studentMap[sid].count += 1;
                    });

                    return Object.values(studentMap)
                        .sort((a, b) => b.count - a.count)
                        .slice(0, 5);
                }

                function renderTop5Table(tbodyId, studentList, isFacultyView = false) {
                    const tbody = document.getElementById(tbodyId);
                    if (!studentList || studentList.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4" class="py-8 text-center text-slate-400 bg-white">ไม่มีข้อมูลการเข้าใช้งานในระบบ</td></tr>';
                        return;
                    }

                    const medalIcons = ['🥇', '🥈', '🥉'];

                    tbody.innerHTML = studentList.map((st, idx) => {
                        const rankBadge = idx < 3 
                            ? `<span class="text-base">${medalIcons[idx]}</span>` 
                            : `<span class="text-xs font-bold text-slate-400 pl-1">${idx + 1}</span>`;
                        
                        const subText = isFacultyView ? st.branch : st.faculty;

                        return `
                            <tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors bg-white">
                                <td class="py-3 px-4 font-medium whitespace-nowrap">${rankBadge}</td>
                                <td class="py-3 px-4 font-semibold text-slate-700 whitespace-nowrap">${st.full_name}</td>
                                <td class="py-3 px-4 text-xs text-slate-500 max-w-[140px] truncate" title="${subText}">${subText}</td>
                                <td class="py-3 px-4 text-right whitespace-nowrap"><span class="bg-blue-50 text-blue-700 px-2.5 py-1 rounded-md font-bold text-xs">${st.count} ครั้ง</span></td>
                            </tr>
                        `;
                    }).join('');
                }

                function renderDashboard() {
                    const rawData = window.rawData || [];
                    const insideData = window.insideData || [];
                    const sessionData = window.sessionData || [];
                    const selFac = facFilter.value;
                    const selBranch = branchFilter.value;

                    const startD = startPicker.selectedDates[0] ? new Date(startPicker.selectedDates[0].setHours(0,0,0,0)) : new Date(0);
                    const endD = endPicker.selectedDates[0] ? new Date(endPicker.selectedDates[0].setHours(23,59,59,999)) : new Date();

                    const dateFilteredLogs = rawData.filter(d => {
                        const dt = new Date(d.date);
                        return dt >= startD && dt <= endD;
                    });

                    currentFilteredLogs = dateFilteredLogs.filter(d => {
                        if (selFac !== "คณะทั้งหมด" && d.faculty !== selFac) return false;
                        if (selBranch !== "สาขาทั้งหมด" && d.branch !== selBranch) return false;
                        return true;
                    });

                    const filteredInside = insideData.filter(d => {
                        if (selFac !== "คณะทั้งหมด" && d.faculty !== selFac) return false;
                        if (selBranch !== "สาขาทั้งหมด" && d.branch !== selBranch) return false;
                        return true;
                    });

                    // --- KPIs ---
                    const uniqueUsersCount = new Set(currentFilteredLogs.map(log => log.student_id)).size;
                    document.getElementById('kpi-inside').innerText = filteredInside.length;
                    document.getElementById('kpi-unique-users').innerText = uniqueUsersCount;
                    document.getElementById('kpi-total').innerText = currentFilteredLogs.length;
                    document.getElementById('kpi-peak-hour').innerText = calculatePeakHour(currentFilteredLogs);

                    const groupCounts = {};
                    const groupBy = selFac === "คณะทั้งหมด" ? "faculty" : "branch";
                    currentFilteredLogs.forEach(d => groupCounts[d[groupBy]] = (groupCounts[d[groupBy]] || 0) + 1);
                    const sortedGroups = Object.entries(groupCounts).sort((a,b) => b[1] - a[1]);
                    
                    document.getElementById('kpi-top-group-title').innerText = selFac === "คณะทั้งหมด" ? "คณะที่เข้าใช้งานมากที่สุด" : "สาขาที่เข้าใช้งานมากที่สุด";
                    document.getElementById('kpi-top-group').innerText = sortedGroups.length > 0 ? sortedGroups[0][0] : "ไม่มีข้อมูล";

                    // --- Render Top 5 Section ---
                    const top5Title = document.getElementById('top5Title');
                    const top5Subtitle = document.getElementById('top5Subtitle');
                    const top5GroupHeader = document.getElementById('top5GroupHeader');

                    let logsForRanking = [];
                    let isFacultyView = false;

                    if (selFac === "คณะทั้งหมด") {
                        isFacultyView = false;
                        logsForRanking = dateFilteredLogs; 
                        top5Title.innerHTML = `<span>🏆</span> 5 อันดับนักศึกษาเข้าใช้งานสูงสุด (ระดับมหาวิทยาลัย)`;
                        top5Subtitle.innerText = `จัดอันดับจากความถี่การเข้าใช้งานทั้งหมด (ทุกคณะ)`;
                        top5GroupHeader.innerText = `คณะ`;
                    } else {
                        isFacultyView = true;
                        logsForRanking = currentFilteredLogs; 
                        top5Title.innerHTML = `<span>🎓</span> 5 อันดับนักศึกษาเข้าใช้งานสูงสุด (<span class="text-blue-600">คณะ${selFac}</span>)`;
                        top5Subtitle.innerText = `จัดอันดับจำแนกเฉพาะในระดับคณะ`;
                        top5GroupHeader.innerText = `สาขา`;
                    }

                    const top5Data = calculateTopStudents(logsForRanking);
                    renderTop5Table('top5Body', top5Data, isFacultyView);

                    // --- Table ---
                    const tbody = document.getElementById('liveTableBody');
                    if(filteredInside.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-400 bg-white">ไม่มีผู้ใช้งานที่ตรงตามเงื่อนไขในขณะนี้</td></tr>';
                    } else {
                        const sortedInside = filteredInside.sort((a, b) => b.time_in.localeCompare(a.time_in));
                        const maxDisplay = 50;
                        const displayList = sortedInside.slice(0, maxDisplay);

                        tbody.innerHTML = displayList.map((user, i) => `
                            <tr class="border-b border-slate-100 hover:bg-emerald-50/50 transition-colors bg-white">
                                <td class="py-4 px-6 text-slate-500 font-medium whitespace-nowrap">${i + 1}</td>
                                <td class="py-4 px-6 whitespace-nowrap"><span class="bg-emerald-100 text-emerald-700 py-1 px-2 rounded-md text-xs font-bold">${user.time_in}</span></td>
                                <td class="py-4 px-6 font-bold text-slate-700 whitespace-nowrap">${user.first_name} ${user.last_name}</td>
                                <td class="py-4 px-6 text-slate-600 max-w-[200px] truncate" title="${user.faculty}">${user.faculty}</td>
                                <td class="py-4 px-6 text-slate-500 text-xs max-w-[200px] truncate" title="${user.branch}">${user.branch}</td>
                            </tr>
                        `).join('');

                        if (filteredInside.length > maxDisplay) {
                            tbody.innerHTML += `
                                <tr>
                                    <td colspan="5" class="py-4 text-center text-xs text-slate-500 bg-slate-50">
                                        กำลังแสดง ${maxDisplay} คนล่าสุด จากทั้งหมด ${filteredInside.length} คน
                                    </td>
                                </tr>
                            `;
                        }
                    }

                    // --- Daily Trend Chart (เปรียบเทียบ ความถี่ vs จำนวนคน) ---
                    const trendSummary = {};
                    const dailyUsersMap = {};

                    currentFilteredLogs.forEach(row => {
                        trendSummary[row.date] = (trendSummary[row.date] || 0) + 1;
                        if (!dailyUsersMap[row.date]) {
                            dailyUsersMap[row.date] = new Set();
                        }
                        dailyUsersMap[row.date].add(row.student_id);
                    });

                    const sortedDates = Object.keys(trendSummary).sort();
                    const trendLabels = sortedDates.map(d => {
                        const dt = new Date(d);
                        return dt.getDate() + ' ' + thaiMonths[dt.getMonth()];
                    });
                    const trendFreqValues = sortedDates.map(d => trendSummary[d]);
                    const trendUserValues = sortedDates.map(d => dailyUsersMap[d] ? dailyUsersMap[d].size : 0);

                    if (trendChartInstance) trendChartInstance.destroy();
                    const ctx1 = document.getElementById('trendChart').getContext('2d');
                    trendChartInstance = new Chart(ctx1, {
                        type: 'bar',
                        data: {
                            labels: trendLabels,
                            datasets: [
                                { 
                                    label: ' ความถี่ (ครั้ง)', 
                                    data: trendFreqValues, 
                                    backgroundColor: '#6366f1', 
                                    borderRadius: 4 
                                },
                                { 
                                    label: ' ผู้ใช้งาน (คน)', 
                                    data: trendUserValues, 
                                    backgroundColor: '#10b981', 
                                    borderRadius: 4 
                                }
                            ]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false,
                            plugins: { 
                                legend: { 
                                    display: true, 
                                    position: 'top', 
                                    labels: { font: {family: 'Sarabun', size: 12} } 
                                }, 
                                tooltip: { 
                                    backgroundColor: 'rgba(15, 23, 42, 0.9)', 
                                    titleFont: {family: 'Sarabun'}, 
                                    bodyFont: {family: 'Sarabun', size: 14} 
                                } 
                            },
                            scales: {
                                y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { stepSize: 1, font: {family: 'Sarabun'} } },
                                x: { grid: { display: false }, ticks: { font: {family: 'Sarabun'} } }
                            }
                        }
                    });

                    // --- Combined Compare Chart (ความถี่ vs จำนวนคน ตามคณะ/สาขา) ---
                    document.getElementById('compareTitle').innerText = selFac === "คณะทั้งหมด" 
                        ? "เปรียบเทียบความถี่การเข้าใช้งาน (ครั้ง) และ จำนวนผู้ใช้งาน (คน) จำแนกตามคณะ" 
                        : "เปรียบเทียบความถี่การเข้าใช้งาน (ครั้ง) และ จำนวนผู้ใช้งาน (คน) จำแนกตามสาขา";

                    const distLabels = sortedGroups.map(g => g[0]);
                    const distValues = sortedGroups.map(g => g[1]);

                    const uniqueUsersMap = {};
                    currentFilteredLogs.forEach(d => {
                        if (!uniqueUsersMap[d.student_id]) {
                            uniqueUsersMap[d.student_id] = d;
                        }
                    });

                    const uniqueGroupCounts = {};
                    Object.values(uniqueUsersMap).forEach(d => {
                        uniqueGroupCounts[d[groupBy]] = (uniqueGroupCounts[d[groupBy]] || 0) + 1;
                    });

                    const uniqueValuesAligned = distLabels.map(label => uniqueGroupCounts[label] || 0);

                    if (compareChartInstance) compareChartInstance.destroy();
                    const ctxCompare = document.getElementById('compareChart').getContext('2d');
                    
                    compareChartInstance = new Chart(ctxCompare, {
                        type: 'bar',
                        data: {
                            labels: distLabels,
                            datasets: [
                                { 
                                    label: ' ความถี่ (ครั้ง)', 
                                    data: distValues, 
                                    backgroundColor: '#3b82f6', 
                                    borderRadius: 4 
                                },
                                { 
                                    label: ' ผู้ใช้งาน (คน)', 
                                    data: uniqueValuesAligned, 
                                    backgroundColor: '#10b981', 
                                    borderRadius: 4 
                                }
                            ]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false,
                            plugins: { 
                                legend: { 
                                    display: true, 
                                    position: 'top', 
                                    labels: { font: {family: 'Sarabun', size: 14} } 
                                }, 
                                tooltip: { 
                                    backgroundColor: 'rgba(15, 23, 42, 0.9)', 
                                    titleFont: {family: 'Sarabun'},
                                    bodyFont: {family: 'Sarabun', size: 14} 
                                } 
                            },
                            scales: {
                                y: { 
                                    beginAtZero: true, 
                                    grid: { color: '#f1f5f9' }, 
                                    ticks: { font: {family: 'Sarabun'}, stepSize: 1 } 
                                },
                                x: { 
                                    grid: { display: false }, 
                                    ticks: { 
                                        font: {family: 'Sarabun'}, 
                                        callback: function(val) { return truncateLabel(this.getLabelForValue(val), 15); } 
                                    } 
                                }
                            }
                        }
                    });

                    // --- Dynamic Average Time Chart ---
                    const filteredSessions = sessionData.filter(d => {
                        const dt = new Date(d.date);
                        if (dt < startD || dt > endD) return false;
                        if (selFac !== "คณะทั้งหมด" && d.faculty !== selFac) return false;
                        if (selBranch !== "สาขาทั้งหมด" && d.branch !== selBranch) return false;
                        return true;
                    });

                    const sumTime = {};
                    const countTime = {};
                    filteredSessions.forEach(s => {
                        const grp = selFac === "คณะทั้งหมด" ? s.faculty : s.branch;
                        sumTime[grp] = (sumTime[grp] || 0) + s.total_hours;
                        countTime[grp] = (countTime[grp] || 0) + 1;
                    });

                    const avgGroups = Object.keys(sumTime).sort((a, b) => (sumTime[b] / countTime[b]) - (sumTime[a] / countTime[a]));

                    const avgCanvas = document.getElementById('avgTimeChart');
                    const avgEmptyState = document.getElementById('avgTimeEmptyState');

                    if (avgGroups.length === 0) {
                        if (avgTimeChartInstance) { avgTimeChartInstance.destroy(); avgTimeChartInstance = null; }
                        avgCanvas.classList.add('hidden');
                        avgEmptyState.classList.remove('hidden');
                        document.getElementById('avgTimeSubtitle').innerText = 'คำนวณจากระยะเวลาที่ใช้งานในแต่ละวัน';
                        return;
                    }
                    avgCanvas.classList.remove('hidden');
                    avgEmptyState.classList.add('hidden');

                    const rawAvgHours = avgGroups.map(grp => sumTime[grp] / countTime[grp]);
                    const maxAvgHours = Math.max(...rawAvgHours, 0);

                    const useMinutes = maxAvgHours > 0 && maxAvgHours < 1;
                    const timeUnitStr = useMinutes ? "นาที" : "ชั่วโมง";

                    const avgDataValues = avgGroups.map(grp => {
                        const hrs = sumTime[grp] / countTime[grp];
                        return useMinutes ? Math.round(hrs * 60) : parseFloat(hrs.toFixed(2));
                    });
                    
                    const avgColors = avgGroups.map(label => {
                        const distIndex = distLabels.indexOf(label);
                        return distIndex !== -1 ? categoricalColors[distIndex % categoricalColors.length] : '#94a3b8';
                    });

                    document.getElementById('avgTimeTitle').innerText = selFac === "คณะทั้งหมด" 
                        ? `เวลาเฉลี่ยในการเข้าใช้พื้นที่ (${timeUnitStr}) จำแนกตามคณะ` 
                        : `เวลาเฉลี่ยในการเข้าใช้พื้นที่ (${timeUnitStr}) จำแนกตามสาขา`;
                    
                    document.getElementById('avgTimeSubtitle').innerText = useMinutes 
                        ? 'คำนวณและแปลงหน่วยเป็นนาทีอัตโนมัติเนื่องจากมีระยะเวลาน้อยกว่า 1 ชั่วโมง'
                        : 'คำนวณเป็นชั่วโมงเฉลี่ยรวมที่ใช้งานในแต่ละวัน';

                    if (avgTimeChartInstance) avgTimeChartInstance.destroy();
                    const ctx3 = document.getElementById('avgTimeChart').getContext('2d');
                    avgTimeChartInstance = new Chart(ctx3, {
                        type: 'bar',
                        data: {
                            labels: avgGroups,
                            datasets: [{ label: ` ${timeUnitStr}เฉลี่ย`, data: avgDataValues, backgroundColor: avgColors, borderRadius: 4, maxBarThickness: 50 }]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false },
                                tooltip: {
                                    backgroundColor: 'rgba(15, 23, 42, 0.9)', titleFont: {family: 'Sarabun'},
                                    bodyFont: {family: 'Sarabun', size: 14}, 
                                    callbacks: { 
                                        label: function(context) { 
                                            const val = context.raw;
                                            if (useMinutes) {
                                                return ` เฉลี่ย ${val} นาที`;
                                            } else {
                                                const hrs = Math.floor(val);
                                                const mins = Math.round((val - hrs) * 60);
                                                return ` เฉลี่ย ${hrs > 0 ? hrs + ' ชม. ' : ''}${mins} นาที (${val} ชม.)`;
                                            }
                                        } 
                                    }
                                }
                            },
                            scales: {
                                y: { 
                                    beginAtZero: true, 
                                    grid: { color: '#f1f5f9' }, 
                                    ticks: { 
                                        font: {family: 'Sarabun'},
                                        callback: function(val) { return val + ' ' + timeUnitStr; }
                                    } 
                                },
                                x: { 
                                    grid: { display: false }, 
                                    ticks: { font: {family: 'Sarabun'}, callback: function(val, index) { return truncateLabel(this.getLabelForValue(val)); } } 
                                }
                            }
                        }
                    });
                }

                // --- Event Listeners ---
                facFilter.addEventListener('change', () => { updateBranchList(); renderDashboard(); });
                branchFilter.addEventListener('change', renderDashboard);
                presetDateFilter.addEventListener('change', () => { applyPresetDate(); renderDashboard(); });

                // Init
                fetchLatestData(true);
                setInterval(() => fetchLatestData(false), 3000);

            </script>
        </body>
        </html>
        """

        file_path = os.path.join(os.getcwd(), Config.DASHBOARD_DIR_HTML)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(html_content)

        webbrowser.open('file://' + file_path)
        log("- แสดงแดชบอร์ดสถิติระดับมืออาชีพสำเร็จ")

    except Exception as e:
        log(f"❌ Graph Error: {e}")
        messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถสร้างแดชบอร์ดสถิติได้: {e}")