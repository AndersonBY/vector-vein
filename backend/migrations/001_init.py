"""Peewee migrations -- 001_init.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    pass


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""
    
    @migrator.create_model
    class User(pw.Model):
        uid = pw.UUIDField(primary_key=True)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()

        class Meta:
            table_name = "user"

    @migrator.create_model
    class Agent(pw.Model):
        aid = pw.UUIDField(primary_key=True)
        name = pw.CharField(max_length=512)
        description = pw.TextField(default='')
        avatar = pw.CharField(default='', max_length=512)
        has_published = pw.BooleanField(default=False)
        shared = pw.BooleanField(default=False)
        is_public = pw.BooleanField(default=False)
        version = pw.IntegerField(default=1)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True)
        settings = pw.TextField()
        model_provider = pw.CharField(max_length=12)
        model = pw.CharField(max_length=30)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()

        class Meta:
            table_name = "agent"

    @migrator.create_model
    class BaseModel(pw.Model):
        id = pw.AutoField()

        class Meta:
            table_name = "basemodel"

    @migrator.create_model
    class Conversation(pw.Model):
        cid = pw.UUIDField(primary_key=True)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True)
        title = pw.CharField(max_length=512)
        settings = pw.TextField()
        brief = pw.TextField(default='')
        shared = pw.BooleanField(default=False)
        shared_meta = pw.TextField()
        is_public = pw.BooleanField(default=False)
        shared_at_message = pw.UUIDField(null=True)
        model_provider = pw.CharField(max_length=12)
        model = pw.CharField(max_length=30)
        agent = pw.ForeignKeyField(column_name='agent_id', field='aid', model=migrator.orm['agent'], null=True)
        agent_version = pw.IntegerField(default=1)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()
        current_message = pw.UUIDField(null=True)

        class Meta:
            table_name = "conversation"

    @migrator.create_model
    class Message(pw.Model):
        mid = pw.UUIDField(primary_key=True)
        parent = pw.ForeignKeyField(column_name='parent_id', field='mid', model='self', null=True)
        conversation = pw.ForeignKeyField(column_name='conversation_id', field='cid', model=migrator.orm['conversation'])
        author_type = pw.CharField(max_length=1)
        content_type = pw.CharField(max_length=3)
        status = pw.CharField(default='P', max_length=1)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()
        metadata = pw.TextField()
        content = pw.TextField()
        attachments = pw.TextField()

        class Meta:
            table_name = "message"

    @migrator.create_model
    class Setting(pw.Model):
        id = pw.AutoField()
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True)
        data = pw.TextField()
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()

        class Meta:
            table_name = "setting"

    @migrator.create_model
    class UserVectorDatabase(pw.Model):
        id = pw.AutoField()
        vid = pw.UUIDField(unique=True)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True, on_delete='SET NULL')
        status = pw.CharField(default='CREATING', max_length=255)
        name = pw.CharField(max_length=255)
        info = pw.TextField()
        embedding_size = pw.IntegerField(default=1536)
        embedding_model = pw.CharField(default='text-embedding-ada-002', max_length=255)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()
        expire_time = pw.DateTimeField(null=True)

        class Meta:
            table_name = "user_vector_database"

    @migrator.create_model
    class UserObject(pw.Model):
        id = pw.AutoField()
        oid = pw.UUIDField(unique=True)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True, on_delete='SET NULL')
        title = pw.CharField(max_length=255)
        info = pw.TextField()
        slug_url = pw.CharField(max_length=255, null=True)
        data_type = pw.CharField(max_length=255)
        status = pw.CharField(default='VA', max_length=255)
        vector_database = pw.ForeignKeyField(column_name='vector_database_id', field='id', model=migrator.orm['user_vector_database'], on_delete='CASCADE')
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()
        source_url = pw.CharField(max_length=255, null=True)
        suffix = pw.CharField(max_length=255, null=True)
        raw_data = pw.TextField()
        embeddings = pw.TextField()

        class Meta:
            table_name = "user_object"

    @migrator.create_model
    class UserRelationalDatabase(pw.Model):
        rid = pw.UUIDField(primary_key=True)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True, on_delete='SET NULL')
        status = pw.CharField(default='CREATING', max_length=255)
        name = pw.CharField(max_length=512)
        info = pw.TextField()
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()
        expire_time = pw.DateTimeField(null=True)
        database_path = pw.CharField(max_length=1024, null=True)
        database_file_last_modified = pw.DateTimeField(null=True)

        class Meta:
            table_name = "user_relational_database"

    @migrator.create_model
    class UserRelationalTable(pw.Model):
        tid = pw.UUIDField(primary_key=True)
        database = pw.ForeignKeyField(column_name='database_id', field='rid', model=migrator.orm['user_relational_database'], on_delete='CASCADE')
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True, on_delete='SET NULL')
        name = pw.CharField(max_length=512)
        info = pw.TextField()
        status = pw.CharField(default='VA', max_length=255)
        schema = pw.TextField()
        current_rows = pw.IntegerField(default=0)
        max_rows = pw.IntegerField(default=20000)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()

        class Meta:
            table_name = "user_relational_table"

    @migrator.create_model
    class Workflow(pw.Model):
        wid = pw.UUIDField(primary_key=True)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True)
        status = pw.CharField(default='VALID', max_length=16)
        title = pw.CharField(max_length=512)
        data = pw.TextField()
        brief = pw.TextField(default='')
        images = pw.TextField()
        language = pw.CharField(max_length=16, null=True)
        version = pw.CharField(max_length=128, null=True)
        is_fast_access = pw.BooleanField(default=False)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()
        expire_time = pw.DateTimeField(null=True)

        class Meta:
            table_name = "workflow"

    @migrator.create_model
    class WorkflowRunRecord(pw.Model):
        rid = pw.UUIDField(primary_key=True)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True)
        workflow = pw.ForeignKeyField(column_name='workflow_id', field='wid', model=migrator.orm['workflow'], null=True)
        status = pw.CharField(default='QUEUED', max_length=16)
        data = pw.TextField()
        schedule_time = pw.DateTimeField(null=True)
        start_time = pw.DateTimeField()
        end_time = pw.DateTimeField(null=True)
        used_credits = pw.IntegerField(default=0)

        class Meta:
            table_name = "workflowrunrecord"

    @migrator.create_model
    class WorkflowRunSchedule(pw.Model):
        sid = pw.UUIDField(primary_key=True)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True)
        workflow = pw.ForeignKeyField(column_name='workflow_id', field='wid', model=migrator.orm['workflow'], null=True)
        status = pw.CharField(default='VALID', max_length=16)
        data = pw.TextField()
        cron_expression = pw.CharField(max_length=128, null=True)
        schedule_time = pw.DateTimeField(null=True)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()

        class Meta:
            table_name = "workflowrunschedule"

    @migrator.create_model
    class WorkflowTag(pw.Model):
        tid = pw.UUIDField(primary_key=True)
        title = pw.CharField(max_length=128)
        is_public = pw.BooleanField(default=False)
        slug_url = pw.CharField(max_length=128, null=True)
        brief = pw.TextField(null=True)
        language = pw.CharField(max_length=16, null=True)
        color = pw.CharField(default='#28c5e5', max_length=16)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True)
        status = pw.CharField(default='VA', max_length=16)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()

        class Meta:
            table_name = "workflowtag"

    @migrator.create_model
    class WorkflowTemplate(pw.Model):
        tid = pw.UUIDField(primary_key=True)
        user = pw.ForeignKeyField(column_name='user_id', field='uid', model=migrator.orm['user'], null=True)
        status = pw.CharField(default='VALID', max_length=16)
        title = pw.CharField(max_length=512)
        brief = pw.TextField(default='')
        language = pw.CharField(max_length=16, null=True)
        data = pw.TextField()
        images = pw.TextField()
        share_to_community = pw.BooleanField(default=False)
        version = pw.CharField(default='1.0.0', max_length=32)
        used_count = pw.IntegerField(default=0)
        is_official = pw.BooleanField(default=False)
        official_order = pw.IntegerField(default=0)
        create_time = pw.DateTimeField()
        update_time = pw.DateTimeField()

        class Meta:
            table_name = "workflowtemplate"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    
    migrator.remove_model('workflowtemplate')

    migrator.remove_model('workflowtag')

    migrator.remove_model('workflowrunschedule')

    migrator.remove_model('workflowrunrecord')

    migrator.remove_model('workflow')

    migrator.remove_model('user_relational_table')

    migrator.remove_model('user_relational_database')

    migrator.remove_model('user_object')

    migrator.remove_model('user_vector_database')

    migrator.remove_model('setting')

    migrator.remove_model('user')

    migrator.remove_model('message')

    migrator.remove_model('conversation')

    migrator.remove_model('basemodel')

    migrator.remove_model('agent')
