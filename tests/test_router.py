import pytest
from hermes_notion.settings import NotionSettings
from hermes_notion.router import evaluate_comment

@pytest.fixture
def settings():
    return NotionSettings(
        bot_integration_id="bot_integ_123",
        bot_user_id="bot_user_456",
        mention_names=["greta", "greta@ufahamu.xyz"]
    )

def test_drop_self_comment(settings):
    comment = {
        "id": "c1",
        "discussion_id": "d1",
        "created_by": {"id": "bot_integ_123"},
        "rich_text": [{"type": "text", "plain_text": "Hello world"}]
    }
    routed = evaluate_comment(comment, settings)
    assert not routed.actionable
    assert routed.reason == "authored_by_bot"

def test_no_mention_is_actionable(settings):
    comment = {
        "id": "c2",
        "discussion_id": "d1",
        "created_by": {"id": "user_human_999"},
        "rich_text": [{"type": "text", "plain_text": "Please check the groceries for tomorrow."}]
    }
    routed = evaluate_comment(comment, settings)
    assert routed.actionable
    assert routed.reason == "no_user_addressed"

def test_addressed_to_greta_text(settings):
    comment = {
        "id": "c3",
        "discussion_id": "d1",
        "created_by": {"id": "user_human_999"},
        "rich_text": [{"type": "text", "plain_text": "Hey @greta please review this"}]
    }
    routed = evaluate_comment(comment, settings)
    assert routed.actionable
    assert routed.reason == "addressed_to_greta"

def test_addressed_to_greta_user_mention(settings):
    comment = {
        "id": "c4",
        "discussion_id": "d1",
        "created_by": {"id": "user_human_999"},
        "rich_text": [{
            "type": "mention",
            "mention": {
                "type": "user",
                "user": {"id": "bot_user_456", "name": "greta@ufahamu.xyz"}
            },
            "plain_text": "@greta@ufahamu.xyz"
        }]
    }
    routed = evaluate_comment(comment, settings)
    assert routed.actionable
    assert routed.reason == "addressed_to_greta"

def test_addressed_to_other_user_ignored(settings):
    comment = {
        "id": "c5",
        "discussion_id": "d1",
        "created_by": {"id": "user_human_999"},
        "rich_text": [{
            "type": "mention",
            "mention": {
                "type": "user",
                "user": {"id": "user_koen", "name": "Koen"}
            },
            "plain_text": "@Koen"
        }, {
            "type": "text",
            "plain_text": " can you take a look?"
        }]
    }
    routed = evaluate_comment(comment, settings)
    assert not routed.actionable
    assert routed.reason == "addressed_to_other_user"
