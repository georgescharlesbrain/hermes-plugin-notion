import json
import pytest
from hermes_notion import tools
from tools.registry import ToolRegistry

@pytest.mark.parametrize("name",list(tools.SCHEMAS))
def test_registered_handler_obeys_real_registry_result_contract(name,monkeypatch):
    if name=="notion_ntn":
        from hermes_notion import ntn
        monkeypatch.setattr(ntn,"execute",lambda *a,**kw:{"ok":True,"stdout":"verified"})
        monkeypatch.setattr(tools,"_settings",lambda:None)
        args={"args":["api","v1/users/me"]}
    else:
        monkeypatch.setattr(tools,"_load_token",lambda:"")
        args={}
    registry=ToolRegistry()
    registry.register(name=name,toolset="notion",schema=tools.SCHEMAS[name],handler=tools.HANDLERS[name],check_fn=lambda:True)
    result=registry.dispatch(name,args)
    assert isinstance(result,str)
    decoded=json.loads(result)
    assert decoded.get("error_type")!="tool_result_contract"
    assert decoded.get("error")!="Tool handler returned unsupported result type: dict"
    if name=="notion_ntn":assert decoded["ok"] and decoded["stdout"]=="verified"
    else:assert decoded["error"]=="notion_not_configured"
