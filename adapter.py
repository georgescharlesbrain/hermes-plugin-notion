"""Top-level entry point so hermes-agent gateway discovers the adapter."""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from hermes_notion.adapter import NotionAdapter

__all__ = ["NotionAdapter"]
