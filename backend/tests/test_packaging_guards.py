import builtins
import importlib
import importlib.util
import sys

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
        "deepgram",
        "deepgram_captions",
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
    (internal_dir / "deepgram").mkdir()

    with pytest.raises(MissingRuntimeDependencyError) as exc_info:
        verify_runtime_dependencies(tmp_path, required_packages=("numpy", "deepgram"))

    assert "numpy" in str(exc_info.value)


def test_verify_runtime_dependencies_accepts_present_packages(tmp_path):
    from packaging_guard import verify_runtime_dependencies

    internal_dir = tmp_path / "_internal"
    internal_dir.mkdir()
    (internal_dir / "numpy").mkdir()
    (internal_dir / "deepgram").mkdir()

    verify_runtime_dependencies(tmp_path, required_packages=("numpy", "deepgram"))


def test_build_command_failures_stop_the_build():
    from subprocess import CalledProcessError

    from build import run_cmd

    with pytest.raises(CalledProcessError):
        run_cmd("python -c \"import sys; sys.exit(7)\"")
