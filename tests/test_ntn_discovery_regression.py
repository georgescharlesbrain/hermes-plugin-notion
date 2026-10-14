from gateway.session_context import set_session_vars,clear_session_vars
from hermes_notion import guard,storage
import pytest

@pytest.mark.parametrize("name,args",[
 ("tool_describe",{"names":["notion_get_comments"]}),
 ("tool_describe",{"names":["notion_ntn"]}),
 ("skill_view",{"name":"notion:use"})
])
def test_supported_notion_tool_discovery_is_not_a_permission_denial(name,args):
    storage.set_discussion_owner("d1","greta")
    storage.set_discussion_page("d1","root")
    storage.bind_comment_discussion("c1","d1")
    marker=set_session_vars(platform="notion",chat_id="notion:page:root",message_id="c1",profile="greta")
    try:assert guard.check(name,args) is None
    finally:clear_session_vars(marker)
