"""Public bridge facade; internal services raise only safe domain errors."""
from api.utils import JResponse
from knowledge_base import KnowledgeError, knowledge_service
from knowledge_base.service import ACTIONS


class KnowledgeBaseAPI:
    name = "knowledge_base"

    def _call(self, action, payload):
        try:
            return JResponse(data=knowledge_service().dispatch(action, payload))
        except KnowledgeError as error:
            return JResponse(status=error.status, data={"error_code": error.code}, msg=str(error))
        except Exception:
            return JResponse(status=500, data={"error_code": "knowledge_unavailable"},
                             msg="Knowledge storage is unavailable. Retry or restart the application.")


def _action(action):
    def invoke(self, payload):
        return self._call(action, payload)
    invoke.__name__ = action
    return invoke


for _name in ACTIONS:
    setattr(KnowledgeBaseAPI, _name, _action(_name))
