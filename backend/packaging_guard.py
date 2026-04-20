from __future__ import annotations

from pathlib import Path
import tomllib


class MissingRuntimeDependencyError(RuntimeError):
    pass


class MissingLockfileGroupError(RuntimeError):
    pass


def _package_exists(internal_dir: Path, package_name: str) -> bool:
    package_path = internal_dir / package_name
    package_file = internal_dir / f"{package_name}.py"

    if package_path.exists():
        return True

    return package_file.exists()


def verify_runtime_dependencies(
    dist_dir: str | Path,
    required_packages: tuple[str, ...] = ("numpy", "deepgram", "pyaudio"),
) -> None:
    dist_dir = Path(dist_dir)
    internal_dir = dist_dir / "_internal"
    if not internal_dir.exists():
        raise MissingRuntimeDependencyError(f"Missing PyInstaller internal directory: {internal_dir}")

    missing_packages = [package for package in required_packages if not _package_exists(internal_dir, package)]
    if missing_packages:
        missing = ", ".join(missing_packages)
        raise MissingRuntimeDependencyError(
            f"Missing packaged runtime dependencies in {internal_dir}: {missing}"
        )


def verify_lockfile_groups(
    lockfile_path: str | Path = "pdm.lock",
    required_groups: tuple[str, ...] = ("default", "dev", "mac"),
) -> None:
    lockfile_path = Path(lockfile_path)
    lockfile_data = tomllib.loads(lockfile_path.read_text(encoding="utf-8"))
    locked_groups = set(lockfile_data.get("metadata", {}).get("groups", []))
    missing_groups = [group for group in required_groups if group not in locked_groups]

    if missing_groups:
        missing = ", ".join(missing_groups)
        raise MissingLockfileGroupError(f"Missing dependency groups in {lockfile_path}: {missing}")
