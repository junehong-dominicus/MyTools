import subprocess
import sys
import os
import shutil


def build_exe():
    print("--- Starting MultiTerminal Build ---")

    # Operate from the script's own directory so the spec, 'dist', and 'exe'
    # resolve correctly no matter where (or how, e.g. `uv run`) this is launched.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Working dir: {script_dir}")

    # Check for PyInstaller
    try:
        import PyInstaller
        print(f"Found PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("Error: PyInstaller not found. Please run 'pip install pyinstaller'")
        return

    # Check for SPEC file
    spec_file = "MultiTerminal.spec"
    if not os.path.exists(spec_file):
        print(f"Error: {spec_file} not found in the current directory.")
        return

    # Run PyInstaller
    cmd = [sys.executable, "-m", "PyInstaller", spec_file, "--noconfirm"]
    print(f"Executing: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        print("\n" + "="*40)
        print("Success! Standalone app is in the 'dist' folder.")
        print("="*40)

        # Copy to local exe/ folder
        app_name = "MultiTerminal.app"
        src_path = os.path.join('dist', app_name)
        dest_folder = 'exe'
        dest_path = os.path.join(dest_folder, app_name)

        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        if os.path.exists(src_path):
            print(f"Copying {app_name} to {dest_folder}...")
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            print("Copy complete.")
        else:
            print(f"Error: {src_path} not found.")

    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with exit code: {e.returncode}")


if __name__ == "__main__":
    build_exe()
