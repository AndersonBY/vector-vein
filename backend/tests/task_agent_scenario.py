"""Deterministic local endpoint used by integration tests and desktop acceptance."""
import json
import time
from http.server import BaseHTTPRequestHandler


class ScenarioModelHandler(BaseHTTPRequestHandler):
    calls = []
    delay = 0

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).calls.append(payload)
        time.sleep(self.delay)
        tools = [m for m in payload["messages"] if m.get("role") == "tool"]
        count = len(tools)
        plans = [
            ("todo_write", {"todos": [{"id": "confirm", "priority": "medium", "title": "确认交付格式", "status": "in_progress"}, {"id": "deliver", "priority": "medium", "title": "生成验收报告", "status": "pending"}]}, "我会先确认交付格式，再生成文件供你检查。"),
            ("ask_user", {"question": "报告使用哪种格式？", "options": ["Markdown", "纯文本"], "selection_type": "single", "allow_custom_options": False}, "请选择报告格式。"),
            ("write_file", {"path": "outputs/验收报告.md", "content": "# 桌面任务 Agent 验收报告\n\n已确认交付格式，并完成文件生成。\n\n- 进展记录可查看\n- 人工回答可继续任务\n- 结果保存在独立工作区\n"}, "已收到你的回答，正在生成报告。"),
            ("todo_write", {"todos": [{"id": "confirm", "priority": "medium", "title": "确认交付格式", "status": "completed"}, {"id": "deliver", "priority": "medium", "title": "生成验收报告", "status": "completed"}]}, "报告已生成，正在整理交付内容。"),
        ]
        call = None
        content = "任务已完成。[查看验收报告](outputs/验收报告.md)。你可以在右侧工作区预览文件或继续补充要求。"
        if count < len(plans):
            name, arguments, content = plans[count]
            call = {"id": f"call_{count}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}
        if payload.get("stream"):
            chunks = [self._chunk(payload, {"role": "assistant", "content": content})]
            if call:
                chunks.append(self._chunk(payload, {"tool_calls": [{"index": 0, **call}]}))
            chunks.append(self._chunk(payload, {}, "tool_calls" if call else "stop"))
            body = "".join("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n"
            mime = "text/event-stream; charset=utf-8"
        else:
            response = {"role": "assistant", "content": content}
            if call:
                response["tool_calls"] = [call]
            body = json.dumps({"id": "scenario", "object": "chat.completion", "created": 1, "model": payload["model"],
                               "choices": [{"index": 0, "message": response, "finish_reason": "tool_calls" if call else "stop"}],
                               "usage": {"prompt_tokens": 32, "completion_tokens": 16, "total_tokens": 48}}, ensure_ascii=False)
            mime = "application/json; charset=utf-8"
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass

    @staticmethod
    def _chunk(payload, delta, finish=None):
        result = {"id": "scenario", "object": "chat.completion.chunk", "created": 1, "model": payload["model"],
                  "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
        if finish:
            result["usage"] = {"prompt_tokens": 32, "completion_tokens": 16, "total_tokens": 48}
        return result

    def log_message(self, *args):
        pass
