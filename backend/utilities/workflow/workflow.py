# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 18:51:34
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-15 18:44:21
import uuid
from copy import deepcopy
from datetime import datetime
from typing import List, Dict, Any
from functools import cached_property

from models import WorkflowRunRecord, Message
from models import Workflow as WorkflowModel
from utilities.general import mprint


class DAG:
    def __init__(self):
        self.nodes = set()
        self.edges = {}

    def add_node(self, node):
        self.nodes.add(node)
        if node not in self.edges:
            self.edges[node] = set()

    def add_edge(self, start, end):
        if start not in self.nodes:
            self.add_node(start)
        if end not in self.nodes:
            self.add_node(end)
        self.edges[start].add(end)

    def get_parents(self, node):
        parents = []
        for start, ends in self.edges.items():
            if node in ends:
                parents.append(start)
        return parents

    def get_children(self, node):
        return list(self.edges[node])

    def get_all_nodes(self):
        return list(self.nodes)

    def topological_sort(self):
        in_degree = {node: 0 for node in self.nodes}
        for start, ends in self.edges.items():
            for end in ends:
                in_degree[end] += 1

        queue = [node for node, degree in in_degree.items() if degree == 0]

        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for child in self.edges[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(result) != len(self.nodes):
            raise ValueError("The graph contains cycles")

        return result


class Node:
    def __init__(self, node_data: dict):
        self.__node_data = node_data
        self.field_map = {field: data for field, data in node_data["data"]["template"].items()}

    def get_field(self, field: str) -> dict:
        return self.field_map.get(field, {})

    def update_field(self, field: str, data: dict):
        self.field_map[field] = data
        self.__node_data["data"]["template"][field] = data

    @property
    def status(self) -> int:
        return self.__node_data["data"].get("status", 0)

    @status.setter
    def status(self, status: int):
        self.__node_data["data"]["status"] = status

    @property
    def id(self) -> str:
        return self.__node_data["id"]

    @property
    def data(self) -> dict:
        return self.__node_data

    @property
    def task_name(self) -> str:
        return self.__node_data["data"]["task_name"]

    @property
    def type(self) -> str:
        return self.__node_data["type"]

    @property
    def category(self) -> str:
        return self.__node_data["category"]

    def __repr__(self) -> str:
        return f"<Node {self.type} @{self.id}>"


class Workflow:
    def __init__(self, workflow_data: dict):
        self.workflow_data = workflow_data
        if "original_workflow_data" not in workflow_data:
            self.original_workflow_data = deepcopy(workflow_data)
            self.workflow_data["original_workflow_data"] = self.original_workflow_data
        else:
            self.original_workflow_data = workflow_data["original_workflow_data"]
        self.related_workflows: dict[str, dict] = workflow_data.get("related_workflows", {})
        self.edges = [edge for edge in self.workflow_data["edges"] if not edge.get("ignored", False)]
        self.workflow_data["nodes"] = [node for node in self.workflow_data["nodes"] if not node.get("ignored", False)]
        self.__node_id_map = workflow_data.get("__node_id_map", {})
        self.nodes, self.workflow_invoke_nodes = self.parse_nodes()
        self.dag = self.create_dag()
        self.workflow_id = workflow_data.get("wid")
        self.record_id = workflow_data.get("rid")

    def parse_nodes(self):
        # 在没有【工作流调用】节点的情况下，所有节点就是原始数据中的nodes
        nodes_list: list[dict] = self.workflow_data["nodes"]
        nodes: dict[str, Node] = {}
        workflow_invoke_nodes: dict[str, Node] = {}
        while len(nodes_list) > 0:
            node = nodes_list.pop(0)
            node_obj = Node(node)
            if node_obj.type != "WorkflowInvoke":
                nodes[node["id"]] = node_obj
                continue

            # 对于【工作流调用】节点，需要将子工作流的节点和边添加到当前工作流中
            new_nodes = deepcopy(self.handle_workflow_invoke(node_obj))
            nodes_list.extend(new_nodes)
            workflow_invoke_nodes[node_obj.id] = node_obj

        # 更新原始数据中的nodes
        self.workflow_data["nodes"] = [node.data for node in nodes.values()]
        return nodes, workflow_invoke_nodes

    def handle_workflow_invoke(self, node_obj: Node) -> List[Dict]:
        """
        对【工作流调用】节点进行处理，将被调用的子工作流的节点和边添加到当前工作流中

        Args:
            node_obj (Node): 【工作流调用】节点

        Returns:
            list[dict]: 子工作流的节点列表
        """
        related_subnodes = self.get_related_subnodes(node_obj)
        subworkflow_id = node_obj.get_field("workflow_id").get("value")
        if subworkflow_id is None:
            return []
        subworkflow = self.related_workflows.get(subworkflow_id)
        if subworkflow is None:
            return []
        return self.add_subnodes_and_subedges(subworkflow, related_subnodes, node_obj)

    def get_related_subnodes(self, node_obj: Node) -> List[str]:
        """
        找出【工作流调用】节点的显示字段有哪些，并且找出字段对应的实际工作流节点 ID

        Args:
            node_obj (Node): 【工作流调用】节点

        Returns:
            list[str]: 关联的子工作流节点 ID 列表
        """
        related_subnodes = []
        for field, field_data in node_obj.field_map.items():
            if field in ("workflow_id",):
                continue
            related_subnode = field_data.get("node")
            if related_subnode is not None:
                related_subnodes.append(related_subnode)
        return related_subnodes

    def add_subnodes_and_subedges(
        self,
        subworkflow: dict,
        related_subnodes: list[str],
        node_obj: Node,
    ):
        subworkflow = deepcopy(subworkflow)
        updated_subnodes = []
        # 我们需要给节点赋值一个新ID，否则如果某个子工作流有被重复利用
        # 会导致连线同一个节点有多个连线，最终可能导致工作流图有环
        # 同时用子工作流里的节点ID加调用工作流的节点ID作为索引
        # 本质上相当于将subworkflow做了一个副本，副本里面的节点ID都是新的
        for subnode in subworkflow.get("nodes", []):
            new_id = str(uuid.uuid4())
            self.__node_id_map[subnode["id"] + node_obj.id] = new_id
            self.workflow_data["__node_id_map"] = self.__node_id_map
            updated_subnode = self.add_subnode(subnode, related_subnodes, node_obj)
            updated_subnode["id"] = new_id
            updated_subnodes.append(updated_subnode)

        # 把subworkflow的边里的source和target替换为新ID
        for edge in subworkflow.get("edges", []):
            edge["source"] = self.__node_id_map.get(edge["source"] + node_obj.id, edge["source"])
            edge["target"] = self.__node_id_map.get(edge["target"] + node_obj.id, edge["target"])
            edge["id"] = f"vueflow__edge-{edge['source']}{edge['sourceHandle']}-{edge['target']}{edge['targetHandle']}"
        self.edges.extend(subworkflow.get("edges", []))
        return updated_subnodes

    def add_subnode(
        self,
        subnode: dict,
        related_subnodes: List[str],
        node_obj: Node,
    ):
        subnode_obj = Node(subnode)
        # 如果是在【工作流调用】节点中显示的节点，不能直接将原始节点添加到当前工作流中
        # 需要将原始节点的字段的值更新为【工作流调用】节点显示的字段的值
        if subnode_obj.id in related_subnodes:
            self.update_subnode_fields(subnode_obj, node_obj)
        return subnode_obj.data

    def update_subnode_fields(self, subnode_obj: Node, node_obj: Node):
        """
        如果是在【工作流调用】节点中显示的节点，不能直接将原始节点添加到当前工作流中
        需要将原始节点的字段的值更新为【工作流调用】节点显示的字段的值

        Args:
            subnode_obj (Node): 【工作流调用】节点中显示的子工作流节点
            node_obj (Node): 【工作流调用】节点
        """
        for subnode_field, subnode_field_data in subnode_obj.field_map.items():
            if subnode_field in ("workflow_id",):
                continue
            if subnode_field not in node_obj.field_map:
                # 不在【工作流调用】节点中显示的字段，不需要更新
                continue
            subnode_field_data["value"] = node_obj.get_field(subnode_field)["value"]
            subnode_obj.update_field(subnode_field, subnode_field_data)

    def create_dag(self):
        dag = DAG()
        for edge in self.edges:
            edge = self.update_edge_nodes(edge)
            if edge is None:
                continue
            dag.add_edge(edge["source"], edge["target"])
        self.add_isolated_nodes_to_dag(dag)
        return dag

    def update_edge_nodes(self, edge: dict):
        source = edge["source"]
        target = edge["target"]
        if source in self.workflow_invoke_nodes:
            workflow_invoke_node = self.workflow_invoke_nodes[source]
            original_source_node_field = workflow_invoke_node.get_field(edge["sourceHandle"])
            original_output_field_key = original_source_node_field.get(
                "output_field_key", original_source_node_field.get("fieldName")
            )
            source = self.get_original_node(source, edge["sourceHandle"])
            if source is None:
                return None
            edge["source"] = self.__node_id_map[source + workflow_invoke_node.id]
            edge["sourceHandle"] = original_output_field_key
        if target in self.workflow_invoke_nodes:
            workflow_invoke_node = self.workflow_invoke_nodes[target]
            target = self.get_original_node(target, edge["targetHandle"])
            if target is None:
                return None
            edge["target"] = self.__node_id_map[target + workflow_invoke_node.id]
        return edge

    def get_original_node(self, node: str, handle: str):
        return self.workflow_invoke_nodes[node].get_field(handle).get("node")

    def add_isolated_nodes_to_dag(self, dag):
        all_nodes = dag.get_all_nodes()
        for node_id in self.nodes:
            node = self.get_node(node_id)
            if node is None:
                continue
            if node_id not in all_nodes and node.category not in ["triggers", "assistedNodes"]:
                dag.add_node(node_id)

    def get_sorted_task_order(self) -> list:
        nodes_order = self.dag.topological_sort()
        tasks = []
        for node_id in nodes_order:
            node = self.get_node(node_id)
            if node is None:
                continue
            task_name = node.task_name
            tasks.append(
                {
                    "node_id": node_id,
                    "task_name": task_name,
                }
            )
        return tasks

    def get_field_actual_node(self, node: Node, field_data: dict):
        if node.type != "WorkflowInvoke":
            return node
        subworkflow_id = node.get_field("workflow_id").get("value")
        if subworkflow_id is None:
            return node
        subworkflow = self.related_workflows.get(subworkflow_id)
        if subworkflow is None:
            return node
        field_key = field_data.get("field_key")
        if field_key is None:
            return node
        field_source_node_id = node.get_field(field_key).get("node")
        for subnode in subworkflow.get("nodes", []):
            subnode_obj = Node(subnode)
            if subnode_obj.id == field_source_node_id:
                return self.get_field_actual_node(subnode_obj, field_data)
        return node

    def update_original_workflow_data(self):
        """
        当存在【工作流调用】节点时，我们是将子工作流的节点和边添加到当前工作流中的。
        但最终返回给用户时不需要展开的工作流节点和边，因此需要替换为原始的节点并更新节点数据。
        """
        updated_nodes = []
        for node_data in self.original_workflow_data["nodes"]:
            original_node = Node(node_data)
            used_node = self.get_node(original_node.id)
            if used_node is not None:
                updated_nodes.append(used_node.data)
                continue
            for field, field_data in original_node.field_map.items():
                if field in ("workflow_id",):
                    continue
                actual_node = self.get_field_actual_node(original_node, {"field_key": field, **field_data})
                actual_field_data = actual_node.get_field(field)
                if len(actual_field_data) == 0:
                    actual_field_data = actual_node.get_field(field_data.get("output_field_key"))
                field_data["value"] = actual_field_data.get("value")
                original_node.update_field(field, field_data)
            updated_nodes.append(original_node.data)

        self.workflow_data["nodes"] = updated_nodes
        self.workflow_data["edges"] = self.original_workflow_data["edges"]

    def clean_workflow_data(self):
        self.workflow_data.pop("original_workflow_data", None)
        self.workflow_data.pop("related_workflows", None)
        self.workflow_data.pop("__node_id_map", None)

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def get_node_field_value(self, node_id: str, field: str, default: Any | None = None) -> Any:
        """
        如果节点有连接的边，则以边的另一端节点作为输入值，忽略节点自身的value。
        同时将获取到的值更新到节点的value中。
        If the node has a connected edge,
        the other end of the edge is used as the input value,
        ignoring the value of the node itself.
        """
        node = self.get_node(node_id)
        if node is None:
            return default
        source_node = source_handle = ""
        for edge in self.edges:
            source_node = self.get_node(edge["source"])
            if source_node is None:
                continue
            if source_node.type in ("Empty", "ButtonTrigger"):
                continue
            if edge["target"] == node_id and edge["targetHandle"] == field:
                source_node = edge["source"]
                source_handle = edge["sourceHandle"]
                break
        else:
            return node.get_field(field).get("value", default)

        source_node = self.get_node(source_node)
        if source_node is None:
            return default
        input_data = source_node.get_field(source_handle).get("value", default)
        self.update_node_field_value(node_id, field, input_data)
        return input_data

    def update_node_field_value(self, node_id: str, field: str, value):
        node = self.get_node(node_id)
        if node is None:
            return
        field_data = node.get_field(field)
        field_data.update({"value": value})
        node.update_field(field, field_data)

    def get_node_fields(self, node_id: str):
        node = self.get_node(node_id)
        if node is None:
            return []
        return node.data["data"]["template"].keys()

    def report_workflow_status(self, status: int, error_task: str = ""):
        try:
            workflow_record = WorkflowRunRecord.get(WorkflowRunRecord.rid == self.record_id)

            workflow_record.status = "FINISHED" if status == 200 else "FAILED"
            workflow_record.data = self.workflow_data
            workflow_record.data["error_task"] = error_task
            workflow_record.end_time = datetime.now()

            if workflow_record.run_from == WorkflowRunRecord.RunFromTypes.CHAT:
                source_message_mid = workflow_record.source_message
                source_message = Message.get(mid=source_message_mid)
                if source_message.status == Message.StatusTypes.RUNNING_WORKFLOW:
                    # 如果是从聊天中调用的工作流，运行完成后先更新 message
                    # If the workflow is called from a chat, update the message first after running
                    workflow_data_obj = WorkflowData(workflow_record.data)
                    output_contents = workflow_data_obj.output_contents
                    source_message.metadata["workflow_result"] = "\n\n".join(
                        [
                            f"# {output_content['title']}\n{output_content['value']}"
                            if output_content["title"]
                            else f"{output_content['value']}"
                            for output_content in output_contents
                        ]
                    )
                    source_message.status = Message.StatusTypes.SUCCESS
                    source_message.save()

            workflow_record.save()
            return True
        except Exception as e:
            mprint.error(f"report_workflow_status failed: {e}")
            return False

    def set_node_status(
        self,
        node_id: str,
        status: int,
    ):
        node = self.get_node(node_id)
        if node is None:
            return False
        node.status = status
        return True

    @property
    def data(self):
        return self.workflow_data


class WorkflowData:
    NON_FORM_TYPES = ["typography-paragraph"]

    def __init__(self, workflow_data: dict):
        self.workflow_data = workflow_data

    @cached_property
    def related_workflows(self) -> dict:
        related_workflows = {}
        for node in self.workflow_data["nodes"]:
            if node["type"] == "WorkflowInvoke":
                workflow_id = node["data"]["template"]["workflow_id"]["value"]
                workflow = WorkflowModel.get(WorkflowModel.wid == workflow_id)
                related_workflows.update(workflow.data.get("related_workflows", {}))
                related_workflows[workflow_id] = workflow.data

        return related_workflows

    def replace_workflow_invoke_nodes_ids(self, id_map: dict):
        for node in self.workflow_data["nodes"]:
            if node["type"] != "WorkflowInvoke":
                continue
            workflow_id = node["data"]["template"]["workflow_id"]["value"]
            if workflow_id not in id_map:
                continue
            node["data"]["template"]["workflow_id"]["value"] = id_map[workflow_id]
        return self.workflow_data

    @cached_property
    def ui_design(self):
        def update_node_list(nodes, unused_nodes, new_node):
            # 查找是否已经有相同id的节点
            prev_node_index = None
            for i, node in enumerate(nodes):
                if node["id"] == new_node["id"]:
                    prev_node_index = i
                    break

            # 如果找到了，替换原节点，否则追加新节点
            if prev_node_index is not None:
                nodes[prev_node_index] = new_node
            else:
                nodes.append(new_node)

            # 清理unused_nodes列表
            unused_nodes[:] = [node for node in unused_nodes if node["id"] != new_node["id"]]

        def update_field_list(fields, unused_fields, new_field):
            # 查找是否已经有相同的nodeId和fieldName的字段
            prev_field_index = None
            for i, field in enumerate(fields):
                if field.get("nodeId") == new_field["nodeId"] and field["fieldName"] == new_field["fieldName"]:
                    prev_field_index = i
                    break

            # 如果找到了，替换原字段，否则追加新字段
            if prev_field_index is not None:
                fields[prev_field_index] = new_field
            else:
                fields.append(new_field)

            # 清理unused_fields列表
            unused_fields[:] = [
                field
                for field in unused_fields
                if not (field.get("nodeId") == new_field["nodeId"] and field["fieldName"] == new_field["fieldName"])
            ]

        def remove_unused_fields(fields, unused_fields):
            for field in unused_fields:
                if "field_type" not in field or field["field_type"] not in WorkflowData.NON_FORM_TYPES:
                    fields[:] = [
                        n
                        for n in fields
                        if not (n["nodeId"] == field.get("nodeId") and n["fieldName"] == field["fieldName"])
                    ]

        def remove_unused_nodes(nodes, unused_nodes):
            for node in unused_nodes:
                if "field_type" not in node or node["field_type"] not in WorkflowData.NON_FORM_TYPES:
                    nodes[:] = [n for n in nodes if n["id"] != node["id"]]

        def has_show_fields(node):
            return any(field_data.get("show", False) for field_data in node["data"]["template"].values())

        ui = self.workflow_data.get("ui", {})
        input_fields = ui.get("inputFields", [])
        unused_input_fields = input_fields[:]
        output_nodes = ui.get("outputNodes", [])
        unused_output_nodes = output_nodes[:]
        trigger_nodes = ui.get("triggerNodes", [])
        unused_trigger_nodes = trigger_nodes[:]
        workflow_invoke_output_nodes = []

        for node in self.workflow_data.get("nodes", []):
            if node["category"] == "triggers":
                trigger_nodes.append(node)
                unused_trigger_nodes = [n for n in unused_trigger_nodes if n["id"] != node["id"]]
            elif node["category"] == "outputs":
                if node["type"] == "WorkflowInvokeOutput":
                    workflow_invoke_output_nodes.append(node)
                    continue
                # Check for visibility of the node based on its type
                elif "template" in node["data"] and not node["data"]["template"].get("show", {}).get("value", True):
                    continue
                update_node_list(output_nodes, unused_output_nodes, node)
            else:
                if not node["data"].get("has_inputs") and has_show_fields(node):
                    continue
                for field, field_data in node["data"]["template"].items():
                    if field_data.get("show"):
                        node_field = field_data.copy()
                        node_field["category"] = node["category"]
                        node_field["nodeId"] = node["id"]
                        node_field["fieldName"] = field
                        update_field_list(input_fields, unused_input_fields, node_field)

        # Remove unused fields and nodes
        remove_unused_fields(input_fields, unused_input_fields)
        remove_unused_nodes(output_nodes, unused_output_nodes)
        remove_unused_nodes(trigger_nodes, unused_trigger_nodes)

        return {
            "input_fields": input_fields,
            "output_nodes": output_nodes,
            "trigger_nodes": trigger_nodes,
            "workflow_invoke_output_nodes": workflow_invoke_output_nodes,
        }

    @cached_property
    def output_contents(self):
        output_nodes = self.ui_design["output_nodes"]
        parsed_nodes = []

        for node in output_nodes:
            parsed_node = {"type": node["type"], "title": "", "value": ""}

            if node["type"] == "Text":
                parsed_node["title"] = node["data"]["template"]["output_title"]["value"]
                parsed_node["value"] = node["data"]["template"]["text"]["value"]
            elif node["type"] == "Audio":
                parsed_node["title"] = "Audio"
                parsed_node["value"] = node["data"]["template"]["audio_url"]["value"]
            elif node["type"] == "Mindmap":
                parsed_node["title"] = "Mindmap"
                parsed_node["value"] = node["data"]["template"]["content"]["value"]
            elif node["type"] == "Mermaid":
                parsed_node["title"] = "Mermaid"
                parsed_node["value"] = node["data"]["template"]["content"]["value"]
            elif node["type"] == "Echarts":
                parsed_node["title"] = "Echarts"
                parsed_node["value"] = node["data"]["template"]["option"]["value"]
            elif node["type"] == "Table":
                parsed_node["title"] = "Table"
                parsed_node["value"] = node["data"]["template"]["option"]["value"]
            elif node["type"] == "Html":
                parsed_node["title"] = "HTML"
                parsed_node["value"] = node["data"]["template"]["output"]["value"]

            parsed_nodes.append(parsed_node)

        return parsed_nodes
