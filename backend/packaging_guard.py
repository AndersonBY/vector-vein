from __future__ import annotations

from pathlib import Path


class MissingRuntimeDependencyError(RuntimeError):
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
