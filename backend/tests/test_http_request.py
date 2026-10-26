import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from utilities import http_request as requests
from utilities.workflow import Workflow
from worker.tasks import tools


@pytest.fixture
def server(monkeypatch):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            seen.append((self.command, self.path, body, dict(self.headers)))
            path = urlsplit(self.path).path
            status = 422 if path == "/error" else 200
            output = b"secret error body" if status == 422 else json.dumps({"query": parse_qs(urlsplit(self.path).query), "body": body}).encode()
            if path == "/large":
                output = b"x" * 200
            elif path == "/text":
                output = b"plain text"
            elif path == "/null":
                output = b"null"
            elif path == "/nonfinite":
                output = b'{"number": NaN}'
            elif path == "/gzip":
                output = gzip.compress(b'{"decoded": true}')
            self.send_response(status)
            if path == "/gzip":
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(output)))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(output)

        do_POST = do_GET
        do_PUT = do_GET
        do_PATCH = do_GET

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(requests, "new_httpx_client", lambda **kwargs: httpx.Client(trust_env=False))
    monkeypatch.setattr(Workflow, "report_node_status", lambda *args: True)
    monkeypatch.setattr(Workflow, "report_workflow_status", lambda *args: True)
    yield f"http://127.0.0.1:{httpd.server_port}", seen
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def workflow(**values):
    return {"nodes": [{"id": "request", "type": "HTTPRequest", "category": "tools", "data": {"task_name": "tools.http_request", "template": {key: {"value": value} for key, value in values.items()}}}], "edges": []}


def test_query_merge_and_workflow_outputs(server):
    base, seen = server
    data = workflow(url=base + "/?existing=1&same=old", query_params={"same": ["new", "next"], "count": 0, "enabled": False}, headers='{"X-Test": "hello"}')
    result = tools.http_request(data, "request")
    wf = Workflow(result)
    assert wf.get_node_field_value("request", "response_json")["query"] == {"existing": ["1"], "same": ["old", "new", "next"], "count": ["0"], "enabled": ["false"]}
    assert wf.get_node_field_value("request", "status_code") == 200
    assert wf.get_node_field_value("request", "response_headers")["content-type"].startswith("application/json")
    assert seen[0][3]["X-Test"] == "hello"


@pytest.mark.parametrize("kind,body,expected", [("json", {"zero": 0, "false": False}, '{"zero": 0, "false": false}'), ("json", False, "false"), ("json", 0, "0"), ("json", "null", "null"), ("text", "hello 世界", "hello 世界"), ("form", '{"a":"hello world","b":0}', "a=hello+world&b=0")])
def test_request_bodies(server, kind, body, expected):
    base, seen = server
    result = requests.perform_http_request(url=base, method="POST", body_type=kind, body=body)
    assert result["response_json"]["body"] == expected
    assert len(seen) == 1


def test_http_failure_retains_outputs_without_secret_diagnostics(server):
    base, seen = server
    data = workflow(url=base + "/error")
    with pytest.raises(RuntimeError, match="status 422") as error:
        tools.http_request(data, "request")
    assert "secret" not in str(error.value)
    assert Workflow(data).get_node_field_value("request", "response_body") == "secret error body"
    assert data["failures"][0]["node_id"] == "request"
    result = tools.http_request(workflow(url=base + "/error", fail_on_http_error=False), "request")
    assert Workflow(result).get_node_field_value("request", "status_code") == 422
    assert len(seen) == 2


@pytest.mark.parametrize("options", [{"url": "file:///secret"}, {"timeout": 0}, {"timeout": 301}, {"timeout": float("nan")}, {"timeout": True}, {"timeout": "30"}, {"headers": '{"x":0}'}, {"headers": {"x": "bad\r\nsecret"}}, {"query_params": {"a": {"nested": 1}}}, {"body_type": "form", "body": "[]"}, {"body_type": "json", "body": "invalid secret"}, {"body_type": "text", "body": False}, {"method": "INVALID"}, {"follow_redirects": "false"}])
def test_invalid_configuration_never_sends(server, options):
    base, seen = server
    with pytest.raises(ValueError):
        requests.perform_http_request(**{"url": base, **options})
    assert seen == []


def test_response_cap_and_non_json(server, monkeypatch):
    base, _ = server
    monkeypatch.setattr(requests, "MAX_RESPONSE_BYTES", 100)
    with pytest.raises(RuntimeError, match="limit"):
        requests.perform_http_request(url=base + "/large")
    assert requests.perform_http_request(url=base + "/text")["response_body"] == "plain text"
    assert requests.perform_http_request(url=base + "/text")["response_json"] is None
    assert requests.perform_http_request(url=base + "/null")["response_json"] is None
    assert requests.perform_http_request(url=base + "/gzip")["response_json"] == {"decoded": True}
    assert requests.perform_http_request(url=base + "/nonfinite")["response_json"] is None


def test_headers_are_not_mutated_and_failed_rerun_clears_outputs(server):
    base, _ = server
    headers = {"X-Test": "preserved"}
    requests.perform_http_request(url=base, headers=headers, body_type="json", body={})
    assert headers == {"X-Test": "preserved"}
    data = tools.http_request(workflow(url=base), "request")
    Workflow(data).update_node_field_value("request", "timeout", 0)
    with pytest.raises(ValueError):
        tools.http_request(data, "request")
    wf = Workflow(data)
    assert wf.get_node_field_value("request", "status_code") is None
    assert wf.get_node_field_value("request", "response_headers") == {}
    assert wf.get_node_field_value("request", "response_body") == ""
    assert wf.get_node_field_value("request", "response_json") is None
    assert data["failures"][0]["code"] == "INVALID_ARGUMENT"


def test_connected_input_and_output(server):
    base, _ = server
    data = workflow(url=base, method="POST", body_type="json", body="{}")
    source = workflow(output=False)["nodes"][0]
    source["id"] = "source"
    target = workflow(body="")["nodes"][0]
    target["id"] = "target"
    data["nodes"].extend([source, target])
    data["edges"] = [{"source": "source", "sourceHandle": "output", "target": "request", "targetHandle": "body"}, {"source": "request", "sourceHandle": "response_json", "target": "target", "targetHandle": "body"}]
    result = tools.http_request(data, "request")
    assert Workflow(result).get_node_field_value("target", "body")["body"] == "false"
    assert tools.http_request.celery_task.name == "tasks.tools.http_request"


def test_transport_error_hides_url_and_closes_client(monkeypatch):
    clients = []
    def handler(request):
        raise httpx.ReadTimeout("secret URL or header", request=request)
    def factory(**kwargs):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        clients.append(client)
        return client
    monkeypatch.setattr(requests, "new_httpx_client", factory)
    with pytest.raises(RuntimeError, match=r"^HTTP request failed \(ReadTimeout\)$"):
        requests.perform_http_request(url="https://example.test/?token=secret")
    assert clients[0].is_closed
