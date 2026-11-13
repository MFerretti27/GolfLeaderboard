"""Main file to run."""
import os
import platform
import subprocess
import sys
import traceback
import venv
from pathlib import Path


def create_virtualenv(venv_dir: str) -> None:
    """Create a virtual environment in the specified directory.

    :param venv_dir: virtual environment directory name
    """
    try:
        if not Path(venv_dir).exists():
            print(f"Creating virtual environment in {venv_dir}...")
            venv.create(venv_dir, with_pip=True)
        else:
            print(f"Virtual environment already exists in {venv_dir}.")
    except (OSError, subprocess.SubprocessError):
        print(f"Failed to create virtual environment in {venv_dir}", file=sys.stderr)
        traceback.print_exc()
        print("Please ensure you have sufficient disk space and permissions.")
        sys.exit(1)


def install_requirements(venv_dir: str, requirements_file: str) -> None:
    """Installs dependencies from a requirements.txt file.

    :param venv_dir: virtual environment directory name
    :param requirements_file: file name to install requirements from
    """
    if not Path(requirements_file).exists():
        print(f"No requirements file found at {requirements_file}. Script cannot run.")
        sys.exit(1)

    print(f"Installing dependencies from {requirements_file}...")

    pip_executable = (Path(venv_dir) / "Scripts" / "pip.exe") \
        if platform.system() == "Windows" else (Path(venv_dir) / "bin" / "pip")

    if not Path(pip_executable).exists():
        print(f"Error: pip executable not found at {pip_executable}")
        sys.exit(1)

    try:
        subprocess.check_call([pip_executable, "install", "-r", requirements_file])
    except subprocess.CalledProcessError:
        print(f"Failed to install dependencies from {requirements_file}", file=sys.stderr)
        traceback.print_exc()
        print("Please check your internet connection and requirements.txt file.")
        sys.exit(1)
    except FileNotFoundError:
        print(f"pip executable not found or permissions denied at {pip_executable}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


def run_program_in_venv(
    venv_dir: Path,
    program_script: str,
    program_args: list[str] | None = None,
    working_dir: Path | None = None,
) -> None:
    """Run a Python program inside the virtual environment.

    :param venv_dir: virtual environment directory name
    :param program_script: python module to execute in subprocess
    """
    python_executable = (venv_dir / "Scripts" / "python.exe") \
        if platform.system() == "Windows" else (venv_dir / "bin" / "python")

    if not Path(python_executable).exists():
        print(f"Error: Python executable not found at {python_executable}")
        sys.exit(1)

    # Run the program
    print(f"Running program {program_script} inside virtual environment...")
    try:
        subprocess.call(
            [str(python_executable), "-m", program_script, *(program_args or [])],
            cwd=working_dir,
        )
    except OSError:
        print(f"Failed to run program {program_script}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


def set_screen() -> None:
    """Set the screen for the program to run on."""
    if sys.prefix == sys.base_prefix:
        print("Please activate the virtual environment before running.")
        sys.exit(1)

    if platform.system() != "Windows" and os.environ.get("DISPLAY", "") == "":
        print("No display found. Using :0.0")
        os.environ["DISPLAY"] = ":0.0"


def remove_ds_files() -> None:
    """Remove all .DS_Store files (only needed on macOS)."""
    if platform.system() == "Darwin":
        print("Removing .DS_Store files...")
        try:
            # Walk through the directory and remove .DS_Store files
            for root, _, files in os.walk("."):
                for file in files:
                    if file == ".DS_Store":
                        path = Path(root) / file
                        try:
                            print(f"Removing: {path}")
                            path.unlink()
                        except OSError:
                            print(f"Failed to remove .DS_Store file: {path}", file=sys.stderr)
                            traceback.print_exc()
        except OSError:
            print("Error walking directory during .DS_Store removal", file=sys.stderr)
            traceback.print_exc()


def main() -> None:
    """Create virtual environment, download dependencies, and run script."""
    repo_root = Path(__file__).resolve().parent
    venv_dir = repo_root / "venv"
    requirements_file = repo_root / "requirements.txt"
    program_script = "golf_live_gui"

    create_virtualenv(str(venv_dir))
    install_requirements(str(venv_dir), str(requirements_file))
    run_program_in_venv(venv_dir, program_script, sys.argv[1:], repo_root)


if __name__ == "__main__":
    main()
