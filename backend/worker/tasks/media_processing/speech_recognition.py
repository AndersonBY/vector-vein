from worker.tasks import task, timer
from utilities.workflow import Workflow
from utilities.network import new_httpx_client
from utilities.media_processing import SpeechRecognitionClient


@task
@timer
def speech_recognition(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    files_or_urls = workflow.get_node_field_value(node_id, "files_or_urls")
    if files_or_urls == "files":
        files = workflow.get_node_field_value(node_id, "files")
        if isinstance(files, str):
            files = [files]
        files_data = [open(file, "rb") for file in files]
    elif files_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            urls = [urls]
        elif isinstance(urls, list):
            urls = urls
        http_client = new_httpx_client(is_async=False)
        files_data = [http_client.get(url).content for url in urls]
    else:
        raise Exception("Invalid files_or_urls")

    engine = workflow.get_node_field_value(node_id, "engine", "openai")
    client = SpeechRecognitionClient(provider=engine)
    output_type = workflow.get_node_field_value(node_id, "output_type")
    outputs = client.batch_transcribe(files_data, output_type)

    if files_or_urls == "urls":
        if isinstance(workflow.get_node_field_value(node_id, "urls"), str):
            outputs = outputs[0]
    elif files_or_urls == "files":
        if len(outputs) == 1:
            outputs = outputs[0]

    workflow.update_node_field_value(node_id, "output", outputs)
    return workflow.data
