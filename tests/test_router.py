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

def test_drop_any_bot_type(settings):
    comment = {
        "id": "c1b",
        "discussion_id": "d1",
        "created_by": {"id": "random_bot_999", "type": "bot"},
        "rich_text": [{"type": "text", "plain_text": "Bot message"}]
    }
    routed = evaluate_comment(comment, settings)
    assert not routed.actionable
    assert routed.reason == "authored_by_bot"

def test_drop_any_integration_display_type(settings):
    comment = {
        "id": "c1c",
        "discussion_id": "d1",
        "created_by": {"id": "some_user_id"},
        "display_name": {"type": "integration", "resolved_name": "some integration"},
        "rich_text": [{"type": "text", "plain_text": "Integration message"}]
    }
    routed = evaluate_comment(comment, settings)
    assert not routed.actionable
    assert routed.reason == "authored_by_bot"

def test_drop_aroa_bot_author(settings):
    comment = {
        "id": "c1d",
        "discussion_id": "d1",
        "created_by": {"id": "3f71c0e1-80e8-8148-8d4a-002761fd23b7"},
        "rich_text": [{"type": "text", "plain_text": "@greta answer please"}]
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

def test_addressed_to_greta_text_at_start(settings):
    comment = {
        "id": "c3",
        "discussion_id": "d1",
        "created_by": {"id": "user_human_999"},
        "rich_text": [{"type": "text", "plain_text": "@greta please review this"}]
    }
    routed = evaluate_comment(comment, settings)
    assert routed.actionable
    assert routed.reason == "addressed_at_start"

def test_addressed_to_greta_name_at_start(settings):
    comment = {
        "id": "c3b",
        "discussion_id": "d1",
        "created_by": {"id": "user_human_999"},
        "rich_text": [{"type": "text", "plain_text": "Greta, please review this"}]
    }
    routed = evaluate_comment(comment, settings)
    assert routed.actionable
    assert routed.reason == "addressed_at_start"

def test_greta_in_middle_is_topic_not_addressed(settings):
    comment = {
        "id": "c3c",
        "discussion_id": "d1",
        "created_by": {"id": "user_human_999"},
        "rich_text": [{"type": "text", "plain_text": "I discussed this with Greta yesterday and she agreed."}]
    }
    routed = evaluate_comment(comment, settings)
    assert not routed.actionable
    assert routed.reason == "mentioned_as_topic_not_addressed"

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
    assert routed.reason == "addressed_at_start"

def test_addressed_to_other_user_at_start(settings):
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
