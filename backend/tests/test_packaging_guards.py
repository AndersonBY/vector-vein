import builtins
import importlib
import importlib.util
import sys
import textwrap

import pytest


def _clear_module(module_name: str) -> None:
    for loaded_name in list(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
            sys.modules.pop(loaded_name)


def test_media_processing_imports_without_audio_dependencies(monkeypatch):
    _clear_module("utilities.media_processing")

    real_import = builtins.__import__
    blocked_prefixes = (
        "utilities.media_processing.audio",
        "numpy",
        "pyaudio",
    )

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level and globals and globals.get("__package__"):
            absolute_name = importlib.util.resolve_name(f"{'.' * level}{name}", globals["__package__"])
        else:
            absolute_name = name

        if absolute_name.startswith(blocked_prefixes):
            raise ModuleNotFoundError(f"simulated missing dependency: {absolute_name}")

        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    media_processing = importlib.import_module("utilities.media_processing")

    assert callable(media_processing.get_screenshot)
    assert "TTSClient" in media_processing.__all__


def test_verify_runtime_dependencies_detects_missing_packages(tmp_path):
    from packaging_guard import MissingRuntimeDependencyError, verify_runtime_dependencies

    internal_dir = tmp_path / "_internal"
    internal_dir.mkdir()
    (internal_dir / "pyaudio").mkdir()

    with pytest.raises(MissingRuntimeDependencyError) as exc_info:
        verify_runtime_dependencies(tmp_path, required_packages=("numpy", "pyaudio"))

    assert "numpy" in str(exc_info.value)


def test_verify_runtime_dependencies_accepts_present_packages(tmp_path):
    from packaging_guard import verify_runtime_dependencies

    internal_dir = tmp_path / "_internal"
    internal_dir.mkdir()
    (internal_dir / "numpy").mkdir()
    (internal_dir / "pyaudio").mkdir()

    verify_runtime_dependencies(tmp_path, required_packages=("numpy", "pyaudio"))


def test_build_command_failures_stop_the_build():
    from subprocess import CalledProcessError

    from build import run_cmd

    with pytest.raises(CalledProcessError):
        run_cmd("python -c \"import sys; sys.exit(7)\"")


def test_verify_lockfile_groups_detects_missing_groups(tmp_path):
    from packaging_guard import MissingLockfileGroupError, verify_lockfile_groups

    lockfile_path = tmp_path / "pdm.lock"
    lockfile_path.write_text(
        textwrap.dedent(
            """
            [metadata]
            groups = ["default", "dev"]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(MissingLockfileGroupError) as exc_info:
        verify_lockfile_groups(lockfile_path, required_groups=("dev", "mac"))

    assert "mac" in str(exc_info.value)


def test_verify_lockfile_groups_accepts_present_groups(tmp_path):
    from packaging_guard import verify_lockfile_groups

    lockfile_path = tmp_path / "pdm.lock"
    lockfile_path.write_text(
        textwrap.dedent(
            """
            [metadata]
            groups = ["default", "dev", "mac"]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    verify_lockfile_groups(lockfile_path, required_groups=("dev", "mac"))


def test_verify_declared_runtime_dependencies_detects_missing_distribution(tmp_path):
    from packaging_guard import MissingDeclaredDependencyError, verify_declared_runtime_dependencies

    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        textwrap.dedent(
            """
            [project]
            dependencies = [
              "numpy>=1.26.0",
              "pyaudio>=0.2.14",
            ]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(MissingDeclaredDependencyError) as exc_info:
        verify_declared_runtime_dependencies(
            pyproject_path,
            required_distributions=("numpy", "pyaudio", "openai"),
        )

    assert "openai" in str(exc_info.value)


def test_verify_declared_runtime_dependencies_accepts_present_distributions(tmp_path):
    from packaging_guard import verify_declared_runtime_dependencies

    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        textwrap.dedent(
            """
            [project]
            dependencies = [
              "numpy>=1.26.0",
              "pyaudio>=0.2.14",
              "openai>=1.0.0",
            ]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    verify_declared_runtime_dependencies(
        pyproject_path,
        required_distributions=("numpy", "pyaudio", "openai"),
    )


def test_project_declares_packaged_runtime_dependencies():
    from packaging_guard import verify_declared_runtime_dependencies

    verify_declared_runtime_dependencies()


def test_verify_importable_runtime_dependencies_detects_missing_package(monkeypatch):
    from packaging_guard import MissingImportableDependencyError, verify_importable_runtime_dependencies

    real_import_module = importlib.import_module

    def guarded_import_module(name: str):
        if name == "pyaudio":
            raise ModuleNotFoundError("simulated missing dependency: pyaudio")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", guarded_import_module)

    with pytest.raises(MissingImportableDependencyError) as exc_info:
        verify_importable_runtime_dependencies(required_packages=("numpy", "pyaudio"))

    assert "pyaudio" in str(exc_info.value)


def test_verify_importable_runtime_dependencies_accepts_present_packages(monkeypatch):
    from packaging_guard import verify_importable_runtime_dependencies

    imported_packages = []

    def guarded_import_module(name: str):
        imported_packages.append(name)
        return object()

    monkeypatch.setattr(importlib, "import_module", guarded_import_module)

    verify_importable_runtime_dependencies(required_packages=("numpy", "pyaudio"))

    assert imported_packages == ["numpy", "pyaudio"]


def test_verify_spec_hidden_imports_detects_missing_package(tmp_path):
    from packaging_guard import MissingRuntimeDependencyError, verify_spec_hidden_imports

    spec_path = tmp_path / "missing.spec"
    spec_path.write_text(
        textwrap.dedent(
            """
            a = Analysis(
                ["main.py"],
                hiddenimports=[
                    "utilities.media_processing.audio",
                    "numpy",
                ],
            )
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(MissingRuntimeDependencyError) as exc_info:
        verify_spec_hidden_imports((spec_path,), required_packages=("numpy", "pyaudio"))

    assert "pyaudio" in str(exc_info.value)


def test_project_specs_include_audio_runtime_dependencies():
    from packaging_guard import verify_spec_hidden_imports

    verify_spec_hidden_imports()
