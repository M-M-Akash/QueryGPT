import os
from pathlib import Path

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama — configure via .env
    ollama_host: str
    ollama_model: str
    ollama_embed_model: str
    ollama_num_ctx: int = 8192  # default context window (Ollama defaults to 2048 which is too small)

    # Neo4j — configure via .env
    neo4j_url: str
    neo4j_username: str
    neo4j_password: str
    neo4j_embedding_dimension: int

    # SQLite — configure via .env
    database_path: str

    # App — optional, these defaults are intentional
    log_level: str = "INFO"
    similarity_top_k: int = 2

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
