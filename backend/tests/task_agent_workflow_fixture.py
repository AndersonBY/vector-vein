"""Local-only workflow used by automated and explicitly authorized live-model checks."""
from copy import deepcopy


def field(value, kind="str", **extra):
    return {"value": value, "type": kind, "show": False, "list": False, **extra}


def workflow_data(feedback=True):
    nodes = [{"id": "compose", "type": "TemplateCompose", "category": "textProcessing", "data": {
        "task_name": "text_processing.template_compose", "has_inputs": True,
        "template": {"template": field("{{text}}"), "text": field("", show=True, display_name="Report text"), "output": field("", is_output=True)}}}]
    edges = []
    previous = "compose"
    if feedback:
        nodes.append({"id": "review", "type": "HumanFeedback", "category": "controlFlows", "data": {
            "task_name": "control_flows.human_feedback", "template": {
                "hint_message": field("Review this report"), "human_input": field(""), "output": field("", is_output=True)}}})
        edges.append({"source": "compose", "target": "review", "sourceHandle": "output", "targetHandle": "hint_message"})
        previous = "review"
    nodes.append({"id": "export", "type": "Document", "category": "outputs", "data": {
        "task_name": "output.document", "template": {
            "file_name": field("agent-workflow-report"), "content": field(""), "export_type": field(".md"),
            "overwrite": field(False, "bool"), "output": field("", is_output=True)}}})
    edges.append({"source": previous, "target": "export", "sourceHandle": "output", "targetHandle": "content"})
    return {"nodes": nodes, "edges": edges}


def create_workflow(feedback=True):
    from models import Workflow
    return Workflow.create(title="Local report workflow", brief="Formats report text, requests human review, and exports a Markdown report locally.", data=deepcopy(workflow_data(feedback)))
