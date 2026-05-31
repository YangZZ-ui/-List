"""
最终打包脚本
1. 先运行预检查
2. 将必要文件复制到 staging 干净目录
3. 生成 PyInstaller spec 并执行打包
4. 产物输出到 packaging/dist/
"""

import os
import sys
import shutil
import subprocess


def run_pre_check():
    """运行预检查"""
    pre_check_path = os.path.join(os.path.dirname(__file__), "pre_check.py")
    print("正在执行打包前预检查...\n")
    result = subprocess.run([sys.executable, pre_check_path])
    if result.returncode != 0:
        print("\n预检查未通过，打包已中止。请修复问题后重试。\n")
        sys.exit(1)
    print()


def copy_to_staging(project_root, staging_dir):
    """复制必要文件到 staging 目录"""
    if os.path.exists(staging_dir):
        print(f"清理旧 staging 目录: {staging_dir}")
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir, exist_ok=True)

    files_to_copy = ["run_app.py", "app.py", "config.py", "requirements.txt"]
    for f in files_to_copy:
        src = os.path.join(project_root, f)
        dst = os.path.join(staging_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  复制文件: {f}")
        else:
            print(f"  ⚠️ 文件不存在，跳过: {f}")

    dirs_to_copy = ["modules", "templates", "assets"]
    for d in dirs_to_copy:
        src = os.path.join(project_root, d)
        dst = os.path.join(staging_dir, d)
        if os.path.exists(src):
            shutil.copytree(src, dst)
            print(f"  复制目录: {d}/")
        else:
            print(f"  ⚠️ 目录不存在，跳过: {d}")

    print(f"\n文件已准备到: {staging_dir}\n")


def generate_spec(staging_dir, spec_path):
    """生成 PyInstaller spec 文件"""
    from PyInstaller.utils.hooks import collect_all

    # 自动收集 streamlit 所有资源
    datas, binaries, hiddenimports = collect_all('streamlit')

    # 添加 staging 中的资源
    for name in ["modules", "templates", "assets"]:
        p = os.path.join(staging_dir, name)
        if os.path.exists(p):
            datas.append((p, name))

    # 补充隐藏导入
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

    # 格式化列表
    datas_lines = ",\n".join([f"            {repr(item)}" for item in datas])
    hidden_lines = ",\n".join([f"            {repr(item)}" for item in hiddenimports])

    run_app_path = os.path.join(staging_dir, "run_app.py").replace("\\", "/")
    pathex = staging_dir.replace("\\", "/")

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

    print(f"已生成打包配置: {spec_path}\n")


def run_pyinstaller(staging_dir, spec_path):
    """执行 PyInstaller 打包"""
    print("开始执行 PyInstaller 打包...")
    print("（此过程通常需要 5-15 分钟，请耐心等待）\n")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "PyInstaller", spec_path],
            cwd=staging_dir,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ PyInstaller 打包失败：{e}")
        return False


def collect_output(staging_dir, dist_dir):
    """收集打包产物到 packaging/dist/"""
    exe_name = "智能审计洞察平台.exe" if sys.platform == "win32" else "智能审计洞察平台"
    src_exe = os.path.join(staging_dir, "dist", exe_name)

    if not os.path.exists(src_exe):
        print(f"\n❌ 未找到生成的 exe 文件：{src_exe}")
        return False

    os.makedirs(dist_dir, exist_ok=True)
    dst_exe = os.path.join(dist_dir, exe_name)

    # 如果已存在，先删除
    if os.path.exists(dst_exe):
        os.remove(dst_exe)

    shutil.copy2(src_exe, dst_exe)
    size_mb = os.path.getsize(dst_exe) / 1024 / 1024

    print("\n" + "=" * 60)
    print("🎉 打包成功！")
    print("=" * 60)
    print(f"文件名称：{exe_name}")
    print(f"文件大小：{size_mb:.1f} MB")
    print(f"输出位置：{dst_exe}")
    print()
    print("使用方式：")
    print(f"  1. 双击运行 {exe_name}")
    print("  2. 程序会自动打开浏览器访问 http://localhost:8501")
    print("  3. 无需安装 Python，可直接复制到其他 Windows 电脑运行")
    print()
    print("提示：")
    print("  - 首次启动可能需要 10-30 秒解压资源，请耐心等待")
    print("  - 关闭程序请直接关闭命令行窗口")
    print("=" * 60)
    return True


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    packaging_dir = os.path.dirname(os.path.abspath(__file__))
    staging_dir = os.path.join(packaging_dir, "staging")
    dist_dir = os.path.join(packaging_dir, "dist")

    print("=" * 60)
    print("智能审计洞察平台 - 最终打包脚本")
    print("=" * 60)
    print(f"项目根目录：{project_root}")
    print(f"打包工作区：{packaging_dir}\n")

    # 1. 预检查
    run_pre_check()

    # 2. 准备 staging
    copy_to_staging(project_root, staging_dir)

    # 3. 生成 spec
    spec_path = os.path.join(staging_dir, "audit_app.spec")
    generate_spec(staging_dir, spec_path)

    # 4. 执行打包
    ok = run_pyinstaller(staging_dir, spec_path)
    if not ok:
        sys.exit(1)

    # 5. 收集产物
    ok = collect_output(staging_dir, dist_dir)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
