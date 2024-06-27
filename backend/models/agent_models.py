# @Author: Bi Ying
# @Date:   2024-06-06 11:18:35
import uuid
from datetime import datetime

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

from models.base import BaseModel, JSONField
from models.user_models import User
from models.workflow_models import Workflow, WorkflowTemplate


class Agent(BaseModel):
    aid = UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    name = CharField(max_length=512)
    description = TextField(default="")
    avatar = CharField(max_length=512, default="")
    has_published = BooleanField(default=False)
    shared = BooleanField(default=False)
    is_public = BooleanField(default=False)
    version = IntegerField(default=1)
    user = ForeignKeyField(User, null=True, backref="agents")
    settings = JSONField(default=dict)
    model_provider = CharField(max_length=12)
    model = CharField(max_length=30)
    related_workflows = ManyToManyField(Workflow, backref="agents")
    related_templates = ManyToManyField(WorkflowTemplate, backref="agents")
    create_time = DateTimeField(default=datetime.now)
    update_time = DateTimeField(default=datetime.now)

    def __str__(self):
        return f"{self.name}-{self.aid.hex[:8]}"


class Conversation(BaseModel):
    cid = UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    user = ForeignKeyField(User, null=True, backref="conversations")
    title = CharField(max_length=512)
    settings = JSONField(default=dict)
    brief = TextField(default="")
    shared = BooleanField(default=False)
    shared_meta = JSONField(default=dict)
    is_public = BooleanField(default=False)
    shared_at_message = UUIDField(null=True)
    model_provider = CharField(max_length=12)
    model = CharField(max_length=30)
    agent = ForeignKeyField(Agent, null=True, backref="conversations")
    agent_version = IntegerField(default=1)
    create_time = DateTimeField(default=datetime.now)
    update_time = DateTimeField(default=datetime.now)
    current_message = UUIDField(null=True)
    related_workflows = ManyToManyField(Workflow, backref="conversations")
    related_templates = ManyToManyField(WorkflowTemplate, backref="conversations")

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

    mid = UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    parent = ForeignKeyField("self", null=True, backref="child_messages")
    conversation = ForeignKeyField(Conversation, backref="messages")
    author_type = CharField(max_length=1, choices=AuthorTypes.__dict__.items())
    content_type = CharField(max_length=3, choices=ContentTypes.__dict__.items())
    status = CharField(max_length=1, choices=StatusTypes.__dict__.items(), default=StatusTypes.PENDING)
    create_time = DateTimeField(default=datetime.now)
    update_time = DateTimeField(default=datetime.now)
    metadata = JSONField(default=dict)
    content = JSONField(default=dict)
    attachments = JSONField(default=list)

    def __str__(self):
        return self.mid.hex
