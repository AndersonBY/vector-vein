# @Author: Bi Ying
# @Date:   2024-06-07 12:59:42
import re

from vectorvein.types.enums import BackendType
from vectorvein.chat_clients import create_chat_client
from vectorvein.settings import settings as vectorvein_settings

from utilities.config import Settings
from models import Workflow, WorkflowTemplate


class ToolCallData:
    _TYPE_MAP = {
        "str": "string",
        "int": "integer",
        "bool": "boolean",
        "float": "number",
        "list": "array",
        "dict": "object",
    }

    def __init__(self, workflow: Workflow | WorkflowTemplate):
        self.workflow = workflow
        self.tool_call_data: dict = workflow.tool_call_data
        self.field_translations = self.tool_call_data.get("field_translations", {})
        self.parameters = self.tool_call_data.get("parameters", {})
        self.parameter_sources = self.tool_call_data.get("parameter_sources", {})
        user_settings = Settings()
        vectorvein_settings.load(user_settings.get("llm_settings"))
        backend, model = user_settings.get("agent.tool_call_data_generate_model")
        if backend.lower().startswith("_local__"):
            backend = BackendType.Local
        else:
            backend = BackendType(backend.lower())
        self.chat_client = create_chat_client(backend=backend, model=model, stream=False)

    @staticmethod
    def _is_valid_string(s):
        # 正则表达式匹配1到64个字母、数字、下划线或连字符
        pattern = r"^[a-zA-Z0-9_-]{1,64}$"
        return bool(re.match(pattern, s))

    @staticmethod
    def _has_show_fields(node):
        return any(value.get("show", False) for value in node["data"]["template"].values())

    def _translate_field(self, field):
        if field in self.field_translations:
            return self.field_translations[field]
        prompt = f"Generate an English parameter name for the following parameter, using only lowercase English letters, numbers, and underscores (_), not exceeding 20 characters. Directly output the result without explanation.\nParameter name: {field}\n"
        messages = [{"role": "user", "content": prompt}]
        translated_field = self.chat_client.create_completion(messages=messages).content
        if translated_field is None:
            return field
        translated_field_options = re.findall(r"[a-z0-9_]{1,20}", translated_field)
        if translated_field_options:
            translated_field = max(translated_field_options, key=len)
        else:
            translated_field = field[-20:]
        self.field_translations[field] = translated_field
        return translated_field

    def update_title(self, force: bool = False):
        if self.tool_call_data.get("name") and not force:
            return
        workflow_title = self.workflow.title
        prompt = f"For the following workflow, generate an English function name, using only lowercase English letters, numbers, and underscores (_), not exceeding 40 characters. Directly output the English function name result without explanation.\nWorkflow Title: {workflow_title}\n"
        messages = [{"role": "user", "content": prompt}]
        title = self.chat_client.create_completion(messages=messages).content
        if title is None:
            return
        titles = re.findall(r"[a-z0-9_]{1,40}", title)
        if titles:
            title = max(titles, key=len)
        else:
            title = workflow_title
        self.tool_call_data["name"] = title

    def update_parameters(self):
        parameters = {}
        parameter_sources = {}
        for node in self.workflow.data["nodes"]:
            if not all(
                [
                    node["data"].get("has_inputs", False),
                    ToolCallData._has_show_fields(node),
                    node["category"] != "triggers",
                ]
            ):
                continue

            for field, value in node["data"]["template"].items():
                if not value.get("show", False):
                    continue

                parameter_source = {"field": field, "node": node["id"]}

                if not ToolCallData._is_valid_string(field):
                    field = self._translate_field(field)

                if field in parameters:
                    count = 1
                    while f"{field}-{count}" in parameters:
                        count += 1
                    parameter_name = f"{field}-{count}"
                else:
                    parameter_name = field

                value_type = value["type"].split("|")[0]
                parameters[parameter_name] = {
                    "type": ToolCallData._TYPE_MAP[value_type],
                }

                parameter_sources[parameter_name] = {
                    **parameter_source,
                    "required": len(str(value["value"])) == 0,
                }

                if value["list"]:
                    if "options" not in value:
                        continue
                    parameters[parameter_name]["enum"] = [option["value"] for option in value["options"]]

        # self.parameters里是原有的参数设置和描述，parameters里是新的参数设置和描述
        # self.parameter_sources里是原有的参数来源，parameter_sources里是新的参数来源
        # 原有的参数的名称、描述可能被用户修改过，需要更新到新的参数里
        combined_parameters = {}
        combined_parameter_sources = {}
        for parameter_name, parameter_value in parameters.items():
            source = parameter_sources[parameter_name]
            # 从 self.parameter_sources 里找有没有同样的source
            for old_parameter_name, old_source in self.parameter_sources.items():
                if source["field"] == old_source["field"] and source["node"] == old_source["node"]:
                    # 如果有，把原有的参数名称、描述赋值给新的参数
                    combined_parameters[old_parameter_name] = self.parameters["properties"][old_parameter_name]
                    combined_parameter_sources[old_parameter_name] = {
                        **parameter_sources[parameter_name],
                        **old_source,
                    }
                    break
            else:
                combined_parameters[parameter_name] = parameter_value
                combined_parameter_sources[parameter_name] = parameter_sources[parameter_name]

        self.tool_call_data["parameters"] = {
            "type": "object",
            "properties": combined_parameters,
            "required": [name for name, value in combined_parameter_sources.items() if value.get("required")],
        }
        self.parameter_sources = combined_parameter_sources

    def save(self):
        description = (
            self.tool_call_data["description"] if self.tool_call_data.get("description") else self.workflow.brief
        )
        self.tool_call_data.update(
            {
                "field_translations": self.field_translations,
                "parameter_sources": self.parameter_sources,
                "description": description,
                "workflow_id": self.workflow.tid.hex
                if isinstance(self.workflow, WorkflowTemplate)
                else self.workflow.wid.hex,
            }
        )
        self.workflow.tool_call_data = self.tool_call_data
        self.workflow.save()
