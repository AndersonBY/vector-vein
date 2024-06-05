# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-06 02:36:21
from models import (
    Setting,
    model_serializer,
)
from utilities.config import config


class SettingAPI:
    name = "setting"

    def get(self, payload):
        if Setting.select().count() == 0:
            setting = Setting.create()
        else:
            setting = Setting.select().order_by(Setting.create_time.desc()).first()
        setting = model_serializer(setting)
        response = {"status": 200, "msg": "success", "data": {**setting, "data_path": config.data_path}}
        return response

    def update(self, payload):
        setting_id = payload.get("id")
        setting = Setting.get_by_id(setting_id)
        setting.data = payload.get("data", {})
        setting.save()
        config.save("data_path", setting.data.get("data_path", "./data"))
        response = {"status": 200, "msg": "success", "data": model_serializer(setting)}
        return response

    def list(self, payload):
        settings = Setting.select().order_by("create_time")
        settings_list = model_serializer(settings, many=True)
        response = {"status": 200, "msg": "success", "data": settings_list}
        return response
