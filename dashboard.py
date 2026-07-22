import os
import json
import webbrowser
from datetime import datetime
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

            # 1. ดึงข้อมูล Logs ทั้งหมดเพื่อเตรียมคำนวณและหาเวลาล่าสุด
            logs_ref = shared_state.db.collection("attendance_logs").stream()
            raw_events = []
            all_logs = []
            latest_clock_in = {} # เก็บเวลาเข้าล่าสุดของวันนี้ { student_id: time }

            for doc in logs_ref:
                d = doc.to_dict()
                action = d.get("action", "")
                s_id = d.get("student_id", "")
                d_date = d.get("date", "")
                d_time = d.get("time", "00:00:00")
                faculty = d.get("faculty", "ไม่ระบุ") if d.get("faculty") else "ไม่ระบุ"
                branch = d.get("branch", "ไม่ระบุ") if d.get("branch") else "ไม่ระบุ"

                if not s_id: # ข้าม log ที่ไม่มีรหัสนักศึกษา
                    continue

                raw_events.append({
                    "student_id": s_id,
                    "action": action,
                    "date": d_date,
                    "time": d_time,
                    "faculty": faculty,
                    "branch": branch
                })

                # เก็บเฉพาะ Clock-IN สำหรับคำนวณจำนวนครั้งที่เข้าใช้รวม
                if action == "Clock-IN":
                    all_logs.append({
                        "date": d_date,
                        "time": d_time,
                        "faculty": faculty,
                        "branch": branch
                    })
                    if d_date == today_date:
                        if s_id not in latest_clock_in or d_time > latest_clock_in[s_id]:
                            latest_clock_in[s_id] = d_time

            # 2. Logic ใหม่: คำนวณระยะเวลาการใช้งาน (ชั่วโมงรวมต่อวัน/ต่อคน)
            events_by_user_date = {}
            for ev in raw_events:
                key = (ev["student_id"], ev["date"])
                if key not in events_by_user_date:
                    events_by_user_date[key] = []
                events_by_user_date[key].append(ev)

            session_data = []
            for key, events in events_by_user_date.items():
                student_id, d_date = key
                events.sort(key=lambda x: x["time"]) # เรียงตามเวลาจากเช้าไปดึก

                total_hours_today = 0.0
                in_time = None

                # ดึงคณะ/สาขา จาก event ล่าสุด (กันกรณีข้อมูลแหว่ง)
                faculty = next((e["faculty"] for e in reversed(events) if e["faculty"] != "ไม่ระบุ"), "ไม่ระบุ")
                branch = next((e["branch"] for e in reversed(events) if e["branch"] != "ไม่ระบุ"), "ไม่ระบุ")

                for ev in events:
                    if ev["action"] == "Clock-IN":
                        # ถ้ามี in_time อยู่แล้ว (สแกน IN ซ้ำ) เราจะไม่ทับค่า เพื่อยึดเวลาเข้าครั้งแรกของรอบนั้น
                        if in_time is None:
                            in_time = ev["time"]
                    elif ev["action"] == "Clock-OUT" and in_time is not None:
                        try:
                            # คำนวณหาความต่างของเวลา
                            t1 = datetime.strptime(in_time, "%H:%M:%S")
                            t2 = datetime.strptime(ev["time"], "%H:%M:%S")
                            duration_hours = (t2 - t1).total_seconds() / 3600.0

                            # ป้องกันเวลาติดลบกรณีข้ามวัน (ถึงแม้เราจะ group by date ก็เผื่อไว้)
                            if duration_hours > 0:
                                total_hours_today += duration_hours
                        except Exception:
                            pass

                        # จบรอบนี้ รีเซ็ต in_time เพื่อรอการเข้าครั้งใหม่ในวันเดียวกัน
                        in_time = None

                # ถ้านักศึกษาคนนี้ มียอดเวลาใช้งานในวันนี้มากกว่า 0 ให้บันทึกเป็นสถิติ
                if total_hours_today > 0:
                    session_data.append({
                        "student_id": student_id,
                        "date": d_date,
                        "faculty": faculty,
                        "branch": branch,
                        "total_hours": total_hours_today
                    })

            # 3. ดึงคนที่อยู่ด้านในปัจจุบัน
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
            <title>Access Control Analytics (Pro)</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/flatpickr/4.6.13/flatpickr.min.css">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/flatpickr/4.6.13/flatpickr.min.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                body { font-family: 'Sarabun', sans-serif; background-color: #f8fafc; }
                .glass-card { background: white; border-radius: 16px; box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.04); border: 1px solid #f1f5f9; }
                .form-select, .form-input {
                    width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px;
                    font-family: 'Sarabun', sans-serif; font-size: 14px; outline: none; transition: all 0.2s; background: #fff;
                }
                .form-select:focus, .form-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1); }
                .form-input:disabled { background-color: #f1f5f9; color: #94a3b8; cursor: not-allowed; }
                .table-container::-webkit-scrollbar { width: 6px; }
                .table-container::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 4px; }
                .fade-in { animation: fadeIn 0.4s ease-in-out; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            </style>
        </head>
        <body class="p-4 md:p-8 text-slate-800">
            <div class="max-w-7xl mx-auto fade-in">

                <!-- Header Section -->
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                    <div>
                        <h1 class="text-3xl font-bold text-slate-900 tracking-tight">Access Analytics</h1>
                        <p class="text-sm text-slate-500 mt-2 flex items-center gap-2 font-medium">
                            <span class="relative flex h-3 w-3">
                              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                              <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                            </span>
                            Live System Auto-Refresh
                        </p>
                    </div>
                    <div class="flex gap-3">
                        <div class="bg-white px-5 py-2 rounded-lg border border-slate-200 shadow-sm flex flex-col justify-center">
                            <p class="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Local Time</p>
                            <p id="currentTime" class="text-lg font-bold text-blue-600 leading-none mt-1"></p>
                        </div>
                    </div>
                </div>

                <!-- Filters Section -->
                <div class="glass-card p-6 mb-8">
                    <div class="flex items-center gap-2 mb-4">
                        <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path></svg>
                        <h2 class="text-base font-semibold text-slate-700">ตัวกรองข้อมูลอัจฉริยะ (Smart Filters)</h2>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-5 items-end">
                        <div>
                            <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">คณะ</label>
                            <select id="facFilter" class="form-select"></select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">สาขา</label>
                            <select id="branchFilter" class="form-select"></select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">ช่วงเวลาแบบด่วน</label>
                            <select id="presetDateFilter" class="form-select">
                                <option value="all" selected>ข้อมูลทั้งหมด (All Time)</option>
                                <option value="7">7 วันย้อนหลัง</option>
                                <option value="15">15 วันย้อนหลัง</option>
                                <option value="30">30 วันย้อนหลัง</option>
                                <option value="custom">กำหนดเอง (Custom Range)</option>
                            </select>
                        </div>
                        <div class="flex items-center gap-3">
                            <div class="w-full">
                                <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">เริ่ม</label>
                                <input type="text" id="startDate" class="form-input">
                            </div>
                            <span class="text-slate-300 mt-6">-</span>
                            <div class="w-full">
                                <label class="block text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">สิ้นสุด</label>
                                <input type="text" id="endDate" class="form-input">
                            </div>
                        </div>
                    </div>
                </div>

                <!-- KPI Cards -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <div class="glass-card p-6 border-l-4 border-l-blue-500 relative overflow-hidden">
                        <div class="absolute -right-4 -bottom-4 opacity-10">
                            <svg class="w-24 h-24 text-blue-500" fill="currentColor" viewBox="0 0 20 20"><path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"></path></svg>
                        </div>
                        <h3 class="text-slate-500 font-semibold text-sm mb-1 z-10 relative">อยู่ในห้องขณะนี้</h3>
                        <div class="text-4xl font-bold text-slate-800 z-10 relative mt-2"><span id="kpi-inside">0</span> <span class="text-base font-normal text-slate-400">คน</span></div>
                    </div>

                    <div class="glass-card p-6 border-l-4 border-l-emerald-500">
                        <h3 class="text-slate-500 font-semibold text-sm mb-1">ยอดเข้าใช้งานสะสม</h3>
                        <div class="text-4xl font-bold text-slate-800 mt-2"><span id="kpi-total">0</span> <span class="text-base font-normal text-slate-400">ครั้ง</span></div>
                    </div>

                    <div class="glass-card p-6 border-l-4 border-l-amber-500 flex flex-col justify-center">
                        <h3 class="text-slate-500 font-semibold text-sm mb-1">กลุ่มผู้ใช้งานหลัก</h3>
                        <div class="text-lg font-bold text-slate-800 mt-2 truncate" id="kpi-top-group" title="...">-</div>
                        <p class="text-xs text-slate-400 mt-1">จากผลการกรอง</p>
                    </div>

                    <div class="glass-card p-6 border-l-4 border-l-purple-500 flex flex-col justify-center">
                        <h3 class="text-slate-500 font-semibold text-sm mb-1">Peak Hour (เวลาหนาแน่น)</h3>
                        <div class="text-2xl font-bold text-slate-800 mt-2" id="kpi-peak-hour">-</div>
                        <p class="text-xs text-slate-400 mt-1">ช่วงเวลาที่คนเข้ามากที่สุด</p>
                    </div>
                </div>

                <!-- Charts Section 1 -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                    <div class="glass-card p-6 lg:col-span-2">
                        <h2 class="text-base font-bold text-slate-700 mb-6">สถิติการเข้าใช้งานรายวัน (Daily Trend)</h2>
                        <div class="relative h-72">
                            <canvas id="trendChart"></canvas>
                        </div>
                    </div>
                    <div class="glass-card p-6">
                        <h2 class="text-base font-bold text-slate-700 mb-6" id="doughnutTitle">สัดส่วนผู้ใช้งาน (Demographics)</h2>
                        <div class="relative h-64 flex justify-center">
                            <canvas id="distChart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Charts Section 2: Average Time -->
                <div class="glass-card p-6 mb-8">
                    <h2 class="text-base font-bold text-slate-700 mb-2" id="avgTimeTitle">เวลาเข้าใช้งานเฉลี่ยต่อคนต่อวัน (ชั่วโมง)</h2>
                    <p class="text-xs text-slate-500 mb-4">นับรวมการเข้าออกหลายรอบใน 1 วันของนักศึกษาแต่ละคน เพื่อหาค่าเฉลี่ยรายวันของแต่ละคณะ</p>
                    <div class="relative h-72">
                        <canvas id="avgTimeChart"></canvas>
                    </div>
                </div>

                <!-- Live User Table -->
                <div class="glass-card overflow-hidden">
                    <div class="p-6 border-b border-slate-100 flex justify-between items-center bg-white">
                        <h2 class="text-base font-bold text-slate-700 flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                            รายชื่อผู้ที่ยังอยู่ด้านใน (Active Users)
                        </h2>
                    </div>
                    <div class="table-container max-h-80 overflow-y-auto bg-slate-50/50">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="bg-white text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                                    <th class="py-4 px-6 font-bold sticky top-0 bg-white">ลำดับ</th>
                                    <th class="py-4 px-6 font-bold sticky top-0 bg-white">เวลาที่เข้าล่าสุด (Time In)</th>
                                    <th class="py-4 px-6 font-bold sticky top-0 bg-white">ชื่อ - นามสกุล</th>
                                    <th class="py-4 px-6 font-bold sticky top-0 bg-white">คณะ</th>
                                    <th class="py-4 px-6 font-bold sticky top-0 bg-white">สาขา</th>
                                </tr>
                            </thead>
                            <tbody id="liveTableBody" class="text-sm text-slate-600">
                                <!-- Data injected via JS -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <script>
                // --- Variables ---
                let lastDataString = "";
                let trendChartInstance = null;
                let distChartInstance = null;
                let avgTimeChartInstance = null;
                let currentFilteredLogs = [];
                const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#64748b'];
                const thaiMonths = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];

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
                    const selBranch = branchFilter.value || "สาขาทั้งหมด";

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
                    return `${peakHour}:00 - ${String(parseInt(peakHour)+1).padStart(2, '0')}:00`;
                }

                function renderDashboard() {
                    const rawData = window.rawData || [];
                    const insideData = window.insideData || [];
                    const sessionData = window.sessionData || [];
                    const selFac = facFilter.value;
                    const selBranch = branchFilter.value;

                    // 1. กรองข้อมูลเวลา
                    const startD = startPicker.selectedDates[0] ? new Date(startPicker.selectedDates[0].setHours(0,0,0,0)) : new Date(0);
                    const endD = endPicker.selectedDates[0] ? new Date(endPicker.selectedDates[0].setHours(23,59,59,999)) : new Date();

                    // 2. กรองข้อมูลทั้งหมดตามเงื่อนไข
                    currentFilteredLogs = rawData.filter(d => {
                        const dt = new Date(d.date);
                        if (dt < startD || dt > endD) return false;
                        if (selFac !== "คณะทั้งหมด" && d.faculty !== selFac) return false;
                        if (selBranch !== "สาขาทั้งหมด" && d.branch !== selBranch) return false;
                        return true;
                    });

                    const filteredInside = insideData.filter(d => {
                        if (selFac !== "คณะทั้งหมด" && d.faculty !== selFac) return false;
                        if (selBranch !== "สาขาทั้งหมด" && d.branch !== selBranch) return false;
                        return true;
                    });

                    // --- อัปเดต KPIs ---
                    document.getElementById('kpi-inside').innerText = filteredInside.length;
                    document.getElementById('kpi-total').innerText = currentFilteredLogs.length;
                    document.getElementById('kpi-peak-hour').innerText = calculatePeakHour(currentFilteredLogs);

                    const groupCounts = {};
                    const groupBy = selFac === "คณะทั้งหมด" ? "faculty" : "branch";
                    currentFilteredLogs.forEach(d => groupCounts[d[groupBy]] = (groupCounts[d[groupBy]] || 0) + 1);
                    const sortedGroups = Object.entries(groupCounts).sort((a,b) => b[1] - a[1]);
                    document.getElementById('kpi-top-group').innerText = sortedGroups.length > 0 ? sortedGroups[0][0] : "ไม่มีข้อมูล";
                    document.getElementById('kpi-top-group').title = sortedGroups.length > 0 ? sortedGroups[0][0] : "";

                    // --- อัปเดต Table (Live) ---
                                        const tbody = document.getElementById('liveTableBody');

                                        if(filteredInside.length === 0) {
                                            tbody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-400 bg-white">ไม่มีผู้ใช้งานที่ตรงตามเงื่อนไขในขณะนี้</td></tr>';
                                        } else {
                                            // 1. เรียงลำดับเวลาเข้า (Time In) จากล่าสุด (มากไปน้อย)
                                            const sortedInside = filteredInside.sort((a, b) => b.time_in.localeCompare(a.time_in));

                                            // 2. จำกัดการแสดงผลที่ 50 คนล่าสุด (เปลี่ยนเลขได้ตามต้องการ)
                                            const maxDisplay = 50;
                                            const displayList = sortedInside.slice(0, maxDisplay);

                                            tbody.innerHTML = displayList.map((user, i) => `
                                                <tr class="border-b border-slate-100 hover:bg-blue-50/50 transition-colors bg-white">
                                                    <td class="py-4 px-6 text-slate-500 font-medium">${i + 1}</td>
                                                    <td class="py-4 px-6"><span class="bg-blue-100 text-blue-700 py-1 px-2 rounded-md text-xs font-bold">${user.time_in}</span></td>
                                                    <td class="py-4 px-6 font-bold text-slate-700">${user.first_name} ${user.last_name}</td>
                                                    <td class="py-4 px-6 text-slate-600">${user.faculty}</td>
                                                    <td class="py-4 px-6 text-slate-500 text-xs">${user.branch}</td>
                                                </tr>
                                            `).join('');

                                            // 3. (Optional) เพิ่มแถวแจ้งเตือนด้านล่างสุด หากมีคนอยู่ข้างในมากกว่าที่แสดงผล
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

                    // --- อัปเดต Trend Chart ---
                    const trendSummary = {};
                    currentFilteredLogs.forEach(row => {
                        trendSummary[row.date] = (trendSummary[row.date] || 0) + 1;
                    });
                    const sortedDates = Object.keys(trendSummary).sort();
                    const trendLabels = sortedDates.map(d => {
                        const dt = new Date(d);
                        return dt.getDate() + ' ' + thaiMonths[dt.getMonth()];
                    });
                    const trendValues = sortedDates.map(d => trendSummary[d]);

                    const trendDataObj = {
                        labels: trendLabels,
                        datasets: [{
                            label: ' จำนวนผู้ใช้',
                            data: trendValues,
                            backgroundColor: 'rgba(59, 130, 246, 0.9)',
                            hoverBackgroundColor: 'rgba(37, 99, 235, 1)',
                            borderRadius: 6,
                            barThickness: 'flex',
                            maxBarThickness: 45
                        }]
                    };

                    if (trendChartInstance) {
                        trendChartInstance.data = trendDataObj;
                        trendChartInstance.update();
                    } else {
                        const ctx1 = document.getElementById('trendChart').getContext('2d');
                        trendChartInstance = new Chart(ctx1, {
                            type: 'bar',
                            data: trendDataObj,
                            options: {
                                responsive: true, maintainAspectRatio: false,
                                plugins: {
                                    legend: { display: false },
                                    tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.9)', titleFont: {family: 'Sarabun'}, bodyFont: {family: 'Sarabun', size: 14}, padding: 12, cornerRadius: 8 }
                                },
                                scales: {
                                    y: { beginAtZero: true, grid: { color: '#f1f5f9', drawBorder: false }, ticks: { stepSize: 1, font: {family: 'Sarabun'} } },
                                    x: { grid: { display: false }, ticks: { font: {family: 'Sarabun'} } }
                                }
                            }
                        });
                    }

                    // --- อัปเดต Distribution Chart ---
                    document.getElementById('doughnutTitle').innerText = selFac === "คณะทั้งหมด" ? "สัดส่วนแบ่งตามคณะ (Faculty)" : "สัดส่วนแบ่งตามสาขา (Branch)";

                    const distDataObj = {
                        labels: sortedGroups.map(g => g[0]),
                        datasets: [{
                            data: sortedGroups.map(g => g[1]),
                            backgroundColor: colors,
                            borderWidth: 3,
                            borderColor: '#ffffff',
                            hoverOffset: 8
                        }]
                    };

                    if (distChartInstance) {
                        distChartInstance.data = distDataObj;
                        distChartInstance.update();
                    } else {
                        const ctx2 = document.getElementById('distChart').getContext('2d');
                        distChartInstance = new Chart(ctx2, {
                            type: 'doughnut',
                            data: distDataObj,
                            options: {
                                responsive: true, maintainAspectRatio: false,
                                plugins: {
                                    legend: { position: 'bottom', labels: { font: { family: 'Sarabun' }, boxWidth: 12, padding: 15, usePointStyle: true } },
                                    tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.9)', bodyFont: {family: 'Sarabun', size: 14}, padding: 12, cornerRadius: 8 }
                                },
                                cutout: '65%'
                            }
                        });
                    }

                    // --- อัปเดต Average Time Chart (อิงยอดรวมรายวันแล้วนำมาเฉลี่ย) ---
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
                        // เอา total_hours (ยอดรวมของคนนั้นใน 1 วัน) มารวมกัน
                        sumTime[grp] = (sumTime[grp] || 0) + s.total_hours;
                        // นับ 1 คือ = นับ 1 คนต่อวัน
                        countTime[grp] = (countTime[grp] || 0) + 1;
                    });

                    const avgGroups = Object.keys(sumTime).sort((a, b) => (sumTime[b] / countTime[b]) - (sumTime[a] / countTime[a]));
                    const avgLabels = avgGroups;
                    const avgDataValues = avgGroups.map(grp => (sumTime[grp] / countTime[grp]).toFixed(2));

                    document.getElementById('avgTimeTitle').innerText = selFac === "คณะทั้งหมด" ? "เวลาเข้าใช้งานเฉลี่ยต่อคนต่อวันแบ่งตามคณะ (ชั่วโมง)" : "เวลาเข้าใช้งานเฉลี่ยต่อคนต่อวันแบ่งตามสาขา (ชั่วโมง)";

                    const avgDataObj = {
                        labels: avgLabels,
                        datasets: [{
                            label: ' ชั่วโมงเฉลี่ย',
                            data: avgDataValues,
                            backgroundColor: 'rgba(16, 185, 129, 0.85)',
                            hoverBackgroundColor: 'rgba(5, 150, 105, 1)',
                            borderRadius: 6,
                            barThickness: 'flex',
                            maxBarThickness: 50
                        }]
                    };

                    if (avgTimeChartInstance) {
                        avgTimeChartInstance.data = avgDataObj;
                        avgTimeChartInstance.update();
                    } else {
                        const ctx3 = document.getElementById('avgTimeChart').getContext('2d');
                        avgTimeChartInstance = new Chart(ctx3, {
                            type: 'bar',
                            data: avgDataObj,
                            options: {
                                responsive: true, maintainAspectRatio: false,
                                indexAxis: 'x',
                                plugins: {
                                    legend: { display: false },
                                    tooltip: {
                                        backgroundColor: 'rgba(15, 23, 42, 0.9)', titleFont: {family: 'Sarabun'},
                                        bodyFont: {family: 'Sarabun', size: 14}, padding: 12, cornerRadius: 8,
                                        callbacks: {
                                            label: function(context) {
                                                return ` เฉลี่ย ${context.raw} ชั่วโมง`;
                                            }
                                        }
                                    }
                                },
                                scales: {
                                    y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: {family: 'Sarabun'} } },
                                    x: { grid: { display: false }, ticks: { font: {family: 'Sarabun'} } }
                                }
                            }
                        });
                    }
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
        messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถสร้างแดชบอร์ดได้: {e}")
