import customtkinter as ctk
from tkinter import messagebox, Menu, filedialog
from tkinter import ttk
import os
import sys
import tempfile
import shutil
import subprocess
import threading
import webbrowser
import http.server
import socketserver
import platform
import json

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
IS_ANDROID = platform.system() == "Linux" and "aarch64" in platform.machine()
FILE_ENCODING = "utf-8"

# 语言配置，默认英语
LANG = "en"
LOCALE_PATH = os.path.join(os.path.dirname(__file__), "locales", f"{LANG}.json")
with open(LOCALE_PATH, "r", encoding="utf-8") as f:
    TEXT = json.load(f)


class PreviewWindow:
    def __init__(self, html_content):
        self.html_content = html_content
        self.temp_dir = None
        self.httpd = None
        self.port = 4444

    def show(self):
        self.temp_dir = tempfile.mkdtemp()
        index_path = os.path.join(self.temp_dir, "index.html")
        with open(index_path, "w", encoding=FILE_ENCODING) as f:
            f.write(self.html_content)
        os.chdir(self.temp_dir)
        handler = http.server.SimpleHTTPRequestHandler
        try:
            self.httpd = socketserver.TCPServer(("", self.port), handler)
        except OSError:
            messagebox.showerror(TEXT["error"], TEXT["cannot_bind_port"].format(port=self.port))
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            return
        server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        server_thread.start()
        url = f"http://localhost:{self.port}"
        try:
            webbrowser.open(url)
        except:
            messagebox.showinfo(TEXT["preview"], TEXT["preview_started"].format(url=url))
        messagebox.showinfo(TEXT["preview"], TEXT["preview_started"].format(url=url))
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class CodeEditor:
    def __init__(self):
        self.window = ctk.CTk()
        self.window.title(TEXT["app_title"])
        self.window.geometry("1200x700")
        self.current_file = None
        self.project_folder = os.path.expanduser("~/CloudCode")
        self._create_menu()
        self._create_widgets()
        self._bind_shortcuts()
        self._ensure_project_folder()
        self._refresh_file_tree()

    def _ensure_project_folder(self):
        if not os.path.exists(self.project_folder):
            os.makedirs(self.project_folder)
        default_index = os.path.join(self.project_folder, "index.html")
        if not os.path.exists(default_index):
            with open(default_index, "w", encoding=FILE_ENCODING) as f:
                f.write(self._get_default_html())
        if os.path.exists(default_index):
            with open(default_index, "r", encoding=FILE_ENCODING) as f:
                self.set_code(f.read())
            self.current_file = default_index
            self.status_bar.configure(text=f"{TEXT['ready']}: index.html")

    def _get_default_html(self):
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Hello World</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            margin-top: 100px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        h1 { font-size: 3em; }
        p { font-size: 1.2em; }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            margin-top: 20px;
            background: white;
            color: #764ba2;
            text-decoration: none;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <h1>🚀 Hello World</h1>
    <p>Welcome to CloudCode Editor!</p>
    <p>Supports Python/Java/C/C++/C#/Kotlin and more.</p>
    <a href="#" class="btn" onclick="alert('Hello from preview!')">Click Me</a>
</body>
</html>"""

    def _create_menu(self):
        menubar = Menu(self.window)
        self.window.config(menu=menubar)
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label=TEXT["file"], menu=file_menu)
        file_menu.add_command(label=TEXT["new_file"], command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label=TEXT["open_file"], command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label=TEXT["save"], command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label=TEXT["save_as"], command=self.save_as_file, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label=TEXT["exit"], command=self.window.quit)
        run_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label=TEXT["run"], menu=run_menu)
        run_menu.add_command(label=TEXT["preview"], command=self.local_preview)
        run_menu.add_command(label=TEXT["package_exe"], command=self.package_as_exe)
        run_menu.add_command(label=TEXT["package_apk"], command=self.package_as_apk)
        run_menu.add_command(label=TEXT["package_ipa"], command=self.package_as_ipa)

    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        left_frame = ctk.CTkFrame(main_frame, width=250)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        ctk.CTkLabel(left_frame, text=f"📁 {TEXT['file_tree_title']}", font=ctk.CTkFont(size=14)).pack(pady=10)
        tree_frame = ctk.CTkFrame(left_frame)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.file_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.file_tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_select)
        self.file_tree.bind("<Button-3>", self.show_context_menu)
        btn_frame = ctk.CTkFrame(left_frame)
        btn_frame.pack(fill="x", pady=5)
        new_btn = ctk.CTkButton(btn_frame, text=TEXT["new_file"], command=self.new_file, width=80)
        new_btn.pack(side="left", padx=5)
        refresh_btn = ctk.CTkButton(btn_frame, text=TEXT["refresh"], command=self._refresh_file_tree, width=80)
        refresh_btn.pack(side="right", padx=5)
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)
        self.editor = ctk.CTkTextbox(right_frame, font=("Consolas", 14), wrap="none")
        self.editor.pack(fill="both", expand=True)
        bottom_frame = ctk.CTkFrame(right_frame, height=40)
        bottom_frame.pack(fill="x", pady=(5, 0))
        self.status_bar = ctk.CTkLabel(bottom_frame, text=TEXT["ready"], anchor="w")
        self.status_bar.pack(side="left", padx=10)

    def _bind_shortcuts(self):
        self.window.bind("<Control-n>", lambda e: self.new_file())
        self.window.bind("<Control-o>", lambda e: self.open_file())
        self.window.bind("<Control-s>", lambda e: self.save_file())
        self.window.bind("<Control-Shift-S>", lambda e: self.save_as_file())

    def _refresh_file_tree(self):
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        self._add_folder_to_tree(self.project_folder, "")

    def _add_folder_to_tree(self, folder, parent):
        try:
            for item in sorted(os.listdir(folder)):
                full_path = os.path.join(folder, item)
                if os.path.isdir(full_path):
                    node = self.file_tree.insert(parent, "end", text=item, open=False, tags=("folder",))
                    self._add_folder_to_tree(full_path, node)
                elif item.endswith((".html", ".htm", ".py", ".java", ".c", ".cpp", ".h", ".cs", ".kt", ".txt", ".js", ".css")):
                    self.file_tree.insert(parent, "end", text=item, tags=("file",), values=(full_path,))
        except PermissionError:
            pass

    def on_file_select(self, event):
        selection = self.file_tree.selection()
        if not selection:
            return
        item = selection[0]
        if self.file_tree.tag_has("file", item):
            file_path = self.file_tree.item(item, "values")[0]
            try:
                with open(file_path, "r", encoding=FILE_ENCODING) as f:
                    self.set_code(f.read())
                self.current_file = file_path
                self.status_bar.configure(text=f"{TEXT['ready']}: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror(TEXT["error"], TEXT["open_failed"].format(msg=e))

    def show_context_menu(self, event):
        item = self.file_tree.identify_row(event.y)
        if not item:
            return
        self.file_tree.selection_set(item)
        menu = Menu(self.window, tearoff=0)
        menu.add_command(label=TEXT["rename"], command=self.rename_file)
        menu.add_command(label=TEXT["delete"], command=self.delete_file)
        menu.post(event.x_root, event.y_root)

    def rename_file(self):
        selection = self.file_tree.selection()
        if not selection:
            return
        item = selection[0]
        if self.file_tree.tag_has("file", item):
            old_path = self.file_tree.item(item, "values")[0]
            new_name = filedialog.asksaveasfilename(initialdir=os.path.dirname(old_path), title=TEXT["rename"], defaultextension="")
            if new_name:
                try:
                    os.rename(old_path, new_name)
                    self._refresh_file_tree()
                    if self.current_file == old_path:
                        self.current_file = new_name
                    self.status_bar.configure(text=f"{TEXT['ready']}: {os.path.basename(new_name)}")
                except Exception as e:
                    messagebox.showerror(TEXT["error"], TEXT["rename_failed"].format(msg=e))

    def delete_file(self):
        selection = self.file_tree.selection()
        if not selection:
            return
        item = selection[0]
        if self.file_tree.tag_has("file", item):
            file_path = self.file_tree.item(item, "values")[0]
            if messagebox.askyesno(TEXT["delete"], TEXT["confirm_delete"].format(filename=os.path.basename(file_path))):
                try:
                    os.remove(file_path)
                    self._refresh_file_tree()
                    if self.current_file == file_path:
                        self.current_file = None
                        self.set_code("")
                        self.status_bar.configure(text=TEXT["file_deleted"])
                except Exception as e:
                    messagebox.showerror(TEXT["error"], TEXT["delete_failed"].format(msg=e))

    def get_code(self):
        return self.editor.get("0.0", "end-1c")

    def set_code(self, code):
        self.editor.delete("0.0", "end")
        self.editor.insert("0.0", code)

    def new_file(self):
        file_name = filedialog.asksaveasfilename(initialdir=self.project_folder, title=TEXT["new_file"], defaultextension=".txt", filetypes=[
            ("All Supported", "*.html;*.htm;*.py;*.java;*.c;*.cpp;*.cs;*.kt;*.txt;*.js;*.css"),
            ("HTML", "*.html"), ("Python", "*.py"), ("Java", "*.java"),
            ("C", "*.c"), ("C++", "*.cpp"), ("C#", "*.cs"), ("Kotlin", "*.kt"),
            ("Text", "*.txt")
        ])
        if file_name:
            try:
                with open(file_name, "w", encoding=FILE_ENCODING) as f:
                    f.write("")
                self._refresh_file_tree()
                self.current_file = file_name
                self.set_code("")
                self.status_bar.configure(text=f"{TEXT['ready']}: {os.path.basename(file_name)}")
            except Exception as e:
                messagebox.showerror(TEXT["error"], TEXT["new_failed"].format(msg=e))

    def open_file(self):
        file_path = filedialog.askopenfilename(initialdir=self.project_folder, title=TEXT["open_file"], filetypes=[
            ("All Supported", "*.html;*.htm;*.py;*.java;*.c;*.cpp;*.cs;*.kt;*.txt;*.js;*.css"),
            ("HTML", "*.html"), ("Python", "*.py"), ("Java", "*.java"),
            ("C", "*.c"), ("C++", "*.cpp"), ("C#", "*.cs"), ("Kotlin", "*.kt"),
            ("Text", "*.txt")
        ])
        if file_path:
            try:
                with open(file_path, "r", encoding=FILE_ENCODING) as f:
                    self.set_code(f.read())
                self.current_file = file_path
                self.status_bar.configure(text=f"{TEXT['ready']}: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror(TEXT["error"], TEXT["open_failed"].format(msg=e))

    def save_file(self):
        if self.current_file:
            try:
                with open(self.current_file, "w", encoding=FILE_ENCODING) as f:
                    f.write(self.get_code())
                self.status_bar.configure(text=f"{TEXT['ready']}: {os.path.basename(self.current_file)}")
            except Exception as e:
                messagebox.showerror(TEXT["error"], TEXT["save_failed"].format(msg=e))
        else:
            self.save_as_file()

    def save_as_file(self):
        file_path = filedialog.asksaveasfilename(initialdir=self.project_folder, title=TEXT["save_as"], defaultextension=".txt", filetypes=[
            ("All Supported", "*.html;*.htm;*.py;*.java;*.c;*.cpp;*.cs;*.kt;*.txt;*.js;*.css"),
            ("HTML", "*.html"), ("Python", "*.py"), ("Java", "*.java"),
            ("C", "*.c"), ("C++", "*.cpp"), ("C#", "*.cs"), ("Kotlin", "*.kt"),
            ("Text", "*.txt")
        ])
        if file_path:
            try:
                with open(file_path, "w", encoding=FILE_ENCODING) as f:
                    f.write(self.get_code())
                self.current_file = file_path
                self._refresh_file_tree()
                self.status_bar.configure(text=f"{TEXT['ready']}: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror(TEXT["error"], TEXT["save_failed"].format(msg=e))

    def local_preview(self):
        if not self.current_file or not self.current_file.endswith((".html", ".htm")):
            messagebox.showerror(TEXT["error"], TEXT["html_only_preview"])
            return
        code = self.get_code()
        if not code.strip():
            messagebox.showerror(TEXT["error"], TEXT["empty_file_preview"])
            return
        PreviewWindow(code).show()

    def package_as_exe(self):
        if not self.current_file:
            messagebox.showerror(TEXT["error"], TEXT["save_first"])
            return
        try:
            subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            messagebox.showerror(TEXT["error"], TEXT["pyinstaller_not_installed"])
            return
        if self.current_file.endswith(".py"):
            cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole", self.current_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                messagebox.showinfo(TEXT["package_exe"], TEXT["build_success"])
            else:
                messagebox.showerror(TEXT["error"], TEXT["build_failed"].format(msg=result.stderr))
        else:
            temp_py = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding=FILE_ENCODING)
            code_content = self.get_code().replace("'''", "\\'''")
            temp_py.write(f"""
import sys, os, webbrowser, tempfile, threading, http.server, socketserver
html_content = r'''{code_content}'''
def run_server():
    temp_dir = tempfile.mkdtemp()
    index_path = os.path.join(temp_dir, "index.html")
    with open(index_path, "w", encoding="{FILE_ENCODING}") as f:
        f.write(html_content)
    os.chdir(temp_dir)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", 0), handler) as httpd:
        port = httpd.server_address[1]
        webbrowser.open(f"http://localhost:{{port}}")
        httpd.serve_forever()
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    input("Press Enter to exit...\n")
""")
            temp_py.close()
            cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole", temp_py.name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            os.unlink(temp_py.name)
            if result.returncode == 0:
                messagebox.showinfo(TEXT["package_exe"], TEXT["build_success"])
            else:
                messagebox.showerror(TEXT["error"], TEXT["build_failed"].format(msg=result.stderr))

    def package_as_apk(self):
        messagebox.showinfo(TEXT["package_apk"], TEXT["apk_guide"])

    def package_as_ipa(self):
        messagebox.showinfo(TEXT["package_ipa"], TEXT["ipa_guide"])

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = CodeEditor()
    app.run()
