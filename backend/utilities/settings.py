# @Author: Bi Ying
# @Date:   2024-04-29 16:50:17
from models import model_serializer
from models import Setting as SettingModel


class Settings:
    def __init__(self):
        self.data = dict()
        self.load_setting()

    def load_setting(self):
        if SettingModel.select().count() == 0:
            setting = SettingModel.create()
        else:
            setting = SettingModel.select().order_by(SettingModel.create_time.desc()).first()
        self.data = model_serializer(setting)["data"]

    def __getattribute__(self, name: str):
        if name == "data":
            return super().__getattribute__(name)
        if name in super().__getattribute__("data"):
            return super().__getattribute__("data")[name]
        return super().__getattribute__(name)

    def get(self, name: str, default=None):
        return self.data.get(name, default)
