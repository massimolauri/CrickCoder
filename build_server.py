import subprocess
import os
import shutil
import sys
import venv

BUILD_ENV_DIR = "build_venv"
REQUIREMENTS_FILE = "requirements.txt"
SPEC_FILE = "server.spec"

def run_in_venv(args, cwd=None):
    """Runs a command inside the virtual environment."""
    if sys.platform == "win32":
        python_exe = os.path.join(BUILD_ENV_DIR, "Scripts", "python.exe")
        pip_exe = os.path.join(BUILD_ENV_DIR, "Scripts", "pip.exe")
    else:
        python_exe = os.path.join(BUILD_ENV_DIR, "bin", "python")
        pip_exe = os.path.join(BUILD_ENV_DIR, "bin", "pip")

    # If the command is 'python' or 'pip', replace with full path
    if args[0] == "python":
        args[0] = python_exe
    elif args[0] == "pip":
        args[0] = pip_exe
    elif args[0] == "pyinstaller":
        # Pyinstaller script is in Scripts/bin
        if sys.platform == "win32":
            args[0] = os.path.join(BUILD_ENV_DIR, "Scripts", "pyinstaller.exe")
        else:
            args[0] = os.path.join(BUILD_ENV_DIR, "bin", "pyinstaller")

    print(f"🔹 Executing in venv: {' '.join(args)}")
    subprocess.check_call(args, cwd=cwd)

def main():
    print("🚀 Starting CLEAN Build Process...")

    # 1. Create Venv
    if not os.path.exists(BUILD_ENV_DIR):
        print(f"📦 Creating virtual environment: {BUILD_ENV_DIR}...")
        venv.create(BUILD_ENV_DIR, with_pip=True)
    else:
        print(f"📦 Virtual environment {BUILD_ENV_DIR} exists.")

    # 2. Install Dependencies
    print("⬇️  Installing/Updating dependencies from requirements_build.txt...")
    # Upgrade pip first
    run_in_venv(["python", "-m", "pip", "install", "--upgrade", "pip"])
    run_in_venv(["pip", "install", "-r", REQUIREMENTS_FILE])
    
    # Ensure PyInstaller is installed (it's in requirements, but double check)
    run_in_venv(["pip", "install", "pyinstaller"])

    # 3. Clean Checks
    if os.path.exists("server-dist"):
        shutil.rmtree("server-dist")
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    # 4. Patch PyInstaller (Workaround for bytecode scan errors)
    print("🩹 Patching PyInstaller to ignore IndexError in bytecode scan...")
    patch_pyinstaller()

    # 5. Run PyInstaller
    print("🔨 Running PyInstaller...")
    # We use the existing server.spec
    if not os.path.exists(SPEC_FILE):
        print(f"❌ Error: {SPEC_FILE} not found!")
        sys.exit(1)

    run_in_venv(["pyinstaller", "--noconfirm", "--clean", "--distpath", "server-dist", SPEC_FILE])

    print("\n✅ CLEAN BUILD COMPLETED!")
    print(f"📁 Output: server-dist/server/")

def patch_pyinstaller():
    """Patches modulegraph/util.py to ignore IndexError during bytecode scanning."""
    # Locate site-packages
    if sys.platform == "win32":
        site_packages = os.path.join(BUILD_ENV_DIR, "Lib", "site-packages")
    else:
        site_packages = os.path.join(BUILD_ENV_DIR, "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages")
    
    util_path = os.path.join(site_packages, "PyInstaller", "lib", "modulegraph", "util.py")
    
    if not os.path.exists(util_path):
        print(f"⚠️ Could not find util.py at {util_path}. Patching skipped.")
        return

    with open(util_path, "r") as f:
        content = f.read()

    # The line to patch
    target = '    yield from (i for i in dis.get_instructions(code_object) if i.opname != "EXTENDED_ARG")'
    replacement = "    try:\n        yield from (i for i in dis.get_instructions(code_object) if i.opname != 'EXTENDED_ARG')\n    except IndexError:\n        pass"

    if target in content:
        new_content = content.replace(target, replacement)
        with open(util_path, "w") as f:
            f.write(new_content)
        print("✅ PyInstaller patched successfully.")
    else:
        print("⚠️ Target line not found in util.py. Maybe version differs? Patching skipped.")


if __name__ == "__main__":
    main()
