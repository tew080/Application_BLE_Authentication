import threading
import tkinter as tk
from tkinter import messagebox

import shared_state
from ble_scanner import run_background_scanner
from dashboard import show_dashboard_graph
from db_manager import import_csv_to_firebase, get_student_by_id, update_student_data
from config import Config

def open_edit_window(parent):
    """หน้าต่างสำหรับค้นหาและแก้ไขข้อมูลรายบุคคล"""
    edit_win = tk.Toplevel(parent)
    edit_win.title("แก้ไขข้อมูลนักศึกษา")
    edit_win.geometry("450x480")
    edit_win.configure(bg="#34495e")
    edit_win.resizable(False, False)

    # ทำให้หน้าต่างนี้บังหน้าต่าง Admin ชั่วคราวจนกว่าจะปิด
    edit_win.transient(parent)
    edit_win.grab_set()

    # --- ส่วนค้นหา ---
    search_frame = tk.Frame(edit_win, bg="#34495e")
    search_frame.pack(pady=(20, 10))

    tk.Label(search_frame, text="ค้นหารหัส นศ.:", bg="#ecf0f1", font=("Arial", 12, "bold"), fg="#2c3e50").grid(row=0, column=0, padx=5)
    entry_search = tk.Entry(search_frame, font=("Arial", 12), width=15)
    entry_search.grid(row=0, column=1, padx=5)

    # --- ส่วนฟอร์มแก้ไขข้อมูล ---
    form_frame = tk.Frame(edit_win, bg="#34495e")
    form_frame.pack(pady=10)

    # ตัวแปรสำหรับเก็บข้อมูลในช่องกรอก (Entries)
    var_prefix = tk.StringVar()
    var_fname = tk.StringVar()
    var_lname = tk.StringVar()
    var_email = tk.StringVar()
    var_faculty = tk.StringVar()
    var_branch = tk.StringVar()
    var_key = tk.StringVar()

    labels = ["คำนำหน้า", "ชื่อ", "นามสกุล", "อีเมล", "คณะ", "สาขา", "รหัสกุญแจ (Key)"]
    vars_list = [var_prefix, var_fname, var_lname, var_email, var_faculty, var_branch, var_key]

    for i, (text, var) in enumerate(zip(labels, vars_list)):
        tk.Label(form_frame, text=text+":", bg="#ecf0f1", font=("Arial", 11, "bold"), fg="#34495e").grid(row=i, column=0, sticky="e", pady=8, padx=10)
        tk.Entry(form_frame, textvariable=var, font=("Arial", 11), width=25).grid(row=i, column=1, pady=8, padx=10)

    # ฟังก์ชันเมื่อกดปุ่มค้นหา
    def perform_search():
        sid = entry_search.get().strip()
        if not sid:
            messagebox.showwarning("แจ้งเตือน", "กรุณากรอกรหัสนักศึกษา")
            return

        # ค้นหาข้อมูลจาก DB
        data = get_student_by_id(sid)
        if data:
            var_prefix.set(data.get("prefix", ""))
            var_fname.set(data.get("first_name", ""))
            var_lname.set(data.get("last_name", ""))
            var_email.set(data.get("email", ""))
            var_faculty.set(data.get("faculty", ""))
            var_branch.set(data.get("branch", ""))
            var_key.set(data.get(Config.FIELD_NAME, ""))

            btn_save.config(state="normal", bg="#27ae60", cursor="hand2")
            messagebox.showinfo("สำเร็จ", f"พบข้อมูลของ {sid}")
        else:
            messagebox.showinfo("ไม่พบข้อมูล", f"ไม่พบข้อมูลของรหัส นศ. {sid} ในระบบ")
            for v in vars_list: v.set("")
            btn_save.config(state="disabled", bg="#95a5a6", cursor="arrow")

    btn_search = tk.Button(search_frame, text="ค้นหา", font=("Arial", 10, "bold"), bg="#3498db", fg="white", command=perform_search)
    btn_search.grid(row=0, column=2, padx=5)

    # ฟังก์ชันเมื่อกดปุ่มบันทึก
    def perform_save():
        sid = entry_search.get().strip()
        if not sid: return

        update_data = {
            "prefix": var_prefix.get().strip(),
            "first_name": var_fname.get().strip(),
            "last_name": var_lname.get().strip(),
            "email": var_email.get().strip(),
            "faculty": var_faculty.get().strip(),
            "branch": var_branch.get().strip(),
            Config.FIELD_NAME: var_key.get().strip()
        }

        success = update_student_data(sid, update_data)
        if success:
            messagebox.showinfo("สำเร็จ", "อัปเดตข้อมูลเรียบร้อยแล้ว")
            edit_win.destroy()
        else:
            messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถอัปเดตข้อมูลได้")

    btn_save = tk.Button(edit_win, text="บันทึกการแก้ไข", font=("Arial", 12, "bold"), bg="#95a5a6", fg="white", state="disabled", command=perform_save)
    btn_save.pack(pady=20, fill=tk.X, padx=50)

def setup_admin_gui(root):
    """ฟังก์ชันสำหรับสร้างหน้าต่างผู้ดูแลระบบแยกออกมา"""
    admin_window = tk.Toplevel(root)
    admin_window.title("ระบบผู้ดูแล")
    admin_window.geometry("600x600")
    admin_window.configure(bg="#34495e")
    admin_window.resizable(False, False)

    lbl_admin = tk.Label(
        admin_window, text="จัดการระบบและข้อมูล", font=("Arial", 35, "bold"), fg="white", bg="#34495e"
    )
    lbl_admin.pack(pady=(20, 15))

    lbl_crud_hint = tk.Label(
        admin_window, text="แดชบอร์ด", font=("Arial", 15), fg="#bdc3c7", bg="#34495e"
    )
    lbl_crud_hint.pack(pady=(15, 0))

    btn_dashboard = tk.Button(
        admin_window,
        text="แสดงแดชบอร์ด",
        font=("Arial", 18, "bold"),
        bg="#3498db",
        fg="white",
        padx=10,
        pady=8,
        command=show_dashboard_graph,
    )
    btn_dashboard.pack(pady=10, fill=tk.X, padx=40)

    lbl_crud_hint = tk.Label(
        admin_window, text="นำเข้าข้อมูลผู้ใช้งาน CSV ไฟล์เท่านั้น", font=("Arial", 15), fg="#bdc3c7", bg="#34495e"
    )
    lbl_crud_hint.pack(pady=(15, 0))

    btn_import = tk.Button(
        admin_window,
        text="นำเข้าข้อมูลผู้ใช้งาน (CSV)",
        font=("Arial", 18, "bold"),
        bg="#27ae60",
        fg="white",
        padx=10,
        pady=8,
        command=import_csv_to_firebase,
    )
    btn_import.pack(pady=10, fill=tk.X, padx=40)

    lbl_crud_hint = tk.Label(
        admin_window, text="จัดการข้อมูลรายบุคคล", font=("Arial", 15), fg="#bdc3c7", bg="#34495e"
    )
    lbl_crud_hint.pack(pady=(15, 0))

    frame_crud = tk.Frame(admin_window, bg="#34495e")
    frame_crud.pack(pady=5, fill=tk.X, padx=40)

    # ผูกปุ่มแก้ไขให้เรียกใช้หน้าต่างค้นหา
    btn_edit = tk.Button(
        frame_crud,
        text="แก้ไขข้อมูล",
        font=("Arial", 18, "bold"),
        bg="#d35400",
        fg="white",
        padx=10,
        pady=8,
        command=lambda: open_edit_window(admin_window)
    )
    btn_edit.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

def setup_gui():
    """ฟังก์ชันสำหรับสร้างหน้าต่างหลัก (แสดงสถานะประตูอย่างเดียว)"""
    root = tk.Tk()
    root.title("หน้าจอแสดงสถานะประตู")
    root.geometry("600x600")
    root.configure(bg="#2c3e50")
    root.resizable(False, False)

    lbl_title = tk.Label(
        root, text="สถานะระบบ", font=("Arial", 35, "bold"), fg="white", bg="#2c3e50"
    )
    lbl_title.pack(pady=(50, 10))

    canvas = tk.Canvas(root, width=200, height=200, bg="#2c3e50", highlightthickness=0)
    canvas.pack(pady=50)

    light_circle = canvas.create_oval(
        10, 10, 190, 190, fill="#e74c3c", outline="#c0392b", width=5
    )

    lbl_status = tk.Label(
        root, text="LOCKED", font=("Arial", 25, "bold"), fg="#e74c3c", bg="#2c3e50"
    )
    lbl_status.pack(pady=(0, 5))

    lbl_action = tk.Label(
        root, text="", font=("Arial", 28, "bold"), fg="#f1c40f", bg="#2c3e50"
    )
    lbl_action.pack()

    lbl_user = tk.Label(
        root,
        text="",
        font=("Arial", 32),
        fg="white",
        bg="#2c3e50"
    )
    lbl_user.pack(pady=(0, 15))

    setup_admin_gui(root)

    def update_gui():
        if shared_state.gui_light_state == "green":
            canvas.itemconfig(light_circle, fill="#2ecc71", outline="#27ae60")
            lbl_status.config(text="ประตูเปิด", fg="#2ecc71")
            lbl_action.config(text=shared_state.gui_action_text)
            lbl_user.config(text=shared_state.gui_user_name)
        else:
            canvas.itemconfig(light_circle, fill="#e74c3c", outline="#c0392b")
            lbl_status.config(text="ประตูปิด", fg="#e74c3c")
            lbl_action.config(text="")
            lbl_user.config(text="")

        root.after(100, update_gui)

    update_gui()
    return root

if __name__ == "__main__":
    bg_thread = threading.Thread(target=run_background_scanner, daemon=True)
    bg_thread.start()

    gui_window = setup_gui()
    gui_window.mainloop()
