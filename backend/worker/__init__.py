# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 16:56:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2025-08-05
import inspect

from worker.tasks import (
    llms,
    tools,
    output,
    triggers,
    vector_db,
    web_crawlers,
    media_editing,
    relational_db,
    control_flows,
    file_processing,
    text_processing,
    image_generation,
    media_processing,
)

# Build task functions registry for workflow execution
task_functions = {}
task_modules = [
    llms,
    tools,
    output,
    triggers,
    vector_db,
    web_crawlers,
    media_editing,
    relational_db,
    control_flows,
    file_processing,
    text_processing,
    image_generation,
    media_processing,
]

for module in task_modules:
    functions = {}
    module_name = module.__name__.split(".")[-1]
    for name, obj in inspect.getmembers(module):
        if callable(obj) and not inspect.isclass(obj) and not inspect.ismethod(obj) and obj.__class__.__name__ == "Task":
            functions[name] = obj
    task_functions[module_name] = functions

# Export task_functions for use by other modules
__all__ = ["task_functions"]
