import logging
from logging.config import dictConfig
from typing import Any, Optional, Dict, List, Union
from pydantic import field_validator, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

# --------------------------------------------------------
# 1. Logging Configuration
# --------------------------------------------------------
class LogConfig(BaseModel):
    LOG_LEVEL: str = "INFO"
    version: int = 1
    disable_existing_loggers: bool = False
    
    formatters: Dict[str, Any] = {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s | %(asctime)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }
    handlers: Dict[str, Any] = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    }
    loggers: Dict[str, Any] = {
        "rdl_app_logger": {"handlers": ["default"], "level": LOG_LEVEL},
    }

# --------------------------------------------------------
# 2. AI Agent Nested Configurations 
# --------------------------------------------------------
class LLMConfig(BaseModel):
    model: str = "models/gemini-1.5-flash"

class STTConfig(BaseModel):
    provider: str = "google"

class TTSConfig(BaseModel):
    provider: str = "google"

class VADConfig(BaseModel):
    provider: str = "silero"

class AgentModels(BaseModel):
    llm: LLMConfig = LLMConfig()
    stt: STTConfig = STTConfig()
    tts: TTSConfig = TTSConfig()
    vad: VADConfig = VADConfig()

class RAGConfig(BaseModel):
    collection_name: str = "rdl_products"
    embedding_model: str = "models/gemini-embedding-001"
    retrieval_k: int = 4
    llm_model: str = "models/gemini-2.5-flash"

class VoiceProcessingConfig(BaseModel):
    noise_cancellation: bool = True

class AgentSettings(BaseModel):
    name: str = "RDL Technologies AI Agent"
    instructions: str = (
        "You are the official RDL Technologies AI Agent. "
        "For all RDL-related questions, you must use the `query_rag_database` tool "
        "to fetch information from the knowledge base. For general questions, answer normally."
    )
    models: AgentModels = AgentModels()
    rag: RAGConfig = RAGConfig()
    voice_processing: VoiceProcessingConfig = VoiceProcessingConfig()

# --------------------------------------------------------
# 3. Core Application Settings (Reads from .env)
# --------------------------------------------------------
class Settings(BaseSettings):
    # --- Basic Info ---
    PROJECT_NAME: str = "RDL Sales Intelligence Platform"
    ENVIRONMENT: str = "local" # local, staging, production
    API_V1_STR: str = "/api/v1"

    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "0.0.0.0"]

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        return v
    
    # --- Database (Postgres) ---
    POSTGRES_SERVER: str = "rdl_db" 
    POSTGRES_USER: str = "rdl_admin"
    POSTGRES_PASSWORD: str = "supersecretpassword"
    POSTGRES_DB: str = "rdl_sales"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str) and v.strip():
            return v
        # Assemble string for SQLAlchemy/psycopg
        values = info.data
        return f"postgresql+psycopg://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_SERVER')}:{values.get('POSTGRES_PORT')}/{values.get('POSTGRES_DB')}"

    # --- LiveKit Streaming ---
    LIVEKIT_API_URL: str
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str
    LIVEKIT_WS_URL: str 

    # --- AI API Keys ---
    GOOGLE_API_KEY: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # --- Google OAuth (multi-account Gmail) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Override the redirect URI base for OAuth callbacks.
    # Must match an authorized redirect URI in Google Cloud Console.
    # Defaults to http://localhost:8001 (required — Google blocks private LAN IPs).
    OAUTH_REDIRECT_BASE: str = ""
    

    # --- REDIS ---
    REDIS_HOST: str = "rdl_redis"
    REDIS_PORT: int = 6379

    # --- LinkedIn Scraper ---
    LINKEDIN_EMAIL: str | None = None
    LINKEDIN_PASSWORD: str | None = None


    # --- JWT Auth ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Set True in production (HTTPS only). False allows cookies over HTTP in local dev.
    COOKIE_SECURE: bool = False

    # --- LangSmith Tracing ---
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "default"
    

    # --- Mount the Agent Settings ---
    # This automatically includes all your YAML configurations!
    AGENT: AgentSettings = AgentSettings()

    # Tells Pydantic to read from the .env file
    model_config = SettingsConfigDict(env_file=".env.local", case_sensitive=True, extra="ignore")

# --------------------------------------------------------
# 4. Initialization
# --------------------------------------------------------

try:
    log_config = LogConfig()
    dictConfig(log_config.model_dump())
except Exception as e:
    print(f"Error loading logging config: {e}")

# Instantiate settings to be imported across the app
settings = Settings()
logger = logging.getLogger("rdl_app_logger")
logger.info("✅ Unified RDL Platform Configuration Loaded Successfully.")

# 👇 ADD THIS BLOCK FOR LANGSMITH 👇
# LangChain strictly reads from os.environ, so we must push Pydantic's settings into the system env.
if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"  # Langchain expects a lowercase string 'true'
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    logger.info(f"🔎 LangSmith Tracing Enabled for project: {settings.LANGCHAIN_PROJECT}")