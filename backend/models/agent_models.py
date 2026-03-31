# @Author: Bi Ying
# @Date:   2024-06-06 11:18:35
import uuid
from datetime import datetime
from typing import Any, cast

from peewee import (
    UUIDField,
    CharField,
    TextField,
    IntegerField,
    BooleanField,
    DateTimeField,
    ForeignKeyField,
    ManyToManyField,
)

from models.base import BaseModel, JSONField, ManyToManyDescriptor, ModelField
from models.user_models import User
from models.workflow_models import Workflow, WorkflowTemplate


class Agent(BaseModel):
    aid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4, unique=True))
    name = cast(ModelField[str], CharField(max_length=512))
    description = cast(ModelField[str], TextField(default=""))
    avatar = cast(ModelField[str], CharField(max_length=512, default=""))
    has_published = cast(ModelField[bool], BooleanField(default=False))
    shared = cast(ModelField[bool], BooleanField(default=False))
    is_public = cast(ModelField[bool], BooleanField(default=False))
    version = cast(ModelField[int], IntegerField(default=1))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, backref="agents"))
    settings = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    model_provider = cast(ModelField[str], CharField(max_length=12))
    model = cast(ModelField[str], CharField(max_length=30))
    related_workflows = cast(ManyToManyDescriptor[Workflow], ManyToManyField(Workflow, backref="agents"))
    related_templates = cast(
        ManyToManyDescriptor[WorkflowTemplate],
        ManyToManyField(WorkflowTemplate, backref="agents"),
    )
    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))

    def __str__(self):
        return f"{self.name}-{self.aid.hex[:8]}"


class Conversation(BaseModel):
    cid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4, unique=True))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, backref="conversations"))
    title = cast(ModelField[str], CharField(max_length=512))
    settings = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    brief = cast(ModelField[str], TextField(default=""))
    shared = cast(ModelField[bool], BooleanField(default=False))
    shared_meta = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    is_public = cast(ModelField[bool], BooleanField(default=False))
    shared_at_message = cast(ModelField[uuid.UUID | None], UUIDField(null=True))
    model_provider = cast(ModelField[str], CharField(max_length=12))
    model = cast(ModelField[str], CharField(max_length=30))
    agent = cast(ModelField[Agent | None], ForeignKeyField(Agent, null=True, backref="conversations"))
    agent_version = cast(ModelField[int], IntegerField(default=1))
    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    current_message = cast(ModelField[uuid.UUID | None], UUIDField(null=True))
    related_workflows = cast(ManyToManyDescriptor[Workflow], ManyToManyField(Workflow, backref="conversations"))
    related_templates = cast(
        ManyToManyDescriptor[WorkflowTemplate],
        ManyToManyField(WorkflowTemplate, backref="conversations"),
    )

    def __str__(self):
        return self.cid.hex


class Message(BaseModel):
    class AuthorTypes:
        SYSTEM = "S"
        ASSISTANT = "A"
        USER = "U"

    class ContentTypes:
        TEXT = "TXT"
        IMAGE = "IMG"
        AUDIO = "AUD"
        VIDEO = "VID"
        FILE = "FIL"
        LINK = "LNK"
        WORKFLOW = "WKF"
        OTHER = "OTH"

    class StatusTypes:
        PENDING = "P"
        GENERATING = "G"
        SUCCESS = "S"
        FAILED = "F"
        OVERTIME = "O"
        WAITING_FOR_WORKFLOW = "W"
        RUNNING_WORKFLOW = "R"
        WORKFLOW_SUCCESS = "A"
        WORKFLOW_FAILED = "Z"

    mid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4, unique=True))
    parent = cast(ModelField["Message | None"], ForeignKeyField("self", null=True, backref="child_messages"))
    conversation = cast(ModelField[Conversation], ForeignKeyField(Conversation, backref="messages"))
    author_type = cast(ModelField[str], CharField(max_length=1, choices=AuthorTypes.__dict__.items()))
    content_type = cast(ModelField[str], CharField(max_length=3, choices=ContentTypes.__dict__.items()))
    status = cast(
        ModelField[str],
        CharField(max_length=1, choices=StatusTypes.__dict__.items(), default=StatusTypes.PENDING),
    )
    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    metadata = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    content = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    attachments = cast(ModelField[list[Any]], JSONField(default=list))

    def __str__(self):
        return self.mid.hex
