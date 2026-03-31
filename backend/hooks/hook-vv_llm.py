from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all vv_llm package data for PyInstaller.
datas, binaries, hiddenimports = collect_all("vv_llm")

# Add vv_llm direct dependencies that PyInstaller may miss.
additional_imports = [
    "openai",
    "tiktoken",
    "httpx",
    "anthropic",
    "pydantic",
    "PIL",
    "deepseek_tokenizer",
    "qwen_tokenizer",
]

# 对每个依赖包收集所有子模块
for package in additional_imports:
    hiddenimports.extend(collect_submodules(package))
