# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 14:21:40
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-18 13:16:16
def get_user_object_general(ObjectClass, **kwargs):
    if len(kwargs) == 0:
        return 500, "wrong args", {}
    try:
        object = ObjectClass.get(*[getattr(ObjectClass, key) == value for key, value in kwargs.items()])
    except ObjectClass.DoesNotExist:
        return 404, "not exist", {}
    return 200, "", object
