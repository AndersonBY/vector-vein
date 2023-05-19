# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 18:51:34
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-16 16:53:22
from datetime import datetime

from models import WorkflowRunRecord
from utilities.print_utils import mprint_error


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

    def get_status(self) -> int:
        return self.__node_data["data"].get("status", 0)

    def update_status(self, status: int):
        self.__node_data["data"]["status"] = status

    def update_credits(self, credits: int):
        self.__node_data["data"]["credits"] = credits

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


class Workflow:
    def __init__(self, workflow_data: dict):
        self.workflow_data = workflow_data
        self.nodes = {node["id"]: Node(node) for node in workflow_data["nodes"]}
        self.edges = workflow_data["edges"]
        self.dag = DAG()
        for edge in self.edges:
            self.dag.add_edge(edge["source"], edge["target"])
        # add isolated nodes
        all_nodes = self.dag.get_all_nodes()
        for node_id in self.nodes:
            node = self.get_node(node_id)
            if node_id not in all_nodes and node.category != "triggers":
                self.dag.add_node(node_id)
        self.workflow_id = workflow_data["wid"]
        self.record_id = workflow_data["rid"]

    def get_sorted_task_order(self) -> list:
        nodes_order = self.dag.topological_sort()
        tasks = []
        for node_id in nodes_order:
            node = self.get_node(node_id)
            task_name = node.task_name
            tasks.append(
                {
                    "node_id": node_id,
                    "task_name": task_name,
                }
            )
        return tasks

    def get_node(self, node_id: str) -> Node:
        return self.nodes.get(node_id)

    def get_node_field_value(self, node_id: str, field: str):
        """
        如果节点有连接的边，则以边的另一端节点作为输入值，忽略节点自身的value。
        同时将获取到的值更新到节点的value中。
        If the node has a connected edge,
        the other end of the edge is used as the input value,
        ignoring the value of the node itself.
        """
        node = self.get_node(node_id)
        if node is None:
            return None
        source_node = source_handle = ""
        for edge in self.edges:
            source_node = self.get_node(edge["source"])
            if source_node.type == "Empty":
                continue
            if edge["target"] == node_id and edge["targetHandle"] == field:
                source_node = edge["source"]
                source_handle = edge["sourceHandle"]
                break
        else:
            return node.get_field(field).get("value")

        source_node = self.get_node(source_node)
        input_data = source_node.get_field(source_handle).get("value")
        self.update_node_field_value(node_id, field, input_data)
        return input_data

    def update_node_field_value(self, node_id: str, field: str, value):
        node = self.get_node(node_id)
        field_data = node.get_field(field)
        field_data.update({"value": value})
        node.update_field(field, field_data)

    def get_node_fields(self, node_id: str):
        node = self.get_node(node_id)
        return node.data["data"]["template"].keys()

    def report_workflow_status(self, status: int):
        try:
            workflow_obj = WorkflowRunRecord.get(WorkflowRunRecord.rid == self.record_id)
            workflow_obj.status = "FINISHED" if status == 200 else "FAILED"
            workflow_obj.data = self.workflow_data
            workflow_obj.end_time = datetime.now()
            workflow_obj.save()
            return True
        except Exception as e:
            mprint_error(f"report_workflow_status failed: {e}")
            return False

    def set_node_status(
        self,
        node_id: str,
        status: int,
    ):
        node = self.get_node(node_id)
        node.update_status(status)
        return True

    @property
    def data(self):
        return self.workflow_data

    @property
    def setting(self):
        return self.workflow_data["setting"]
