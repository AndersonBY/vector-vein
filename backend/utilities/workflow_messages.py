"""Project the authoritative run result onto its originating chat message."""
import json

from models import Message, WorkflowRunRecord
from utilities.workflow_errors import workflow_error_payload


def project_workflow_message(record):
    if record.run_from != WorkflowRunRecord.RunFromTypes.CHAT:
        return
    message = Message.get_or_none(Message.mid == record.source_message)
    if message is None or message.metadata.get("record_id") != record.rid.hex:
        return
    metadata = {**message.metadata, "recordStatus": record.status}
    status = Message.StatusTypes.RUNNING_WORKFLOW
    if record.status == "FINISHED":
        from utilities.workflow import WorkflowData
        metadata["workflow_result"] = "\n\n".join(
            f"# {item['title']}\n{item['value']}" if item["title"] else f"{item['value']}"
            for item in WorkflowData(record.data).output_contents)
        status = Message.StatusTypes.SUCCESS
    elif record.status == "FAILED":
        metadata["workflow_result"] = json.dumps(workflow_error_payload(record), ensure_ascii=False)
        status = Message.StatusTypes.WORKFLOW_FAILED
    elif record.status == "STOPPED":
        metadata["workflow_result"] = "Workflow stopped. Completed outputs are retained."
        status = Message.StatusTypes.WORKFLOW_FAILED
    Message.update(metadata=metadata, status=status).where(Message.mid == message.mid,
        Message.metadata == message.metadata).execute()
