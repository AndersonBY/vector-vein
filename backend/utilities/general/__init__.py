# @Author: Bi Ying
# @Date:   2024-06-09 12:02:10
from .print_utils import LogServer, mprint_with_name, mprint
from .ratelimit import add_request_record, clear_expired_records, is_request_allowed
from .retry import Retry


def align_elements(input_data):
    """
    将输入的列表或元组中的每个元素拉齐到同样的长度。

    ### 情况1
    `print(align_elements(("a", "b")))`
    > 输出: (False, (['a'], ['b']))

    ### 情况2
    `print(align_elements(("a", ["b1", "b2"])))`
    > 输出: (True, (['a'], ['b1', 'b2']))

    ### 情况3
    `print(align_elements((["a", "a"], ["b1", "b2"])))`
    > 输出: (True, (['a', 'a'], ['b1', 'b2']))

    参数:
    input_data (tuple): 包含字符串或列表的元组。

    返回:
    tuple: 包含一个布尔值和拉齐后的元素元组。
           - 布尔值表示输入中是否包含列表/元组。
           - 拉齐后的元素元组。
    """
    # 检查输入是否包含列表/元组
    has_list = any(isinstance(item, list) or isinstance(item, tuple) for item in input_data)

    # 找到最长的列表长度
    max_length = max(len(item) if isinstance(item, list) else 1 for item in input_data)

    # 将所有元素拉齐到同样的长度
    outputs = []
    for item in input_data:
        if isinstance(item, list):
            # 如果元素是列表，直接使用
            outputs.append(item + [item[0]] * (max_length - len(item)) if len(item) < max_length else item)
        else:
            # 如果元素不是列表，重复元素以达到最大长度
            outputs.append([item] * max_length)

    return has_list, tuple(outputs)


__all__ = [
    "Retry",
    "mprint",
    "LogServer",
    "align_elements",
    "mprint_with_name",
    "add_request_record",
    "is_request_allowed",
    "clear_expired_records",
]
