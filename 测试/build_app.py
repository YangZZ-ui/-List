"""
一键打包脚本：将本项目打包为独立的 Windows 可执行文件（.exe）
无需目标电脑安装 Python，双击即可运行
"""

import os
import sys
import shutil
import subprocess


def ensure_pyinstaller():
    """确保 PyInstaller 已安装"""
    try:
        import PyInstaller
        return True
    except ImportError:
        print("PyInstaller 未安装，正在自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("PyInstaller 安装完成\n")
        return True


def generate_spec(base_dir, spec_path):
    """生成 PyInstaller .spec 文件"""
    from PyInstaller.utils.hooks import collect_all

    # 自动收集 streamlit 所有静态资源、二进制依赖与隐藏导入
    datas, binaries, hiddenimports = collect_all('streamlit')

    # 添加项目自有资源文件
    for name in ["config.py", "app.py"]:
        p = os.path.join(base_dir, name)
        if os.path.exists(p):
            datas.append((p, "."))

    for name in ["modules", "templates", "assets"]:
        p = os.path.join(base_dir, name)
        if os.path.exists(p):
            datas.append((p, name))

    # 补充审计分析相关的隐藏导入
    extra_hidden = [
        'pandas',
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs.np_datetime',
        'plotly',
        'plotly.express',
        'plotly.graph_objects',
        'plotly.subplots',
        'openpyxl',
        'docx',
        'docx.shared',
        'docx.enum.text',
        'scipy',
        'scipy.stats',
        'sqlalchemy',
        'markdown',
        'openai',
        'numpy',
        'PIL',
        'pyarrow',
    ]
    hiddenimports.extend(extra_hidden)

    # 格式化 datas 列表
    datas_lines = ",\n".join([f"            {repr(item)}" for item in datas])
    hidden_lines = ",\n".join([f"            {repr(item)}" for item in hiddenimports])

    run_app_path = os.path.join(base_dir, "run_app.py").replace("\\", "/")
    pathex = base_dir.replace("\\", "/")

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# 自动收集 streamlit 全部资源（前端静态文件、proto、组件等）
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all('streamlit')

# 项目自有资源
custom_datas = [
{datas_lines}
]

datas = streamlit_datas + custom_datas
binaries = streamlit_binaries
hiddenimports = streamlit_hiddenimports + [
{hidden_lines}
]

a = Analysis(
    [r'{run_app_path}'],
    pathex=[r'{pathex}'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='智能审计洞察平台',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)


def build():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    ensure_pyinstaller()

    # 清理旧构建产物
    for d in ["build", "dist"]:
        p = os.path.join(base_dir, d)
        if os.path.exists(p):
            print(f"清理旧目录: {p}")
            shutil.rmtree(p)

    spec_path = os.path.join(base_dir, "audit_app.spec")
    print("正在生成打包配置...")
    generate_spec(base_dir, spec_path)

    print("\n开始打包，预计需要 5-15 分钟（取决于电脑性能）...")
    print("期间请不要关闭窗口\n")

    try:
        subprocess.check_call([sys.executable, "-m", "PyInstaller", spec_path])
    except subprocess.CalledProcessError as e:
        print(f"\n打包过程出错：{e}")
        sys.exit(1)

    # 验证输出
    exe_name = "智能审计洞察平台.exe" if sys.platform == "win32" else "智能审计洞察平台"
    exe_path = os.path.join(base_dir, "dist", exe_name)

    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / 1024 / 1024
        print("\n" + "=" * 50)
        print("打包成功！")
        print("=" * 50)
        print(f"文件名称：{exe_name}")
        print(f"文件大小：{size_mb:.1f} MB")
        print(f"文件位置：{exe_path}")
        print("\n使用方式：")
        print(f"  1. 双击运行 {exe_name}")
        print("  2. 程序会自动在浏览器中打开 http://localhost:8501")
        print("  3. 无需安装 Python，可直接复制到其他电脑运行")
        print("\n提示：")
        print("  - 首次启动可能需要 10-30 秒解压资源，请耐心等待")
        print("  - 关闭程序请直接关闭命令行窗口")
        print("=" * 50)
    else:
        print("\n未找到生成的 exe 文件，请检查 dist/ 目录")


if __name__ == "__main__":
    build()
