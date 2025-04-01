import json
import logging
import os
import shutil
from datetime import datetime
from typing import Generic, Optional, TypeVar
from urllib.parse import urlparse
from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime, Integer, func
import chromadb
from webui_backend.internal.db import Base, get_db
from webui_backend.env import (
    DATA_DIR,
    DATABASE_URL,
    ENV,
    FRONTEND_BUILD_DIR,
    OFFLINE_MODE,
    OPEN_WEBUI_DIR,
    WEBUI_AUTH,
    WEBUI_NAME,
    STATIC_DIR,
    log,
)

# Explicitly defining variables to ensure they persist even if the import is removed
DATA_DIR = DATA_DIR
DATABASE_URL = DATABASE_URL
ENV = ENV
FRONTEND_BUILD_DIR = FRONTEND_BUILD_DIR
OFFLINE_MODE = OFFLINE_MODE
OPEN_WEBUI_DIR = OPEN_WEBUI_DIR
WEBUI_AUTH = WEBUI_AUTH
WEBUI_NAME = WEBUI_NAME
STATIC_DIR = STATIC_DIR
log = log

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1


logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

# Config helpers


def run_migrations():
    log.info("Running migrations")
    try:
        from alembic import command
        from alembic.config import Config
        alembic_cfg = Config(OPEN_WEBUI_DIR / "alembic.ini")
        migrations_path = OPEN_WEBUI_DIR / "migrations"
        alembic_cfg.set_main_option("script_location", str(migrations_path))
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        log.exception(f"Error running migrations: {e}")


run_migrations()


class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


def load_json_config():
    with open(f"{DATA_DIR}/config.json", "r") as file:
        return json.load(file)


def save_to_db(data):
    with get_db() as db:
        existing_config = db.query(Config).first()
        if not existing_config:
            new_config = Config(data=data, version=0)
            db.add(new_config)
        else:
            existing_config.data = data
            existing_config.updated_at = datetime.now()
            db.add(existing_config)
        db.commit()


def reset_config():
    with get_db() as db:
        db.query(Config).delete()
        db.commit()


# When initializing, check if config.json exists and migrate it to the database
if os.path.exists(f"{DATA_DIR}/config.json"):
    data = load_json_config()
    save_to_db(data)
    os.rename(f"{DATA_DIR}/config.json", f"{DATA_DIR}/old_config.json")

DEFAULT_CONFIG = {"version": 0, "ui": {"default_locale": "", "prompt_suggestions": [{"title": ["Help me study", "vocabulary for a college entrance exam"], "content": "Help me study vocabulary: write a sentence for me to fill in the blank, and I'll try to pick the correct option."}, {"title": ["Give me ideas", "for what to do with my kids' art"], "content": "What are 5 creative things I could do with my kids' art? I don't want to throw them away, but it's also so much clutter."}, {"title": ["Tell me a fun fact", "about the Roman Empire"], "content": "Tell me a random fun fact about the Roman Empire"}, {"title": ["Show me a code snippet", "of a website's sticky header"],
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 "content": "Show me a code snippet of a website's sticky header in CSS and JavaScript."}, {"title": ["Explain options trading", "if I'm familiar with buying and selling stocks"], "content": "Explain options trading in simple terms if I'm familiar with buying and selling stocks."}, {"title": ["Overcome procrastination", "give me tips"], "content": "Could you start by asking me about instances when I procrastinate the most and then give me some suggestions to overcome it?"}, {"title": ["Grammar check", "rewrite it for better readability "], "content": 'Check the following sentence for grammar and clarity: "[sentence]". Rewrite it for better readability while maintaining its original meaning.'}]}}


def get_config():
    with get_db() as db:
        config_entry = db.query(Config).order_by(Config.id.desc()).first()
        return config_entry.data if config_entry else DEFAULT_CONFIG


CONFIG_DATA = get_config()


def get_config_value(config_path: str):
    path_parts = config_path.split(".")
    cur_config = CONFIG_DATA
    for key in path_parts:
        if key in cur_config:
            cur_config = cur_config[key]
        else:
            return None
    return cur_config


PERSISTENT_CONFIG_REGISTRY = []


def save_config(config):
    global CONFIG_DATA, PERSISTENT_CONFIG_REGISTRY
    try:
        save_to_db(config)
        CONFIG_DATA = config

        # Trigger updates on all registered PersistentConfig entries
        for config_item in PERSISTENT_CONFIG_REGISTRY:
            config_item.update()
    except Exception as e:
        log.exception(e)
        return False
    return True


T = TypeVar("T")


class PersistentConfig(Generic[T]):
    def __init__(self, env_name: str, config_path: str, env_value: T):
        self.env_name = env_name
        self.config_path = config_path
        self.env_value = env_value
        self.config_value = get_config_value(config_path)
        if self.config_value is not None:
            log.info(f"'{env_name}' loaded from the latest database entry")
            self.value = self.config_value
        else:
            self.value = env_value
        PERSISTENT_CONFIG_REGISTRY.append(self)

    def __str__(self):
        return str(self.value)

    @property
    def __dict__(self):
        raise TypeError("PersistentConfig object cannot be converted to dict, use config_get or .value instead.")

    def __getattribute__(self, item):
        if item == "__dict__":
            raise TypeError("PersistentConfig object cannot be converted to dict, use config_get or .value instead.")
        return super().__getattribute__(item)

    def update(self):
        new_value = get_config_value(self.config_path)
        if new_value is not None:
            self.value = new_value
            log.info(f"Updated {self.env_name} to new value {self.value}")

    def save(self):
        log.info(f"Saving '{self.env_name}' to the database")
        path_parts = self.config_path.split(".")
        sub_config = CONFIG_DATA
        for key in path_parts[:-1]:
            if key not in sub_config:
                sub_config[key] = {}
            sub_config = sub_config[key]
        sub_config[path_parts[-1]] = self.value
        save_to_db(CONFIG_DATA)
        self.config_value = self.value


class AppConfig:
    _state: dict[str, PersistentConfig]

    def __init__(self):
        super().__setattr__("_state", {})

    def __setattr__(self, key, value):
        if isinstance(value, PersistentConfig):
            self._state[key] = value
        else:
            self._state[key].value = value
            self._state[key].save()

    def __getattr__(self, key):
        return self._state[key].value


# WEBUI_AUTH (Required for security)
ENABLE_API_KEY = PersistentConfig("ENABLE_API_KEY", "auth.api_key.enable", os.environ.get("ENABLE_API_KEY", "True").lower() == "true")
ENABLE_API_KEY_ENDPOINT_RESTRICTIONS = PersistentConfig("ENABLE_API_KEY_ENDPOINT_RESTRICTIONS", "auth.api_key.endpoint_restrictions", os.environ.get("ENABLE_API_KEY_ENDPOINT_RESTRICTIONS", "False").lower() == "true")
API_KEY_ALLOWED_ENDPOINTS = PersistentConfig("API_KEY_ALLOWED_ENDPOINTS", "auth.api_key.allowed_endpoints", os.environ.get("API_KEY_ALLOWED_ENDPOINTS", ""))
JWT_EXPIRES_IN = PersistentConfig("JWT_EXPIRES_IN", "auth.jwt_expiry", os.environ.get("JWT_EXPIRES_IN", "-1"))
# Static DIR
for file_path in (FRONTEND_BUILD_DIR / "static").glob("**/*"):
    if file_path.is_file():
        target_path = STATIC_DIR / file_path.relative_to((FRONTEND_BUILD_DIR / "static"))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(file_path, target_path)
        except Exception as e:
            logging.error(f"An error occurred: {e}")

frontend_favicon = FRONTEND_BUILD_DIR / "static" / "favicon.png"
if frontend_favicon.exists():
    try:
        shutil.copyfile(frontend_favicon, STATIC_DIR / "favicon.png")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

frontend_splash = FRONTEND_BUILD_DIR / "static" / "splash.png"
if frontend_splash.exists():
    try:
        shutil.copyfile(frontend_splash, STATIC_DIR / "splash.png")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

frontend_loader = FRONTEND_BUILD_DIR / "static" / "loader.js"
if frontend_loader.exists():
    try:
        shutil.copyfile(frontend_loader, STATIC_DIR / "loader.js")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

# STORAGE PROVIDER
STORAGE_PROVIDER = os.environ.get("STORAGE_PROVIDER", "local")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", None)
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", None)
S3_REGION_NAME = os.environ.get("S3_REGION_NAME", None)
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", None)
S3_KEY_PREFIX = os.environ.get("S3_KEY_PREFIX", None)
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", None)
S3_USE_ACCELERATE_ENDPOINT = os.environ.get("S3_USE_ACCELERATE_ENDPOINT", "False").lower() == "true"
S3_ADDRESSING_STYLE = os.environ.get("S3_ADDRESSING_STYLE", None)
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", None)
# File Upload DIR
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# Cache DIR
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# DIRECT CONNECTIONS
ENABLE_DIRECT_CONNECTIONS = PersistentConfig("ENABLE_DIRECT_CONNECTIONS", "direct.enable", os.environ.get("ENABLE_DIRECT_CONNECTIONS", "True").lower() == "true")
# OLLAMA_BASE_URL
ENABLE_OLLAMA_API = PersistentConfig("ENABLE_OLLAMA_API", "ollama.enable", os.environ.get("ENABLE_OLLAMA_API", "True").lower() == "true")
OLLAMA_API_BASE_URL = os.environ.get("OLLAMA_API_BASE_URL", "http://localhost:11434/api")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "")
if OLLAMA_BASE_URL:
    OLLAMA_BASE_URL = OLLAMA_BASE_URL[:-1] if OLLAMA_BASE_URL.endswith("/") else OLLAMA_BASE_URL

K8S_FLAG = os.environ.get("K8S_FLAG", "")
USE_OLLAMA_DOCKER = os.environ.get("USE_OLLAMA_DOCKER", "false")
if OLLAMA_BASE_URL == "" and OLLAMA_API_BASE_URL != "":
    OLLAMA_BASE_URL = OLLAMA_API_BASE_URL[:-4] if OLLAMA_API_BASE_URL.endswith("/api") else OLLAMA_API_BASE_URL

if ENV == "prod":
    if OLLAMA_BASE_URL == "/ollama" and not K8S_FLAG:
        if USE_OLLAMA_DOCKER.lower() == "true":
            OLLAMA_BASE_URL = "http://localhost:11434"
        else:
            OLLAMA_BASE_URL = "http://host.docker.internal:11434"
    elif K8S_FLAG:
        OLLAMA_BASE_URL = "http://ollama-service.open-webui.svc.cluster.local:11434"

OLLAMA_BASE_URLS = os.environ.get("OLLAMA_BASE_URLS", "")
OLLAMA_BASE_URLS = OLLAMA_BASE_URLS if OLLAMA_BASE_URLS != "" else OLLAMA_BASE_URL
OLLAMA_BASE_URLS = [url.strip() for url in OLLAMA_BASE_URLS.split(";")]
OLLAMA_BASE_URLS = PersistentConfig("OLLAMA_BASE_URLS", "ollama.base_urls", OLLAMA_BASE_URLS)
OLLAMA_API_CONFIGS = PersistentConfig("OLLAMA_API_CONFIGS", "ollama.api_configs", {})

# OPENAI_API
ENABLE_OPENAI_API = PersistentConfig("ENABLE_OPENAI_API", "openai.enable", os.environ.get("ENABLE_OPENAI_API", "True").lower() == "true")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_BASE_URL = os.environ.get("OPENAI_API_BASE_URL", "")
if OPENAI_API_BASE_URL == "":
    OPENAI_API_BASE_URL = "https://api.openai.com/v1"

OPENAI_API_KEYS = os.environ.get("OPENAI_API_KEYS", "")
OPENAI_API_KEYS = OPENAI_API_KEYS if OPENAI_API_KEYS != "" else OPENAI_API_KEY
OPENAI_API_KEYS = [url.strip() for url in OPENAI_API_KEYS.split(";")]
OPENAI_API_KEYS = PersistentConfig("OPENAI_API_KEYS", "openai.api_keys", OPENAI_API_KEYS)
OPENAI_API_BASE_URLS = os.environ.get("OPENAI_API_BASE_URLS", "")
OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS if OPENAI_API_BASE_URLS != "" else OPENAI_API_BASE_URL
OPENAI_API_BASE_URLS = [url.strip() if url != "" else "https://api.openai.com/v1" for url in OPENAI_API_BASE_URLS.split(";")]
OPENAI_API_BASE_URLS = PersistentConfig("OPENAI_API_BASE_URLS", "openai.api_base_urls", OPENAI_API_BASE_URLS)
OPENAI_API_CONFIGS = PersistentConfig("OPENAI_API_CONFIGS", "openai.api_configs", {})
OPENAI_API_KEY = ""
try:
    OPENAI_API_KEY = OPENAI_API_KEYS.value[OPENAI_API_BASE_URLS.value.index("https://api.openai.com/v1")]
except Exception:
    pass
OPENAI_API_BASE_URL = "https://api.openai.com/v1"

####################################
# WEBUI
####################################

WEBUI_URL = PersistentConfig("WEBUI_URL", "webui.url", "http://localhost:3000")
ENABLE_SIGNUP = PersistentConfig("ENABLE_SIGNUP", "ui.enable_signup", False if not WEBUI_AUTH else "True".lower() == "true")
ENABLE_LOGIN_FORM = PersistentConfig("ENABLE_LOGIN_FORM", "ui.ENABLE_LOGIN_FORM", "True".lower() == "true")
DEFAULT_LOCALE = PersistentConfig("DEFAULT_LOCALE", "ui.default_locale", "")
DEFAULT_MODELS = PersistentConfig("DEFAULT_MODELS", "ui.default_models", None)

DEFAULT_PROMPT_SUGGESTIONS = PersistentConfig("DEFAULT_PROMPT_SUGGESTIONS", "ui.prompt_suggestions", [{"title": ["Help me study", "vocabulary for a college entrance exam"], "content": "Help me study vocabulary: write a sentence for me to fill in the blank, and I'll try to pick the correct option."}, {"title": ["Give me ideas", "for what to do with my kids' art"], "content": "What are 5 creative things I could do with my kids' art? I don't want to throw them away, but it's also so much clutter."}, {"title": ["Tell me a fun fact", "about the Roman Empire"], "content": "Tell me a random fun fact about the Roman Empire"}, {
                                              "title": ["Show me a code snippet", "of a website's sticky header"], "content": "Show me a code snippet of a website's sticky header in CSS and JavaScript."}, {"title": ["Explain options trading", "if I'm familiar with buying and selling stocks"], "content": "Explain options trading in simple terms if I'm familiar with buying and selling stocks."}, {"title": ["Overcome procrastination", "give me tips"], "content": "Could you start by asking me about instances when I procrastinate the most and then give me some suggestions to overcome it?"}])
MODEL_ORDER_LIST = PersistentConfig("MODEL_ORDER_LIST", "ui.model_order_list", [])
DEFAULT_USER_ROLE = PersistentConfig("DEFAULT_USER_ROLE", "ui.default_user_role", "pending")
USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS = "False".lower() == "true"
USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS = "False".lower() == "true"
USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS = "False".lower() == "true"
USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS = "False".lower() == "true"
USER_PERMISSIONS_CHAT_CONTROLS = "True".lower() == "true"
USER_PERMISSIONS_CHAT_FILE_UPLOAD = "True".lower() == "true"
USER_PERMISSIONS_CHAT_DELETE = "True".lower() == "true"
USER_PERMISSIONS_CHAT_EDIT = "True".lower() == "true"
USER_PERMISSIONS_CHAT_TEMPORARY = "True".lower() == "true"
USER_PERMISSIONS_FEATURES_WEB_SEARCH = "True".lower() == "true"

USER_PERMISSIONS_FEATURES_IMAGE_GENERATION = "True".lower() == "true"

USER_PERMISSIONS_FEATURES_CODE_INTERPRETER = "True".lower() == "true"

DEFAULT_USER_PERMISSIONS = {"workspace": {"models": USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS, "knowledge": USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS, "prompts": USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS, "tools": USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS}, "chat": {"controls": USER_PERMISSIONS_CHAT_CONTROLS, "file_upload": USER_PERMISSIONS_CHAT_FILE_UPLOAD,
                                                                                                                                                                                                                                                                          "delete": USER_PERMISSIONS_CHAT_DELETE, "edit": USER_PERMISSIONS_CHAT_EDIT, "temporary": USER_PERMISSIONS_CHAT_TEMPORARY}, "features": {"web_search": USER_PERMISSIONS_FEATURES_WEB_SEARCH, "image_generation": USER_PERMISSIONS_FEATURES_IMAGE_GENERATION, "code_interpreter": USER_PERMISSIONS_FEATURES_CODE_INTERPRETER}}

USER_PERMISSIONS = PersistentConfig("USER_PERMISSIONS", "user.permissions", DEFAULT_USER_PERMISSIONS)

ENABLE_EVALUATION_ARENA_MODELS = PersistentConfig("ENABLE_EVALUATION_ARENA_MODELS", "evaluation.arena.enable", "True".lower() == "true")

EVALUATION_ARENA_MODELS = PersistentConfig("EVALUATION_ARENA_MODELS", "evaluation.arena.models", [])

DEFAULT_ARENA_MODEL = {"id": "arena-model", "name": "Arena Model", "meta": {"profile_image_url": "/favicon.png", "description": "Submit your questions to anonymous AI chatbots and vote on the best response.", "model_ids": None}}

ENABLE_ADMIN_EXPORT = "True".lower() == "true"

ENABLE_ADMIN_CHAT_ACCESS = "True".lower() == "true"

ENABLE_MESSAGE_RATING = PersistentConfig("ENABLE_MESSAGE_RATING", "ui.enable_message_rating", "True".lower() == "true")


def validate_cors_origins(origins):
    for origin in origins:
        if origin != "*":
            validate_cors_origin(origin)


def validate_cors_origin(origin):
    parsed_url = urlparse(origin)
    if parsed_url.scheme not in ["http", "https"]:
        raise ValueError(f"Invalid scheme in CORS_ALLOW_ORIGIN: '{origin}'. Only 'http' and 'https' are allowed.")
    if not parsed_url.netloc:
        raise ValueError(f"Invalid URL structure in CORS_ALLOW_ORIGIN: '{origin}'.")


CORS_ALLOW_ORIGIN = "*".split(";")

if "*" in CORS_ALLOW_ORIGIN:
    log.warning("\n\nWARNING: CORS_ALLOW_ORIGIN IS SET TO '*' - NOT RECOMMENDED FOR PRODUCTION DEPLOYMENTS.\n")

validate_cors_origins(CORS_ALLOW_ORIGIN)


class BannerModel(BaseModel):
    id: str
    type: str
    title: Optional[str] = None
    content: str
    dismissible: bool
    timestamp: int


try:
    banners = json.loads("[]")
    banners = [BannerModel(**banner) for banner in banners]
except Exception as e:
    log.exception(f"Error loading WEBUI_BANNERS: {e}")
    banners = []

WEBUI_BANNERS = PersistentConfig("WEBUI_BANNERS", "ui.banners", banners)

SHOW_ADMIN_DETAILS = PersistentConfig("SHOW_ADMIN_DETAILS", "auth.admin.show", "true".lower() == "true")

ADMIN_EMAIL = PersistentConfig("ADMIN_EMAIL", "auth.admin.email", None)

####################################
# TASKS
####################################

TASK_MODEL = PersistentConfig("TASK_MODEL", "task.model.default", "")

TASK_MODEL_EXTERNAL = PersistentConfig("TASK_MODEL_EXTERNAL", "task.model.external", "")

TITLE_GENERATION_PROMPT_TEMPLATE = PersistentConfig("TITLE_GENERATION_PROMPT_TEMPLATE", "task.title.prompt_template", "")

DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a concise, 3-5 word title with an emoji summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Use emojis that enhance understanding of the topic, but avoid quotation marks or special formatting.
- Write the title in the chat's primary language; default to English if multilingual.
- Prioritize accuracy over excessive creativity; keep it clear and simple.
### Output:
JSON format: { "title": "your concise title here" }
### Examples:
- { "title": "📉 Stock Market Trends" },
- { "title": "🍪 Perfect Chocolate Chip Recipe" },
- { "title": "Evolution of Music Streaming" },
- { "title": "Remote Work Productivity Tips" },
- { "title": "Artificial Intelligence in Healthcare" },
- { "title": "🎮 Video Game Development Insights" }
### Chat History:
<chat_history>
{{MESSAGES:END:2}}
</chat_history>"""

TAGS_GENERATION_PROMPT_TEMPLATE = PersistentConfig("TAGS_GENERATION_PROMPT_TEMPLATE", "task.tags.prompt_template", "")

DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.

### Guidelines:
- Start with high-level domains (e.g. Science, Technology, Philosophy, Arts, Politics, Business, Health, Sports, Entertainment, Education)
- Consider including relevant subfields/subdomains if they are strongly represented throughout the conversation
- If content is too short (less than 3 messages) or too diverse, use only ["General"]
- Use the chat's primary language; default to English if multilingual
- Prioritize accuracy over specificity

### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = PersistentConfig("IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE", "task.image.prompt_template", "")

DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a detailed prompt for am image generation task based on the given language and context. Describe the image as if you were explaining it to someone who cannot see it. Include relevant details, colors, shapes, and any other important elements.

### Guidelines:
- Be descriptive and detailed, focusing on the most important aspects of the image.
- Avoid making assumptions or adding information not present in the image.
- Use the chat's primary language; default to English if multilingual.
- If the image is too complex, focus on the most prominent elements.

### Output:
Strictly return in JSON format:
{
    "prompt": "Your detailed description here."
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

ENABLE_TAGS_GENERATION = PersistentConfig("ENABLE_TAGS_GENERATION", "task.tags.enable", "True".lower() == "true")

ENABLE_TITLE_GENERATION = PersistentConfig("ENABLE_TITLE_GENERATION", "task.title.enable", "True".lower() == "true")

ENABLE_SEARCH_QUERY_GENERATION = PersistentConfig("ENABLE_SEARCH_QUERY_GENERATION", "task.query.search.enable", "True".lower() == "true")

ENABLE_RETRIEVAL_QUERY_GENERATION = PersistentConfig("ENABLE_RETRIEVAL_QUERY_GENERATION", "task.query.retrieval.enable", "True".lower() == "true")

QUERY_GENERATION_PROMPT_TEMPLATE = PersistentConfig("QUERY_GENERATION_PROMPT_TEMPLATE", "task.query.prompt_template", "")

DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE = """### Task:
Analyze the chat history to determine the necessity of generating search queries, in the given language. By default, **prioritize generating 1-3 broad and relevant search queries** unless it is absolutely certain that no additional information is required. The aim is to retrieve comprehensive, updated, and valuable information even with minimal uncertainty. If no search is unequivocally needed, return an empty list.

### Guidelines:
- Respond **EXCLUSIVELY** with a JSON object. Any form of extra commentary, explanation, or additional text is strictly prohibited.
- When generating search queries, respond in the format: { "queries": ["query1", "query2"] }, ensuring each query is distinct, concise, and relevant to the topic.
- If and only if it is entirely certain that no useful results can be retrieved by a search, return: { "queries": [] }.
- Err on the side of suggesting search queries if there is **any chance** they might provide useful or updated information.
- Be concise and focused on composing high-quality search queries, avoiding unnecessary elaboration, commentary, or assumptions.
- Today's date is: {{CURRENT_DATE}}.
- Always prioritize providing actionable and broad queries that maximize informational coverage.

### Output:
Strictly return in JSON format:
{
  "queries": ["query1", "query2"]
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
"""

ENABLE_AUTOCOMPLETE_GENERATION = PersistentConfig("ENABLE_AUTOCOMPLETE_GENERATION", "task.autocomplete.enable", "True".lower() == "true")

AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = PersistentConfig("AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH", "task.autocomplete.input_max_length", int("-1"))

AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = PersistentConfig("AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE", "task.autocomplete.prompt_template", "")

DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = """### Task:
You are an autocompletion system. Continue the text in `<text>` based on the **completion type** in `<type>` and the given language.

### **Instructions**:
1. Analyze `<text>` for context and meaning.
2. Use `<type>` to guide your output:
   - **General**: Provide a natural, concise continuation.
   - **Search Query**: Complete as if generating a realistic search query.
3. Start as if you are directly continuing `<text>`. Do **not** repeat, paraphrase, or respond as a model. Simply complete the text.
4. Ensure the continuation:
   - Flows naturally from `<text>`.
   - Avoids repetition, overexplaining, or unrelated ideas.
5. If unsure, return: `{ "text": "" }`.

### **Output Rules**:
- Respond only in JSON format: `{ "text": "<your_completion>" }`.

### **Examples**:
#### Example 1:
Input:
<type>General</type>
<text>The sun was setting over the horizon, painting the sky</text>
Output:
{ "text": "with vibrant shades of orange and pink." }

#### Example 2:
Input:
<type>Search Query</type>
<text>Top-rated restaurants in</text>
Output:
{ "text": "New York City for Italian cuisine." }

---
### Context:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
<type>{{TYPE}}</type>
<text>{{PROMPT}}</text>
#### Output:
"""

TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = PersistentConfig("TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE", "task.tools.prompt_template", "")

DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = """Available Tools: {{TOOLS}}

Your task is to choose and return the correct tool(s) from the list of available tools based on the query. Follow these guidelines:

- Return only the JSON object, without any additional text or explanation.

- If no tools match the query, return an empty array:
   {
     "tool_calls": []
   }

- If one or more tools match the query, construct a JSON response containing a "tool_calls" array with objects that include:
   - "name": The tool's name.
   - "parameters": A dictionary of required parameters and their corresponding values.

The format for the JSON response is strictly:
{
  "tool_calls": [
    {"name": "toolName1", "parameters": {"key1": "value1"}},
    {"name": "toolName2", "parameters": {"key2": "value2"}}
  ]
}"""

DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE = """Your task is to reflect the speaker's likely facial expression through a fitting emoji. Interpret emotions from the message and reflect their facial expression using fitting, diverse emojis (e.g., 😊, 😢, 😡, 😱).

Message: ```{{prompt}}```"""

DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE = """You have been provided with a set of responses from various models to the latest user query: "{{prompt}}"

Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured, coherent, and adheres to the highest standards of accuracy and reliability.

Responses from models: {{responses}}"""

####################################
# Code Interpreter
####################################

ENABLE_CODE_EXECUTION = PersistentConfig("ENABLE_CODE_EXECUTION", "code_execution.enable", "True".lower() == "true")
CODE_EXECUTION_ENGINE = PersistentConfig("CODE_EXECUTION_ENGINE", "code_execution.engine", "pyodide")
CODE_EXECUTION_JUPYTER_URL = PersistentConfig("CODE_EXECUTION_JUPYTER_URL", "code_execution.jupyter.url", "")
CODE_EXECUTION_JUPYTER_AUTH = PersistentConfig("CODE_EXECUTION_JUPYTER_AUTH", "code_execution.jupyter.auth", "")
CODE_EXECUTION_JUPYTER_AUTH_TOKEN = PersistentConfig("CODE_EXECUTION_JUPYTER_AUTH_TOKEN", "code_execution.jupyter.auth_token", "")
CODE_EXECUTION_JUPYTER_AUTH_PASSWORD = PersistentConfig("CODE_EXECUTION_JUPYTER_AUTH_PASSWORD", "code_execution.jupyter.auth_password", "")
CODE_EXECUTION_JUPYTER_TIMEOUT = PersistentConfig("CODE_EXECUTION_JUPYTER_TIMEOUT", "code_execution.jupyter.timeout", 60)
ENABLE_CODE_INTERPRETER = PersistentConfig("ENABLE_CODE_INTERPRETER", "code_interpreter.enable", "True".lower() == "true")
CODE_INTERPRETER_ENGINE = PersistentConfig("CODE_INTERPRETER_ENGINE", "code_interpreter.engine", "pyodide")
CODE_INTERPRETER_PROMPT_TEMPLATE = PersistentConfig("CODE_INTERPRETER_PROMPT_TEMPLATE", "code_interpreter.prompt_template", "")
CODE_INTERPRETER_JUPYTER_URL = PersistentConfig("CODE_INTERPRETER_JUPYTER_URL", "code_interpreter.jupyter.url", "")
CODE_INTERPRETER_JUPYTER_AUTH = PersistentConfig("CODE_INTERPRETER_JUPYTER_AUTH", "code_interpreter.jupyter.auth", "")
CODE_INTERPRETER_JUPYTER_AUTH_TOKEN = PersistentConfig("CODE_INTERPRETER_JUPYTER_AUTH_TOKEN", "code_interpreter.jupyter.auth_token", "")
CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD = PersistentConfig("CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD", "code_interpreter.jupyter.auth_password", "")
CODE_INTERPRETER_JUPYTER_TIMEOUT = PersistentConfig("CODE_INTERPRETER_JUPYTER_TIMEOUT", "code_interpreter.jupyter.timeout", 60)

DEFAULT_CODE_INTERPRETER_PROMPT = """
#### Tools Available

1. **Code Interpreter**: `<code_interpreter type="code" lang="python"></code_interpreter>`
   - You have access to a Python shell that runs directly in the user's browser, enabling fast execution of code for analysis, calculations, or problem-solving.  Use it in this response.
   - The Python code you write can incorporate a wide array of libraries, handle data manipulation or visualization, perform API calls for web-related tasks, or tackle virtually any computational challenge. Use this flexibility to **think outside the box, craft elegant solutions, and harness Python's full potential**.
   - To use it, **you must enclose your code within `<code_interpreter type="code" lang="python">` XML tags** and stop right away. If you don't, the code won't execute. Do NOT use triple backticks.
   - When coding, **always aim to print meaningful outputs** (e.g., results, tables, summaries, or visuals) to better interpret and verify the findings. Avoid relying on implicit outputs; prioritize explicit and clear print statements so the results are effectively communicated to the user.
   - After obtaining the printed output, **always provide a concise analysis, interpretation, or next steps to help the user understand the findings or refine the outcome further.**
   - If the results are unclear, unexpected, or require validation, refine the code and execute it again as needed. Always aim to deliver meaningful insights from the results, iterating if necessary.
   - **If a link to an image, audio, or any file is provided in markdown format in the output, ALWAYS regurgitate word for word, explicitly display it as part of the response to ensure the user can access it easily, do NOT change the link.**
   - All responses should be communicated in the chat's primary language, ensuring seamless understanding. If the chat is multilingual, default to English for clarity.

Ensure that the tools are effectively utilized to achieve the highest-quality analysis for the user."""

####################################
# Vector Database
####################################

# Chroma
CHROMA_DATA_PATH = f"{DATA_DIR}/vector_db"
CHROMA_TENANT = chromadb.DEFAULT_TENANT
CHROMA_DATABASE = chromadb.DEFAULT_DATABASE
CHROMA_HTTP_HOST = ""
CHROMA_HTTP_PORT = 8000
CHROMA_CLIENT_AUTH_PROVIDER = ""
CHROMA_CLIENT_AUTH_CREDENTIALS = ""
CHROMA_HTTP_HEADERS = ""
if CHROMA_HTTP_HEADERS:
    CHROMA_HTTP_HEADERS = dict([pair.split("=") for pair in CHROMA_HTTP_HEADERS.split(",")])
else:
    CHROMA_HTTP_HEADERS = None
CHROMA_HTTP_SSL = "false".lower() == "true"

####################################
# Information Retrieval (RAG)
####################################

# RAG Content Extraction
CONTENT_EXTRACTION_ENGINE = PersistentConfig("CONTENT_EXTRACTION_ENGINE", "rag.CONTENT_EXTRACTION_ENGINE", "".lower())
BYPASS_EMBEDDING_AND_RETRIEVAL = PersistentConfig("BYPASS_EMBEDDING_AND_RETRIEVAL", "rag.bypass_embedding_and_retrieval", "False".lower() == "true")
RAG_TOP_K = PersistentConfig("RAG_TOP_K", "rag.top_k", int("3"))
RAG_RELEVANCE_THRESHOLD = PersistentConfig("RAG_RELEVANCE_THRESHOLD", "rag.relevance_threshold", float("0.0"))
ENABLE_RAG_HYBRID_SEARCH = PersistentConfig("ENABLE_RAG_HYBRID_SEARCH", "rag.enable_hybrid_search", "".lower() == "true")
RAG_FULL_CONTEXT = PersistentConfig("RAG_FULL_CONTEXT", "rag.full_context", "False".lower() == "true")
RAG_FILE_MAX_COUNT = PersistentConfig("RAG_FILE_MAX_COUNT", "rag.file.max_count", None if not "" else int(""))
RAG_FILE_MAX_SIZE = PersistentConfig("RAG_FILE_MAX_SIZE", "rag.file.max_size", None if not "" else int(""))
ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION = PersistentConfig("ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION", "rag.enable_web_loader_ssl_verification", "True".lower() == "true")
RAG_EMBEDDING_ENGINE = PersistentConfig("RAG_EMBEDDING_ENGINE", "rag.embedding_engine", "")
PDF_EXTRACT_IMAGES = PersistentConfig("PDF_EXTRACT_IMAGES", "rag.pdf_extract_images", "False".lower() == "true")
RAG_EMBEDDING_MODEL = PersistentConfig("RAG_EMBEDDING_MODEL", "rag.embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
log.info(f"Embedding model set: {RAG_EMBEDDING_MODEL.value}")
RAG_EMBEDDING_MODEL_AUTO_UPDATE = not OFFLINE_MODE and "True".lower() == "true"
RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE = "True".lower() == "true"
RAG_EMBEDDING_BATCH_SIZE = PersistentConfig("RAG_EMBEDDING_BATCH_SIZE", "rag.embedding_batch_size", int("1"))
RAG_RERANKING_MODEL = PersistentConfig("RAG_RERANKING_MODEL", "rag.reranking_model", "")
if RAG_RERANKING_MODEL.value != "":
    log.info(f"Reranking model set: {RAG_RERANKING_MODEL.value}")
RAG_RERANKING_MODEL_AUTO_UPDATE = not OFFLINE_MODE and "True".lower() == "true"
RAG_RERANKING_MODEL_TRUST_REMOTE_CODE = "True".lower() == "true"
RAG_TEXT_SPLITTER = PersistentConfig("RAG_TEXT_SPLITTER", "rag.text_splitter", "")
TIKTOKEN_CACHE_DIR = f"{CACHE_DIR}/tiktoken"
TIKTOKEN_ENCODING_NAME = PersistentConfig("TIKTOKEN_ENCODING_NAME", "rag.tiktoken_encoding_name", "cl100k_base")
CHUNK_SIZE = PersistentConfig("CHUNK_SIZE", "rag.chunk_size", int("1000"))
CHUNK_OVERLAP = PersistentConfig("CHUNK_OVERLAP", "rag.chunk_overlap", int("100"))

DEFAULT_RAG_TEMPLATE = """### Task:
Respond to the user query using the provided context, incorporating inline citations in the format [source_id] **only when the <source_id> tag is explicitly provided** in the context.

### Guidelines:
- If you don't know the answer, clearly state that.
- If uncertain, ask the user for clarification.
- Respond in the same language as the user's query.
- If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
- If the answer isn't present in the context but you possess the knowledge, explain this to the user and provide the answer using your own understanding.
- **Only include inline citations using [source_id] (e.g., [1], [2]) when a `<source_id>` tag is explicitly provided in the context.**
- Do not cite if the <source_id> tag is not provided in the context.
- Do not use XML tags in your response.
- Ensure citations are concise and directly related to the information provided.

### Example of Citation:
If the user asks about a specific topic and the information is found in "whitepaper.pdf" with a provided <source_id>, the response should include the citation like so:
* "According to the study, the proposed method increases efficiency by 20% [whitepaper.pdf]."
If no <source_id> is present, the response should omit the citation.

### Output:
Provide a clear and direct response to the user's query, including inline citations in the format [source_id] only when the <source_id> tag is present in the context.

<context>
{{CONTEXT}}
</context>

<user_query>
{{QUERY}}
</user_query>
"""

RAG_TEMPLATE = PersistentConfig("RAG_TEMPLATE", "rag.template", DEFAULT_RAG_TEMPLATE)
RAG_OPENAI_API_BASE_URL = PersistentConfig("RAG_OPENAI_API_BASE_URL", "rag.openai_api_base_url", OPENAI_API_BASE_URL)
RAG_OPENAI_API_KEY = PersistentConfig("RAG_OPENAI_API_KEY", "rag.openai_api_key", OPENAI_API_KEY)
RAG_OLLAMA_BASE_URL = PersistentConfig("RAG_OLLAMA_BASE_URL", "rag.ollama.url", OLLAMA_BASE_URL)
RAG_OLLAMA_API_KEY = PersistentConfig("RAG_OLLAMA_API_KEY", "rag.ollama.key", "")
ENABLE_RAG_LOCAL_WEB_FETCH = "False".lower() == "true"
YOUTUBE_LOADER_LANGUAGE = PersistentConfig("YOUTUBE_LOADER_LANGUAGE", "rag.youtube_loader_language", "en".split(","))
YOUTUBE_LOADER_PROXY_URL = PersistentConfig("YOUTUBE_LOADER_PROXY_URL", "rag.youtube_loader_proxy_url", "")
ENABLE_RAG_WEB_SEARCH = PersistentConfig("ENABLE_RAG_WEB_SEARCH", "rag.web.search.enable", "False".lower() == "true")
RAG_WEB_SEARCH_ENGINE = PersistentConfig("RAG_WEB_SEARCH_ENGINE", "rag.web.search.engine", "")
BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL = PersistentConfig("BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL", "rag.web.search.bypass_embedding_and_retrieval", "False".lower() == "true")
RAG_WEB_SEARCH_DOMAIN_FILTER_LIST = PersistentConfig("RAG_WEB_SEARCH_DOMAIN_FILTER_LIST", "rag.web.search.domain.filter_list", [])
BRAVE_SEARCH_API_KEY = PersistentConfig("BRAVE_SEARCH_API_KEY", "rag.web.search.brave_search_api_key", "")
JINA_API_KEY = PersistentConfig("JINA_API_KEY", "rag.web.search.jina_api_key", "")
PERPLEXITY_API_KEY = PersistentConfig("PERPLEXITY_API_KEY", "rag.web.search.perplexity_api_key", "")
RAG_WEB_SEARCH_RESULT_COUNT = PersistentConfig("RAG_WEB_SEARCH_RESULT_COUNT", "rag.web.search.result_count", int("3"))
RAG_WEB_SEARCH_CONCURRENT_REQUESTS = PersistentConfig("RAG_WEB_SEARCH_CONCURRENT_REQUESTS", "rag.web.search.concurrent_requests", int("10"))
RAG_WEB_LOADER_ENGINE = PersistentConfig("RAG_WEB_LOADER_ENGINE", "rag.web.loader.engine", "safe_web")
RAG_WEB_SEARCH_TRUST_ENV = PersistentConfig("RAG_WEB_SEARCH_TRUST_ENV", "rag.web.search.trust_env", "False".lower() == "true")


####################################
# Images
####################################

IMAGE_GENERATION_ENGINE = PersistentConfig("IMAGE_GENERATION_ENGINE", "image_generation.engine", "openai")
ENABLE_IMAGE_GENERATION = PersistentConfig("ENABLE_IMAGE_GENERATION", "image_generation.enable", False)
ENABLE_IMAGE_PROMPT_GENERATION = PersistentConfig("ENABLE_IMAGE_PROMPT_GENERATION", "image_generation.prompt.enable", True)
AUTOMATIC1111_BASE_URL = PersistentConfig("AUTOMATIC1111_BASE_URL", "image_generation.automatic1111.base_url", "")
AUTOMATIC1111_API_AUTH = PersistentConfig("AUTOMATIC1111_API_AUTH", "image_generation.automatic1111.api_auth", "")
AUTOMATIC1111_CFG_SCALE = PersistentConfig("AUTOMATIC1111_CFG_SCALE", "image_generation.automatic1111.cfg_scale", None)
AUTOMATIC1111_SAMPLER = PersistentConfig("AUTOMATIC1111_SAMPLER", "image_generation.automatic1111.sampler", None)
AUTOMATIC1111_SCHEDULER = PersistentConfig("AUTOMATIC1111_SCHEDULER", "image_generation.automatic1111.scheduler", None)
COMFYUI_BASE_URL = PersistentConfig("COMFYUI_BASE_URL", "image_generation.comfyui.base_url", "")
COMFYUI_API_KEY = PersistentConfig("COMFYUI_API_KEY", "image_generation.comfyui.api_key", "")

COMFYUI_DEFAULT_WORKFLOW = """
{
  "3": {
    "inputs": {
      "seed": 0,
      "steps": 20,
      "cfg": 8,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1,
      "model": [
        "4",
        0
      ],
      "positive": [
        "6",
        0
      ],
      "negative": [
        "7",
        0
      ],
      "latent_image": [
        "5",
        0
      ]
    },
    "class_type": "KSampler",
    "_meta": {
      "title": "KSampler"
    }
  },
  "4": {
    "inputs": {
      "ckpt_name": "model.safetensors"
    },
    "class_type": "CheckpointLoaderSimple",
    "_meta": {
      "title": "Load Checkpoint"
    }
  },
  "5": {
    "inputs": {
      "width": 512,
      "height": 512,
      "batch_size": 1
    },
    "class_type": "EmptyLatentImage",
    "_meta": {
      "title": "Empty Latent Image"
    }
  },
  "6": {
    "inputs": {
      "text": "Prompt",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "CLIP Text Encode (Prompt)"
    }
  },
  "7": {
    "inputs": {
      "text": "",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "CLIP Text Encode (Prompt)"
    }
  },
  "8": {
    "inputs": {
      "samples": [
        "3",
        0
      ],
      "vae": [
        "4",
        2
      ]
    },
    "class_type": "VAEDecode",
    "_meta": {
      "title": "VAE Decode"
    }
  },
  "9": {
    "inputs": {
      "filename_prefix": "ComfyUI",
      "images": [
        "8",
        0
      ]
    },
    "class_type": "SaveImage",
    "_meta": {
      "title": "Save Image"
    }
  }
}
"""

COMFYUI_WORKFLOW = PersistentConfig("COMFYUI_WORKFLOW", "image_generation.comfyui.workflow", COMFYUI_DEFAULT_WORKFLOW)
COMFYUI_WORKFLOW_NODES = PersistentConfig("COMFYUI_WORKFLOW", "image_generation.comfyui.nodes", [])
IMAGE_SIZE = PersistentConfig("IMAGE_SIZE", "image_generation.size", "512x512")
IMAGE_STEPS = PersistentConfig("IMAGE_STEPS", "image_generation.steps", 50)
IMAGE_GENERATION_MODEL = PersistentConfig("IMAGE_GENERATION_MODEL", "image_generation.model", "")

####################################
# Audio
####################################

# Transcription
WHISPER_MODEL = PersistentConfig("WHISPER_MODEL", "audio.stt.whisper_model", "base")
WHISPER_MODEL_DIR = f"{CACHE_DIR}/whisper/models"
WHISPER_MODEL_AUTO_UPDATE = not OFFLINE_MODE
AUDIO_STT_ENGINE = PersistentConfig("AUDIO_STT_ENGINE", "audio.stt.engine", "")
AUDIO_STT_MODEL = PersistentConfig("AUDIO_STT_MODEL", "audio.stt.model", "")
AUDIO_TTS_API_KEY = PersistentConfig("AUDIO_TTS_API_KEY", "audio.tts.api_key", "")
AUDIO_TTS_ENGINE = PersistentConfig("AUDIO_TTS_ENGINE", "audio.tts.engine", "")
AUDIO_TTS_MODEL = PersistentConfig("AUDIO_TTS_MODEL", "audio.tts.model", "tts-1")
AUDIO_TTS_VOICE = PersistentConfig("AUDIO_TTS_VOICE", "audio.tts.voice", "alloy")
AUDIO_TTS_SPLIT_ON = PersistentConfig("AUDIO_TTS_SPLIT_ON", "audio.tts.split_on", "punctuation")
