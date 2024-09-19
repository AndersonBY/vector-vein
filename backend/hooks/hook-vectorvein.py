from PyInstaller.utils.hooks import collect_all, collect_submodules

# 收集vectorvein的所有内容
datas, binaries, hiddenimports = collect_all("vectorvein")

# 添加vectorvein的直接依赖
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
