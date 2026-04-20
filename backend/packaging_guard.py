from __future__ import annotations

import ast
import importlib
from pathlib import Path
import re
import tomllib


class MissingRuntimeDependencyError(RuntimeError):
    pass


class MissingLockfileGroupError(RuntimeError):
    pass


class MissingDeclaredDependencyError(RuntimeError):
    pass


class MissingImportableDependencyError(RuntimeError):
    pass


def _package_exists(internal_dir: Path, package_name: str) -> bool:
    package_path = internal_dir / package_name
    package_file = internal_dir / f"{package_name}.py"

    if package_path.exists():
        return True

    return package_file.exists()


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _dependency_name(requirement: str) -> str:
    requirement = requirement.split(";", 1)[0].strip()
    return re.split(r"\s*(?:\[|==|!=|<=|>=|~=|<|>|@)\s*", requirement, maxsplit=1)[0]


def verify_runtime_dependencies(
    dist_dir: str | Path,
    required_packages: tuple[str, ...] = ("numpy", "pyaudio"),
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


def verify_declared_runtime_dependencies(
    pyproject_path: str | Path = "pyproject.toml",
    required_distributions: tuple[str, ...] = ("numpy", "pyaudio"),
) -> None:
    pyproject_path = Path(pyproject_path)
    pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = pyproject_data.get("project", {}).get("dependencies", [])
    declared_distributions = {
        _normalize_distribution_name(_dependency_name(dependency))
        for dependency in dependencies
    }

    missing_distributions = [
        distribution
        for distribution in required_distributions
        if _normalize_distribution_name(distribution) not in declared_distributions
    ]

    if missing_distributions:
        missing = ", ".join(missing_distributions)
        raise MissingDeclaredDependencyError(
            f"Missing runtime dependency declarations in {pyproject_path}: {missing}"
        )


def verify_importable_runtime_dependencies(
    required_packages: tuple[str, ...] = ("numpy", "pyaudio"),
) -> None:
    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ModuleNotFoundError as exc:
            if exc.name is None or exc.name == package or exc.name.startswith(f"{package}."):
                missing_packages.append(package)
            else:
                raise

    if missing_packages:
        missing = ", ".join(missing_packages)
        raise MissingImportableDependencyError(f"Missing importable runtime dependencies: {missing}")


def _spec_hidden_imports(spec_path: Path) -> set[str]:
    spec_tree = ast.parse(spec_path.read_text(encoding="utf-8"), filename=str(spec_path))
    for node in ast.walk(spec_tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = getattr(node.func, "id", None)
        if function_name != "Analysis":
            continue
        for keyword in node.keywords:
            if keyword.arg == "hiddenimports":
                hidden_imports = ast.literal_eval(keyword.value)
                return {str(hidden_import) for hidden_import in hidden_imports}
    return set()


def verify_spec_hidden_imports(
    spec_paths: tuple[str | Path, ...] = ("main.spec", "debug.spec"),
    required_packages: tuple[str, ...] = ("utilities.media_processing.audio", "numpy", "pyaudio"),
) -> None:
    missing_by_spec = {}
    for spec_path in spec_paths:
        spec_path = Path(spec_path)
        hidden_imports = _spec_hidden_imports(spec_path)
        missing_packages = [package for package in required_packages if package not in hidden_imports]
        if missing_packages:
            missing_by_spec[str(spec_path)] = missing_packages

    if missing_by_spec:
        details = "; ".join(
            f"{spec}: {', '.join(packages)}"
            for spec, packages in missing_by_spec.items()
        )
        raise MissingRuntimeDependencyError(f"Missing PyInstaller hidden imports: {details}")
