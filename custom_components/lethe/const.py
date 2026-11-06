"""Konstanten für die Lethe-Messenger-Integration."""

DOMAIN = "lethe"

DEFAULT_URL = "https://letheapp.de"
DEFAULT_BOT_NAME = "Home Assistant"

CONF_URL = "url"
CONF_BOT_NAME = "bot_name"
CONF_BOT_TOKEN = "bot_token"
CONF_BOT_ID = "bot_id"
CONF_BOT_FAKE_NUMBER = "bot_fake_number"
CONF_CHAT_ID = "chat_id"
CONF_USER_NAME = "user_name"

# Options: Liste von Regeln
CONF_RULES = "rules"
CONF_RULE_ID = "id"
CONF_RULE_NAME = "name"
CONF_ENTITIES = "entities"
CONF_OPERATOR = "operator"
CONF_VALUE = "value"
CONF_MESSAGE = "message"
CONF_COOLDOWN = "cooldown"
CONF_ENABLED = "enabled"
CONF_AWAY_ONLY_ENTITY = "away_only_entity"
CONF_DELETE = "delete"

OP_EQ = "eq"
OP_NE = "ne"
OP_GT = "gt"
OP_LT = "lt"
OP_CHANGED = "changed"
OPERATORS = [OP_EQ, OP_NE, OP_GT, OP_LT, OP_CHANGED]

DEFAULT_MESSAGE = "🔔 {{ name }} ist jetzt {{ state }}"

QR_TIMEOUT = 300  # Sekunden, entspricht der Gültigkeit des QR-Tokens im Backend
QR_POLL_INTERVAL = 2.5

SERVICE_SEND_MESSAGE = "send_message"
ATTR_MESSAGE = "message"
