# main.py
import tkinter as tk
import threading

import shared_state
from ble_scanner import run_background_scanner
from dashboard import show_dashboard_graph
from db_manager import import_csv_to_firebase

def setup_gui():
    root = tk.Tk()
    root.title("BLE Access Control")
    root.geometry("600x600")
    root.configure(bg="#2c3e50")
    root.resizable(False, False)

    lbl_title = tk.Label(root, text="System Status", font=("Arial", 20, "bold"), fg="white", bg="#2c3e50")
    lbl_title.pack(pady=(30, 5))

    canvas = tk.Canvas(root, width=200, height=200, bg="#2c3e50", highlightthickness=0)
    canvas.pack(pady=10)

    light_circle = canvas.create_oval(10, 10, 190, 190, fill="#e74c3c", outline="#c0392b", width=5)

    lbl_status = tk.Label(root, text="LOCKED", font=("Arial", 24, "bold"), fg="#e74c3c", bg="#2c3e50")
    lbl_status.pack(pady=(0, 5))

    lbl_action = tk.Label(root, text="", font=("Arial", 16, "bold"), fg="#f1c40f", bg="#2c3e50")
    lbl_action.pack()

    lbl_user = tk.Label(root, text="", font=("Arial", 14), fg="white", bg="#2c3e50")
    lbl_user.pack(pady=(0, 15))

    btn_dashboard = tk.Button(
        root,
        text="📈 แดชบอร์ดสถิติ (Web/HTML)",
        font=("Arial", 12, "bold"),
        bg="#e67e22",
        fg="white",
        padx=10,
        pady=5,
        command=show_dashboard_graph
    )
    btn_dashboard.pack(pady=10)

    btn_import = tk.Button(
        root,
        text="📂 นำเข้าข้อมูลผู้ใช้งาน (CSV)",
        font=("Arial", 12, "bold"),
        bg="#3498db",
        fg="white",
        padx=10,
        pady=5,
        command=import_csv_to_firebase
    )
    btn_import.pack(pady=5)

    def update_gui():
        if shared_state.gui_light_state == "green":
            canvas.itemconfig(light_circle, fill="#2ecc71", outline="#27ae60")
            lbl_status.config(text="ACCESS GRANTED", fg="#2ecc71")
            lbl_action.config(text=shared_state.gui_action_text)
            lbl_user.config(text=shared_state.gui_user_name)
        else:
            canvas.itemconfig(light_circle, fill="#e74c3c", outline="#c0392b")
            lbl_status.config(text="LOCKED", fg="#e74c3c")
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
