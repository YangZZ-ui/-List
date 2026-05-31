"""
打包前预检查脚本
检查 Python 环境、依赖完整性、关键文件齐全性、磁盘空间等
在真正执行 PyInstaller 前发现潜在问题，避免打包中途失败
"""

import sys
import os
import importlib.util
import shutil

REQUIRED_FILES = [
    "run_app.py",
    "app.py",
    "config.py",
    "requirements.txt",
]

REQUIRED_DIRS = [
    "modules",
    "templates",
    "assets",
]

REQUIRED_PACKAGES = [
    ("streamlit", "Streamlit 主框架"),
    ("pandas", "数据处理"),
    ("plotly", "可视化图表"),
    ("openpyxl", "Excel 读写"),
    ("docx", "Word 报告生成"),
    ("scipy", "统计计算"),
    ("sqlalchemy", "数据库连接"),
    ("markdown", "Markdown 转 HTML"),
    ("openai", "AI 大模型调用（可选，但建议安装）"),
    ("numpy", "数值计算"),
    ("PIL", "图像处理（Pillow）"),
    ("pyarrow", "Arrow 数据格式（pandas 依赖）"),
]


def check_python_version():
    """检查 Python 版本 >= 3.9"""
    version = sys.version_info
    if version < (3, 9):
        return False, f"Python 版本过低：{version.major}.{version.minor}.{version.micro}，需要 >= 3.9"
    return True, f"Python 版本：{version.major}.{version.minor}.{version.micro} ✅"


def check_project_files(project_root):
    """检查关键文件和目录是否存在"""
    errors = []
    for f in REQUIRED_FILES:
        path = os.path.join(project_root, f)
        if not os.path.exists(path):
            errors.append(f"缺少关键文件：{f}")
    for d in REQUIRED_DIRS:
        path = os.path.join(project_root, d)
        if not os.path.exists(path):
            errors.append(f"缺少关键目录：{d}")
    if errors:
        return False, errors
    return True, [f"所有关键文件和目录齐全（{len(REQUIRED_FILES)} 个文件 + {len(REQUIRED_DIRS)} 个目录）✅"]


def check_dependencies():
    """检查 Python 包是否已安装"""
    missing = []
    installed = []
    for pkg, desc in REQUIRED_PACKAGES:
        spec = importlib.util.find_spec(pkg)
        if spec is None:
            missing.append(f"{pkg}（{desc}）")
        else:
            installed.append(pkg)
    if missing:
        return False, missing, installed
    return True, [], installed


def check_pyinstaller():
    """检查 PyInstaller 是否已安装"""
    spec = importlib.util.find_spec("PyInstaller")
    if spec is None:
        return False, "PyInstaller 未安装"
    return True, "PyInstaller 已安装 ✅"


def check_disk_space():
    """检查磁盘空间（临时目录至少 2GB）"""
    temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))
    try:
        free = shutil.disk_usage(temp_dir).free
        free_gb = free / (1024 ** 3)
        if free_gb < 2:
            return False, f"临时目录剩余空间仅 {free_gb:.1f} GB，建议至少 2GB 以上"
        return True, f"磁盘空间充足：临时目录剩余 {free_gb:.1f} GB ✅"
    except Exception as e:
        return False, f"无法检测磁盘空间：{e}"


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("智能审计洞察平台 - 打包前预检查")
    print("=" * 60)
    print(f"项目根目录：{project_root}\n")

    all_pass = True
    results = []

    # 1. Python 版本
    ok, msg = check_python_version()
    results.append(("Python 版本", ok, msg))
    if not ok:
        all_pass = False

    # 2. 项目文件完整性
    ok, msgs = check_project_files(project_root)
    if isinstance(msgs, list) and len(msgs) > 0 and isinstance(msgs[0], str) and msgs[0].endswith("✅"):
        results.append(("项目文件完整性", ok, msgs[0]))
    else:
        for m in msgs:
            results.append(("项目文件完整性", False, m))
        all_pass = False

    # 3. Python 依赖
    ok, missing, installed = check_dependencies()
    if ok:
        results.append(("Python 依赖", True, f"所有 {len(installed)} 个依赖包已安装 ✅"))
    else:
        for m in missing:
            results.append(("Python 依赖", False, f"缺少：{m}"))
        all_pass = False

    # 4. PyInstaller
    ok, msg = check_pyinstaller()
    results.append(("PyInstaller", ok, msg))
    if not ok:
        all_pass = False

    # 5. 磁盘空间
    ok, msg = check_disk_space()
    results.append(("磁盘空间", ok, msg))
    if not ok:
        all_pass = False

    # 输出结果
    print()
    for name, ok, msg in results:
        status = "✅" if ok else "❌"
        print(f"  {status} {name}: {msg}")

    print()
    if all_pass:
        print("=" * 60)
        print("预检查全部通过，可以开始打包！")
        print("=" * 60)
        return 0
    else:
        print("=" * 60)
        print("预检查未通过，请修复上述问题后再打包")
        print()
        print("快速修复命令：")
        print(f"  cd \"{project_root}\"")
        print("  pip install -r requirements.txt")
        if any(r[0] == "PyInstaller" and not r[1] for r in results):
            print("  pip install pyinstaller")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
