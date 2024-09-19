# @Author: Bi Ying
# @Date:   2024-06-06 11:38:21
import json
from datetime import datetime

from models import (
    Agent,
    Message,
    Workflow,
    Conversation,
    model_serializer,
    WorkflowRunRecord,
)
from api.utils import (
    JResponse,
    run_workflow_common,
    get_history_messages,
    get_user_object_general,
)
from utilities.config import cache
from utilities.file_processing import static_file_server
from utilities.media_processing import SpeechRecognitionClient


class ConversationAPI:
    name = "conversation"

    def list(self, payload):
        limit = int(payload.get("limit", 25))
        offset = int(payload.get("offset", 0))
        aid = payload.get("aid")
        status, msg, agent = get_user_object_general(Agent, aid=aid)
        if status != 200:
            return JResponse(status=status, msg=msg)
        conversations = Conversation.select().where(Conversation.agent == agent)
        total = conversations.count()
        conversations = conversations.order_by(Conversation.update_time.desc())
        conversations = conversations[offset : offset + limit]
        return JResponse(
            data={
                "agent": model_serializer(agent, manytomany=True),
                "conversations": model_serializer(conversations, many=True, manytomany=True),
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    def get(self, payload):
        cid = payload.get("cid")
        status, msg, conversation = get_user_object_general(Conversation, cid=cid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        if conversation.agent_version != conversation.agent.version:
            conversation.settings = conversation.agent.settings
            conversation.agent_version = conversation.agent.version

            conversation.related_workflows.clear()
            conversation.related_templates.clear()
            conversation.related_workflows.add(list(conversation.agent.related_workflows))
            conversation.related_templates.add(list(conversation.agent.related_templates))

            conversation.save()

        conversation_serializer = model_serializer(conversation, manytomany=True)
        conversation_serializer["agent"] = model_serializer(conversation.agent)
        _, _, start_message = get_user_object_general(Message, mid=conversation.current_message)
        history_messages = get_history_messages(start_message, count=None)
        return JResponse(
            data={
                "conversation": conversation_serializer,
                "messages": history_messages,
            }
        )

    def create(self, payload):
        conversation_data = payload.get("conversation", {})
        aid = conversation_data.get("aid")
        if aid is None:
            return JResponse(status=400)

        status, msg, agent = get_user_object_general(Agent, aid=aid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        conversation = Conversation.create(
            title=conversation_data.get("title", "New"),
            settings=conversation_data.get("settings", agent.settings),
            agent=agent,
            agent_version=agent.version,
            model=conversation_data.get("model", agent.model),
            model_provider=conversation_data.get("model_provider", agent.model_provider),
        )

        conversation.related_workflows.add(list(agent.related_workflows))
        conversation.related_templates.add(list(agent.related_templates))

        return JResponse(data={"cid": conversation.cid.hex})

    def update(self, payload):
        cid = payload.get("cid")
        conversation = Conversation.get_or_none(Conversation.cid == cid)

        if conversation is None:
            return JResponse(status=404)

        conversation.title = payload.get("title", conversation.title)
        conversation.model = payload.get("model", conversation.model)
        conversation.model_provider = payload.get("model_provider", conversation.model_provider)
        conversation.update_time = datetime.now()
        conversation.save()

        return JResponse()

    def delete(self, payload):
        cid = payload.get("cid")
        conversation = Conversation.get_or_none(Conversation.cid == cid)

        if conversation is None:
            return JResponse(status=404)

        conversation.delete_instance(recursive=True)

        return JResponse()

    def update_workflows(self, payload):
        cid = payload.get("cid")
        conversation = Conversation.get_or_none(Conversation.cid == cid)

        if conversation is None:
            return JResponse(status=404)

        workflow_ids = payload.get("workflow_ids", [])
        conversation.related_workflows.clear()

        for workflow_id in workflow_ids:
            workflow = Workflow.get_or_none(Workflow.wid == workflow_id)
            if workflow:
                conversation.related_workflows.add(workflow)

        return JResponse()

    def update_settings(self, payload):
        cid = payload.get("cid")
        status, msg, conversation = get_user_object_general(Conversation, cid=cid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        conversation.settings = payload.get("settings", {})
        conversation.save()
        return JResponse()


class MessageAPI:
    name = "message"

    def send(self, payload):
        cid = payload.get("cid")
        content = payload.get("content")
        content_type = payload.get("content_type")
        conversation = Conversation.get_or_none(Conversation.cid == cid)
        if not conversation:
            return JResponse(status=404)

        parent_mid = payload.get("parent_mid")
        parent_message = None
        if parent_mid:
            parent_message = Message.get_or_none((Message.mid == parent_mid) & (Message.conversation == conversation))
            if not parent_message:
                return JResponse(status=404)

        if parent_message:
            history_messages = get_history_messages(
                start_message=parent_message,
                count=None,
                all_children=False,
            )
        else:
            history_messages = []

        user_message = Message.create(
            conversation=conversation,
            author_type=Message.AuthorTypes.USER,
            content_type=content_type,
            content={"text": content},
            attachments=payload.get("attachments", []),
            parent=parent_message,
            status=Message.StatusTypes.SUCCESS,
        )

        ai_message: Message = Message.create(
            conversation=conversation,
            author_type=Message.AuthorTypes.ASSISTANT,
            content_type=Message.ContentTypes.TEXT,
            content={"text": ""},
            parent=user_message,
        )

        conversation.current_message = ai_message.mid
        conversation.update_time = ai_message.create_time
        conversation.save()

        history_messages = get_history_messages(
            start_message=user_message,
            count=None,
            all_children=False,
        )
        while len(history_messages) > 0 and history_messages[0]["author_type"] == Message.AuthorTypes.ASSISTANT:
            history_messages = history_messages[1:]

        need_title = payload.get("need_title", False)

        conversation_data = model_serializer(conversation)
        conversation_data["related_workflows"] = model_serializer(
            conversation.related_workflows, many=True, fields=["wid", "title", "brief"]
        )
        conversation_data["related_templates"] = model_serializer(
            conversation.related_templates, many=True, fields=["wid", "title", "brief"]
        )
        conversation_data["tool_call_data"] = {
            "workflows": [workflow.tool_call_data for workflow in conversation.related_workflows],
            "templates": [template.tool_call_data for template in conversation.related_templates],
        }

        return JResponse(
            data={
                "ai_message_mid": ai_message.mid.hex,
                "user_message_mid": user_message.mid.hex,
                "conversation": conversation_data,
                "history_messages": history_messages,
                "need_title": need_title,
            }
        )

    def append_answer(self, payload):
        cid = payload.get("cid")
        conversation = Conversation.get_or_none(Conversation.cid == cid)
        if not conversation:
            return JResponse(status=404)

        mid = payload.get("mid")
        parent_message = Message.get_or_none((Message.mid == mid) & (Message.conversation == conversation))
        if not parent_message:
            return JResponse(status=404)

        history_messages = get_history_messages(
            start_message=parent_message,
            count=None,
            all_children=False,
        )

        ai_message = Message.create(
            conversation=conversation,
            author_type=Message.AuthorTypes.ASSISTANT,
            content_type=Message.ContentTypes.TEXT,
            content={"text": ""},
            parent=parent_message,
        )

        conversation.current_message = ai_message.mid
        conversation.update_time = ai_message.create_time
        conversation.save()

        history_messages = get_history_messages(
            start_message=parent_message,
            count=None,
            all_children=False,
        )
        while len(history_messages) > 0 and history_messages[0]["author_type"] == Message.AuthorTypes.ASSISTANT:
            history_messages = history_messages[1:]
        need_title = False

        conversation_data = model_serializer(conversation)
        conversation_data["related_workflows"] = model_serializer(
            conversation.related_workflows, many=True, fields=["wid", "title", "brief"]
        )
        conversation_data["related_templates"] = model_serializer(
            conversation.related_templates, many=True, fields=["wid", "title", "brief"]
        )
        conversation_data["tool_call_data"] = {
            "workflows": [workflow.tool_call_data for workflow in conversation.related_workflows],
            "templates": [template.tool_call_data for template in conversation.related_templates],
        }

        return JResponse(
            data={
                "ai_message_mid": ai_message.mid.hex,
                "conversation": conversation_data,
                "history_messages": history_messages,
                "need_title": need_title,
            }
        )

    def done_notice(self, payload):
        mid = payload.get("mid")
        message = Message.get_or_none(Message.mid == mid)
        if not message:
            return JResponse(status=404)

        response = json.loads(cache.get(f"chat_response:{mid}"))
        message.content_type = response["content_type"]
        message.content = response["content"]
        message.metadata.update(response["metadata"])

        message.status = (
            Message.StatusTypes.WAITING_FOR_WORKFLOW
            if response["content_type"] == Message.ContentTypes.WORKFLOW
            else Message.StatusTypes.SUCCESS
        )
        message.save()

        title = response.get("conversation_title")
        if title and message.conversation.title != title:
            message.conversation.title = title
            message.conversation.update_time = datetime.now()
            message.conversation.save()

        return JResponse()

    def get(self, payload):
        mid = payload.get("mid")
        if not mid:
            return JResponse(status=400, msg="Missing 'mid' in payload")

        status, msg, message = get_user_object_general(Message, mid=mid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        return JResponse(data=model_serializer(message))

    def update(self, payload):
        mid = payload.get("mid")
        if not mid:
            return JResponse(status=400, msg="Missing 'mid' in payload")

        status, msg, message = get_user_object_general(Message, mid=mid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        content_type = payload.get("content_type")
        if content_type is not None:
            message.content_type = content_type
        status = payload.get("status")
        if status is not None:
            message.status = status

        message.save()

        return JResponse()

    def run_workflow(self, payload):
        wid = payload.get("wid")
        if not wid:
            return JResponse(status=400, msg="Missing 'wid' in payload")

        status, msg, workflow = get_user_object_general(Workflow, wid=wid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        mid = payload.get("mid")
        if not mid:
            return JResponse(status=400, msg="Missing 'mid' in payload")

        status, msg, message = get_user_object_general(Message, mid=mid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        params = payload.get("params", {})
        parameter_sources = workflow.tool_call_data.get("parameter_sources", {})

        nodes = {}
        for key, value in parameter_sources.items():
            node_id = value["node"]
            field = value["field"]

            if node_id not in nodes:
                nodes[node_id] = {}
            if params.get(key):
                nodes[node_id][field] = params[key]

        workflow_data = workflow.data
        for node_id, node_data in nodes.items():
            for original_node in workflow_data["nodes"]:
                if original_node["id"] == node_id:
                    break
            for field in node_data:
                original_node["data"]["template"][field]["value"] = node_data[field]

        record_rid = run_workflow_common(
            workflow_data=workflow_data,
            workflow=workflow,
            message=message,
            run_from=WorkflowRunRecord.RunFromTypes.CHAT,
        )

        message.metadata.update({"record_id": record_rid})
        message.status = Message.StatusTypes.RUNNING_WORKFLOW
        message.save()

        return JResponse(msg="success", data={"rid": record_rid})


class AgentAPI:
    name = "agent"

    def get(self, payload):
        aid = payload.get("aid")
        if not aid:
            return JResponse(status=400, msg="Missing 'aid' in payload")

        status, msg, agent = get_user_object_general(Agent, aid=aid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        return JResponse(data={**model_serializer(agent, manytomany=True), "is_owner": True})

    def list(self, payload):
        limit = payload.get("limit")
        if limit is not None:
            limit = int(limit)
        offset = int(payload.get("offset", 0))
        search = payload.get("search", "")

        agents_query = Agent.select()

        if search:
            agents_query = agents_query.where((Agent.name.contains(search)) | (Agent.description.contains(search)))

        total = agents_query.count()
        agents_query = agents_query.order_by(-Agent.update_time)

        if limit is not None:
            agents_query = agents_query.offset(offset).limit(limit)
        else:
            agents_query = agents_query.offset(offset)

        agents = agents_query

        return JResponse(
            data={
                "agents": model_serializer(agents, many=True, manytomany=True),
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    def create(self, payload):
        avatar = payload.get("avatar", "")
        name = payload.get("name", "")
        description = payload.get("description", "")
        settings = payload.get("settings", {})
        model_provider = payload.get("model_provider", "OpenAI")
        model = payload.get("model", "gpt-4o-mini")

        if avatar and not avatar.startswith("http://localhost"):
            avatar = static_file_server.get_static_file_url(avatar, "images/avatar")

        agent: Agent = Agent.create(
            avatar=avatar,
            name=name,
            description=description,
            settings=settings,
            model_provider=model_provider,
            model=model,
        )

        related_workflow_ids = payload.get("related_workflows", [])
        related_workflows = Workflow.select().where(Workflow.wid.in_(related_workflow_ids))
        agent.related_workflows.add(list(related_workflows))

        return JResponse(data={"aid": agent.aid.hex})

    def delete(self, payload):
        aid = payload.get("aid")
        if not aid:
            return JResponse(status=400, msg="Missing 'aid' in payload")

        status, msg, agent = get_user_object_general(Agent, aid=aid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        agent.delete_instance(recursive=True)

        return JResponse(status=200, msg="Agent deleted successfully")

    def duplicate(self, payload):
        aid = payload.get("aid")

        status, msg, original_agent = get_user_object_general(Agent, aid=aid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        new_agent = Agent.create(**{k: v for k, v in original_agent.__data__.items() if k != "aid"})

        new_agent.related_workflows.add(list(original_agent.related_workflows))

        return JResponse(data=model_serializer(new_agent, manytomany=True))

    def update(self, payload):
        aid = payload.get("aid")

        status, msg, agent = get_user_object_general(Agent, aid=aid)
        if status != 200:
            return JResponse(status=status, msg=msg)

        avatar = payload.get("avatar", "")
        if avatar and not avatar.startswith("http://localhost"):
            agent.avatar = static_file_server.get_static_file_url(avatar, "images/avatar")

        agent.name = payload.get("name", agent.name)
        agent.description = payload.get("description", agent.description)
        agent.settings = payload.get("settings", agent.settings)
        agent.model = payload.get("model", agent.model)
        agent.model_provider = payload.get("model_provider", agent.model_provider)

        agent.related_workflows.clear()
        agent.related_templates.clear()

        related_workflows = payload.get("related_workflows", [workflow.wid for workflow in agent.related_workflows])
        # related_templates = payload.get("related_templates", [template.tid for template in agent.related_templates])

        workflows = Workflow.select().where(Workflow.wid.in_(related_workflows))
        agent.related_workflows.add(list(workflows))
        agent.version += 1
        agent.update_time = datetime.now()
        agent.save()

        return JResponse(data={**model_serializer(agent, manytomany=True), "is_owner": True})


class AudioAPI:
    name = "audio"

    def transcribe(self, payload):
        audio_file = payload.get("audio_file")
        if not audio_file:
            return JResponse(status=400, msg="Missing 'audio_file' in payload")

        client = SpeechRecognitionClient()
        transcription = client.transcribe(open(audio_file, "rb"), "text")
        return JResponse(data={"transcription": transcription})
