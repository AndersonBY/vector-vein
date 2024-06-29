# @Author: Bi Ying
# @Date:   2024-04-29 16:50:17
DEFAULT_SETTINGS = {
    "initial_setup": False,
    "openai_api_type": "open_ai",
    "openai_api_key": "",
    "openai_api_base": "https://api.openai.com/v1",
    "azure_openai": {
        "endpoints": [],
        "gpt_35_deployment": {"id": "", "endpoint_id": "", "endpoint": {"api_base": "", "api_key": ""}},
        "gpt_4_deployment": {"id": "", "endpoint_id": "", "endpoint": {"api_base": "", "api_key": ""}},
        "gpt_4o_deployment": {"id": "", "endpoint_id": "", "endpoint": {"api_base": "", "api_key": ""}},
        "gpt_4v_deployment": {"id": "", "endpoint_id": "", "endpoint": {"api_base": "", "api_key": ""}},
        "whisper_deployment": {"id": "", "endpoint_id": "", "endpoint": {"api_base": "", "api_key": ""}},
        "tts_deployment": {"id": "", "endpoint_id": "", "endpoint": {"api_base": "", "api_key": ""}},
        "tts_hd_deployment": {"id": "", "endpoint_id": "", "endpoint": {"api_base": "", "api_key": ""}},
        "dalle3_deployment": {"id": "", "endpoint_id": "", "endpoint": {"api_base": "", "api_key": ""}},
        "text_embedding_ada_002_deployment": {
            "id": "",
            "endpoint_id": "",
            "endpoint": {"api_base": "", "api_key": ""},
        },
    },
    "baichuan_api_base": "https://api.baichuan-ai.com/v1",
    "baichuan_api_key": "",
    "moonshot_api_base": "https://api.moonshot.cn/v1",
    "moonshot_api_key": "",
    "zhipuai_api_base": "https://open.bigmodel.cn/api/paas/v4/",
    "zhipuai_api_key": "",
    "anthropic_api_base": "https://api.anthropic.com/v1",
    "anthropic_api_key": "",
    "minimax_api_base": "https://api.minimax.chat/v1/text/chatcompletion_v2",
    "minimax_api_key": "",
    "qwen_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "qwen_api_key": "",
    "mistral_api_base": "https://api.mistral.ai/v1",
    "mistral_api_key": "",
    "deepseek_api_base": "https://api.deepseek.com/v1",
    "deepseek_api_key": "",
    "lingyiwanwu_api_base": "https://api.lingyiwanwu.com/v1",
    "lingyiwanwu_api_key": "",
    "gemini_api_base": "https://generativelanguage.googleapis.com/v1beta",
    "gemini_api_key": "",
    "groq_api_base": "https://api.groq.com/openai/v1",
    "groq_api_key": "",
    "local_llms": [],
    "output_folder": "./",
    "data_path": "./data",
    "log_path": "./log",
    "email": {"user": "", "password": "", "smtp_host": "", "smtp_port": "", "smtp_ssl": True},
    "pexels_api_key": "",
    "stable_diffusion_base_url": "http://127.0.0.1:7860",
    "stability_key": "",
    "use_system_proxy": True,
    "website_domain": "vectorvein.ai",
    "agent": {"auto_title": True, "auto_title_model": ["OpenAI", "gpt-35-turbo"], "screenshot_monitor_device": 0},
    "microphone_device": 0,
    "shortcuts": {},
    "embedding_models": {"text_embeddings_inference": {"api_base": "http://localhost:8080/embed"}},
    "tts": {"piper": {"api_base": "http://localhost:5000"}},
    "asr": {
        "provider": "openai",
        "openai": {"same_as_llm": True, "api_base": "https://api.openai.com/v1", "api_key": "", "model": "whisper-1"},
        "deepgram": {"api_key": "", "speech_to_text": {"model": "nova-2", "language": "en"}},
    },
    "web_search": {"jinaai": {"api_key": ""}, "bing": {"ocp_apim_subscription_key": ""}},
}


class Settings:
    def __init__(self):
        self.data = dict()
        try:
            self.load_setting()
        except Exception:
            self.data = dict()

    def load_setting(self):
        from models import model_serializer
        from models import Setting as SettingModel

        if SettingModel.select().count() == 0:
            setting = SettingModel.create(data=DEFAULT_SETTINGS)
        else:
            setting = SettingModel.select().order_by(SettingModel.create_time.desc()).first()
            setting.data = {**DEFAULT_SETTINGS, **setting.data}
            setting.save()
        self.data = model_serializer(setting)["data"]

    def __getattribute__(self, name: str):
        if name == "data":
            return super().__getattribute__(name)
        if name in super().__getattribute__("data"):
            return super().__getattribute__("data")[name]
        return super().__getattribute__(name)

    def get(self, name: str, default=None):
        """
        Retrieve a value from the settings data using a dot-separated key.

        This method allows you to access nested dictionary values using a
        dot-separated string to specify the key hierarchy. If any part of
        the specified key is not found, the method returns the provided
        default value.

        Parameters:
        name (str): A dot-separated string representing the key hierarchy
                    to access the desired value.
        default: The value to return if the specified key is not found.
                 Defaults to None.

        Returns:
        The value corresponding to the specified key hierarchy if found,
        otherwise the default value.

        Example:
        ```python
        settings = Settings()
        value = settings.get("level1.level2", "default")
        # If data is {"level1": {"level2": "abc"}}, value will be "abc"
        # If "level1.level2" does not exist, value will be "default"
        ```
        """
        keys = name.split(".")
        value = self.data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
