# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 13:34:28
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 15:51:14
import os
import shlex
import shutil
import argparse
import platform
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "dist"
APP_DIST_DIR = DIST_DIR / "vector-vein"
FRONTEND_DIR = BASE_DIR.parent / "frontend"
WEB_DIR = BASE_DIR / "web"
MIGRATIONS_DIR = BASE_DIR / "migrations"


def run_cmd(cmd: str | list[str], cwd: Path | None = None):
    """
    Run command in a specific working directory and fail fast on errors.
    """
    if isinstance(cmd, str):
        cmd_args = shlex.split(cmd)
    else:
        cmd_args = cmd

    print(f"$ {' '.join(shlex.quote(part) for part in cmd_args)}")
    return subprocess.run(cmd_args, cwd=str(cwd or BASE_DIR), check=True)


def build_production(version):
    run_cmd(["pyinstaller", "main.spec", "--noconfirm"])
    # Create a version file in ./dist/vector-vein/
    version_txt_path = APP_DIST_DIR / "version.txt"
    if not version_txt_path.parent.exists():
        version_txt_path.parent.mkdir(parents=True, exist_ok=True)
    with version_txt_path.open("w", encoding="utf-8") as f:
        f.write(version)

    # Copy migrations to dist/vector-vein/migrations
    if MIGRATIONS_DIR.exists():
        dist_migrations_path = APP_DIST_DIR / "migrations"
        if dist_migrations_path.exists():
            shutil.rmtree(dist_migrations_path)
        shutil.copytree(MIGRATIONS_DIR, dist_migrations_path)

    system_name = platform.system().lower()
    if system_name == "darwin":
        platform_name = "mac"
    elif system_name == "windows":
        platform_name = "windows"
    else:
        platform_name = "linux"

    # Create the ZIP file
    zip_filename = f"vector-vein-{platform_name}-v{version}.zip"
    zip_filepath = DIST_DIR / zip_filename

    # Compress the directory
    shutil.make_archive(base_name=str(zip_filepath.with_suffix("")), format="zip", root_dir=DIST_DIR, base_dir="vector-vein")

    print(f"Created {zip_filename} at {zip_filepath}")


def build_development(version):
    run_cmd(["pyinstaller", "debug.spec", "--noconfirm"])
    # Create a version file in ./dist/vector-vein/
    version_txt_path = APP_DIST_DIR / "version.txt"
    if not version_txt_path.parent.exists():
        version_txt_path.parent.mkdir(parents=True, exist_ok=True)
    with version_txt_path.open("w", encoding="utf-8") as f:
        f.write(version)
    with (APP_DIST_DIR / "DEBUG").open("w", encoding="utf-8") as f:
        f.write("1")

    # Copy migrations to dist/vector-vein/migrations
    if MIGRATIONS_DIR.exists():
        dist_migrations_path = APP_DIST_DIR / "migrations"
        if dist_migrations_path.exists():
            shutil.rmtree(dist_migrations_path)
        shutil.copytree(MIGRATIONS_DIR, dist_migrations_path)


def build_frontend():
    run_cmd(["pnpm", "run", "build"], cwd=FRONTEND_DIR)

    if WEB_DIR.exists():
        shutil.rmtree(WEB_DIR)
    WEB_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copytree(FRONTEND_DIR / "dist", WEB_DIR, dirs_exist_ok=True)

    assets_dir = FRONTEND_DIR / "src" / "assets"
    if assets_dir.exists():
        shutil.copytree(assets_dir, WEB_DIR / "assets", dirs_exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Build software.")
    parser.add_argument(
        "-v", "--version", default=os.getenv("VECTORVEIN_VERSION", "0.0.1"), help="version number, default: 0.0.1"
    )
    parser.add_argument(
        "-t", "--type", default="production", help="build type: development(d) or production(p) or frontend(f)"
    )
    args = parser.parse_args()
    if args.type == "p" or args.type == "production":
        build_production(args.version)
    elif args.type == "d" or args.type == "development":
        build_development(args.version)
    elif args.type == "f" or args.type == "frontend":
        build_frontend()


if __name__ == "__main__":
    main()
