import pytest
from hermes_notion import notion_client

def test_extract_block_text_paragraph():
    block = {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"plain_text": "Here is "},
                {"plain_text": "some selected text."}
            ]
        }
    }
    assert notion_client.extract_block_text(block) == "Here is some selected text."

def test_extract_block_text_heading():
    block = {
        "type": "heading_1",
        "heading_1": {
            "rich_text": [{"plain_text": "Project Overview"}]
        }
    }
    assert notion_client.extract_block_text(block) == "Project Overview"

def test_extract_block_text_empty():
    assert notion_client.extract_block_text({}) == ""
    assert notion_client.extract_block_text({"type": "divider", "divider": {}}) == ""
