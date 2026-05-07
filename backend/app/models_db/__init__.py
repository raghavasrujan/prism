"""SQLAlchemy ORM models — mirror ``schema.dbml``.

All tables use CHAR(36) UUIDs (via ``UUIDString``) so the schema is portable
to Postgres without change (Postgres backend can swap to native UUID later).
"""

from app.models_db.attachment import Attachment
from app.models_db.audit import AuditLog
from app.models_db.conversation import (
    Conversation,
    ConversationMcpServer,
    ConversationTool,
)
from app.models_db.custom_tool import CustomTool
from app.models_db.mcp_server import McpServer, McpToolCache
from app.models_db.message import Message
from app.models_db.provider_model import ProviderModel
from app.models_db.rate_limit import RateLimitWindow
from app.models_db.refresh_token import RefreshToken
from app.models_db.schema_meta import SchemaMeta
from app.models_db.usage import UsageDailySummary
from app.models_db.user import User

__all__ = [
    "Attachment",
    "AuditLog",
    "Conversation",
    "ConversationMcpServer",
    "ConversationTool",
    "CustomTool",
    "McpServer",
    "McpToolCache",
    "Message",
    "ProviderModel",
    "RateLimitWindow",
    "RefreshToken",
    "SchemaMeta",
    "UsageDailySummary",
    "User",
]
