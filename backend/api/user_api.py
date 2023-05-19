# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-17 11:54:04
from models import (
    Setting,
    model_serializer,
)


class SettingAPI:
    name = "setting"

    def get(self, payload):
        if Setting.select().count() == 0:
            setting = Setting.create()
        else:
            setting = Setting.select().order_by(Setting.create_time.desc()).first()
        setting = model_serializer(setting)
        response = {"status": 200, "msg": "success", "data": setting}
        return response

    def update(self, payload):
        setting_id = payload.get("id")
        setting = Setting.get_by_id(setting_id)
        setting.data = payload.get("data", {})
        setting.save()
        setting = model_serializer(setting)
        response = {"status": 200, "msg": "success", "data": setting}
        return response

    def list(self, payload):
        settings = Setting.select().order_by("create_time")
        settings_list = model_serializer(settings, many=True)
        response = {"status": 200, "msg": "success", "data": settings_list}
        return response
