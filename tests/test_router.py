import pytest
from hermes_notion.settings import NotionSettings
from hermes_notion.router import (
    evaluate_comment,
    is_terminal_acknowledgment,
    KOEN_USER_ID,
    KOEN_EMAIL,
    AROA_BOT_ID,
    GRETA_BOT_ID,
)

@pytest.fixture
def greta_settings():
    return NotionSettings(
        profile="greta",
        bot_integration_id=GRETA_BOT_ID,
        bot_user_id="bot_user_greta_456",
        mention_names=["greta", "greta@ufahamu.xyz"],
    )

@pytest.fixture
def aroa_settings():
    return NotionSettings(
        profile="aroa",
        bot_integration_id=AROA_BOT_ID,
        bot_user_id="bot_user_aroa_123",
        mention_names=["aroa", "aroa@ufahamu.xyz"],
    )

def test_is_terminal_acknowledgment():
    assert is_terminal_acknowledgment("thanks")
    assert is_terminal_acknowledgment("Thank you!")
    assert is_terminal_acknowledgment("got it")
    assert is_terminal_acknowledgment("noted")
    assert is_terminal_acknowledgment("all good")
    assert is_terminal_acknowledgment("perfect, thank you")
    assert is_terminal_acknowledgment("@greta thanks", ["greta"])
    assert is_terminal_acknowledgment("Greta thank you so much", ["greta"])

    # Non-terminal phrases
    assert not is_terminal_acknowledgment("Thanks, but can you fix the date?")
    assert not is_terminal_acknowledgment("Thank you? Is it done?")
    assert not is_terminal_acknowledgment("Please do this")
    assert not is_terminal_acknowledgment("")

def test_drop_terminal_acknowledgment(greta_settings):
    comment = {
        "id": "c_ack",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{"type": "text", "plain_text": "Thank you so much!"}]
    }
    routed = evaluate_comment(comment, greta_settings, discussion_owner="greta")
    assert not routed.actionable
    assert routed.reason == "terminal_acknowledgment"

def test_drop_self_comment_greta(greta_settings):
    comment = {
        "id": "c1",
        "discussion_id": "d1",
        "created_by": {"id": GRETA_BOT_ID},
        "rich_text": [{"type": "text", "plain_text": "Hello world"}]
    }
    routed = evaluate_comment(comment, greta_settings)
    assert not routed.actionable
    assert routed.reason == "authored_by_target_bot"

def test_drop_self_comment_aroa(aroa_settings):
    comment = {
        "id": "c1_aroa",
        "discussion_id": "d1",
        "created_by": {"id": AROA_BOT_ID},
        "rich_text": [{"type": "text", "plain_text": "Hello world"}]
    }
    routed = evaluate_comment(comment, aroa_settings)
    assert not routed.actionable
    assert routed.reason == "authored_by_target_bot"

def test_drop_unauthorized_user_addressing_aroa(aroa_settings):
    comment = {
        "id": "c2",
        "discussion_id": "d1",
        "created_by": {"id": "stranger_id_999"},
        "rich_text": [{"type": "text", "plain_text": "@aroa help me please"}]
    }
    routed = evaluate_comment(comment, aroa_settings)
    assert not routed.actionable
    assert routed.reason == "author_not_authorized"

def test_drop_unauthorized_user_addressing_greta(greta_settings):
    comment = {
        "id": "c3",
        "discussion_id": "d1",
        "created_by": {"id": "stranger_id_999"},
        "rich_text": [{"type": "text", "plain_text": "@greta help me please"}]
    }
    routed = evaluate_comment(comment, greta_settings)
    assert not routed.actionable
    assert routed.reason == "author_not_authorized"

def test_drop_bot_addressing_aroa(aroa_settings):
    # Greta bot cannot address Aroa
    comment = {
        "id": "c4",
        "discussion_id": "d1",
        "created_by": {"id": GRETA_BOT_ID, "type": "bot"},
        "display_name": {"type": "integration", "resolved_name": "greta"},
        "rich_text": [{"type": "text", "plain_text": "@aroa please answer"}]
    }
    routed = evaluate_comment(comment, aroa_settings)
    assert not routed.actionable
    assert routed.reason == "author_not_authorized"

def test_allow_aroa_addressing_greta(greta_settings):
    # Aroa bot is permitted to address Greta
    comment = {
        "id": "c5",
        "discussion_id": "d1",
        "created_by": {"id": AROA_BOT_ID, "type": "bot"},
        "display_name": {"type": "integration", "resolved_name": "aroa | pa koen"},
        "rich_text": [{"type": "text", "plain_text": "@greta please update the grocery list"}]
    }
    routed = evaluate_comment(comment, greta_settings)
    assert routed.actionable
    assert routed.reason == "addressed_at_start"

def test_allow_koen_addressing_aroa(aroa_settings):
    comment = {
        "id": "c6",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{"type": "text", "plain_text": "@aroa check my schedule"}]
    }
    routed = evaluate_comment(comment, aroa_settings)
    assert routed.actionable
    assert routed.reason == "addressed_at_start"

def test_allow_koen_addressing_greta(greta_settings):
    comment = {
        "id": "c7",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{"type": "text", "plain_text": "@greta review cleaning schedule"}]
    }
    routed = evaluate_comment(comment, greta_settings)
    assert routed.actionable
    assert routed.reason == "addressed_at_start"

def test_allow_qaren_email_addressing_greta(greta_settings):
    comment = {
        "id": "c8",
        "discussion_id": "d1",
        "created_by": {
            "id": "qaren_user_id_111",
            "type": "person",
            "person": {"email": "haelnerac@gmail.com"}
        },
        "display_name": {"type": "user", "resolved_name": "Qaren"},
        "rich_text": [{"type": "text", "plain_text": "@greta dinner options for Friday"}]
    }
    routed = evaluate_comment(comment, greta_settings)
    assert routed.actionable
    assert routed.reason == "addressed_at_start"

def test_addressed_to_greta_name_at_start(greta_settings):
    comment = {
        "id": "c9",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{"type": "text", "plain_text": "Greta, please review this"}]
    }
    routed = evaluate_comment(comment, greta_settings)
    assert routed.actionable
    assert routed.reason == "addressed_at_start"

def test_addressed_to_other_user_at_start(greta_settings):
    comment = {
        "id": "c10",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{
            "type": "mention",
            "mention": {
                "type": "user",
                "user": {"id": "user_someone_else", "name": "Someone Else"}
            },
            "plain_text": "@Someone Else"
        }, {
            "type": "text",
            "plain_text": " can you take a look?"
        }]
    }
    routed = evaluate_comment(comment, greta_settings)
    assert not routed.actionable
    assert routed.reason == "addressed_to_other_user"

def test_greta_in_middle_is_topic_not_addressed(greta_settings):
    comment = {
        "id": "c11",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{"type": "text", "plain_text": "I discussed this with Greta yesterday and she agreed."}]
    }
    routed = evaluate_comment(comment, greta_settings)
    assert not routed.actionable
    assert routed.reason == "mentioned_as_topic_not_addressed"

def test_no_mention_not_addressed_when_no_owner(greta_settings):
    comment = {
        "id": "c12",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{"type": "text", "plain_text": "Random note on this page without addressing anyone."}]
    }
    routed = evaluate_comment(comment, greta_settings, discussion_owner=None)
    assert not routed.actionable
    assert routed.reason == "not_addressed"

def test_thread_continuation_when_greta_owns_thread(greta_settings):
    comment = {
        "id": "c13",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{"type": "text", "plain_text": "Yes, please add organic milk as well."}]
    }
    routed = evaluate_comment(comment, greta_settings, discussion_owner="greta")
    assert routed.actionable
    assert routed.reason == "thread_continuation"

def test_thread_continuation_dropped_when_aroa_owns_thread(greta_settings):
    comment = {
        "id": "c14",
        "discussion_id": "d1",
        "created_by": {"id": KOEN_USER_ID, "type": "person"},
        "display_name": {"type": "user", "resolved_name": "GCB"},
        "rich_text": [{"type": "text", "plain_text": "Yes, please check the time."}]
    }
    routed = evaluate_comment(comment, greta_settings, discussion_owner="aroa")
    assert not routed.actionable
    assert routed.reason == "not_addressed"
