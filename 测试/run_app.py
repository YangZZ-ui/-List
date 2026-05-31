import sys
import os
import webbrowser
import threading
import time

def main():
    # 获取当前 exe 所在目录（PyInstaller 打包后 sys._MEIPASS 指向临时解压目录）
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    app_file = os.path.join(base_dir, "app.py")
    
    # 延迟自动打开浏览器
    def open_browser():
        time.sleep(2.5)
        webbrowser.open("http://localhost:8501")
    threading.Thread(target=open_browser, daemon=True).start()
    
    # 直接调用 Streamlit CLI（避免 subprocess 在打包后失效）
    sys.argv = [
        "streamlit",
        "run",
        app_file,
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.port=8501",
    ]
    
    try:
        from streamlit.web.cli import main as st_main
        st_main()
    except SystemExit:
        pass

if __name__ == "__main__":
    main()