import pytest
from hermes_notion import policy, tools, notion_client, storage
from hermes_notion.settings import (
    NotionSettings, KOEN_USER_ID, AROA_BOT_INTEGRATION_ID,
    GRETA_BOT_INTEGRATION_ID, GRETA_BOT_USER_ID, GRETA_ALLOWED_ROOT_IDS
)

GRETA_ROOT_1 = "3f71c0e1-80e8-8076-be25-f9cadd5041bd"
OUTSIDE_ROOT = "5ca79d2b-9fbb-48d3-9a67-141668a70990"

def test_settings_resolves_profile_identities_and_policy():
    # Staged config with empty lists
    staged_aroa = NotionSettings.from_config({"profile": "aroa", "allowed_user_ids": [], "allowed_root_ids": []})
    assert staged_aroa.allowed_user_ids == [KOEN_USER_ID]
    assert "*" in staged_aroa.allowed_root_ids
    assert staged_aroa.bot_integration_id == AROA_BOT_INTEGRATION_ID

    # For greta
    import hermes_constants
    token = hermes_constants.set_hermes_home_override("/home/hermes/.hermes/profiles/greta")
    try:
        staged_greta = NotionSettings.from_config({"profile": "greta", "allowed_user_ids": [], "allowed_root_ids": []})
        assert staged_greta.allowed_user_ids == [KOEN_USER_ID]
        assert set(staged_greta.allowed_root_ids) == set(GRETA_ALLOWED_ROOT_IDS)
        assert staged_greta.bot_integration_id == GRETA_BOT_INTEGRATION_ID
        assert staged_greta.bot_user_id == GRETA_BOT_USER_ID
    finally:
        hermes_constants.reset_hermes_home_override(token)

def test_aroa_has_full_workspace_authority():
    decision = policy.check_mutation_gate(
        profile="aroa",
        token="fake-token",
        target_id=OUTSIDE_ROOT,
        operation="reply_comment",
        allowed_root_ids=["*"],
        allowed_user_ids=[KOEN_USER_ID],
        issuer_user_id=KOEN_USER_ID,
    )
    assert decision.allowed
    assert decision.reason in ("authorized_workspace_authority", "authorized_in_scope")

def test_greta_restricted_to_configured_roots(monkeypatch):
    monkeypatch.setattr(notion_client, "get_block", lambda t, i: {"parent": {"type": "workspace", "workspace": True}})
    # Within allowed roots
    decision_ok = policy.check_mutation_gate(
        profile="greta",
        token="fake-token",
        target_id=GRETA_ROOT_1,
        operation="reply_comment",
        allowed_root_ids=GRETA_ALLOWED_ROOT_IDS,
        allowed_user_ids=[KOEN_USER_ID],
        issuer_user_id=KOEN_USER_ID,
    )
    assert decision_ok.allowed

    # Outside allowed roots
    decision_denied = policy.check_mutation_gate(
        profile="greta",
        token="fake-token",
        target_id=OUTSIDE_ROOT,
        operation="reply_comment",
        allowed_root_ids=GRETA_ALLOWED_ROOT_IDS,
        allowed_user_ids=[KOEN_USER_ID],
        issuer_user_id=KOEN_USER_ID,
    )
    assert not decision_denied.allowed
    assert decision_denied.reason == "outside_allowed_roots"

def test_greta_wildcard_grant_rejected():
    decision = policy.check_mutation_gate(
        profile="greta",
        token="fake-token",
        target_id=OUTSIDE_ROOT,
        operation="reply_comment",
        allowed_root_ids=["*"],
    )
    assert not decision.allowed
    assert decision.reason == "wildcard_forbidden_for_profile"

def test_human_issuer_revocation():
    decision = policy.check_mutation_gate(
        profile="aroa",
        token="fake-token",
        target_id=OUTSIDE_ROOT,
        operation="reply_comment",
        allowed_root_ids=["*"],
        allowed_user_ids=[KOEN_USER_ID],
        issuer_user_id="revoked-user-id",
    )
    assert not decision.allowed
    assert decision.reason == "unauthorized_human_issuer"
