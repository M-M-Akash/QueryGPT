import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class TableOutput(BaseModel):
    """Structured output for table selection."""

    tables: list[str] = Field(description="List of table names needed to answer the query")
    explanation: str = Field(description="Brief explanation of why these tables were chosen")


class TableAgent:
    """Determines which tables are needed to answer a query."""

    def __init__(self, schema_info: dict[str, Any]):
        self.schema_info = schema_info
        llm = ChatOllama(model=settings.ollama_model, base_url=settings.ollama_host)
        self.structured_llm = llm.with_structured_output(TableOutput)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a database expert that identifies which tables are needed to answer a query."),
            ("human",
             "Based on the following user query and database schema, determine which tables are needed.\n\n"
             "User Query: \"{user_query}\"\n"
             "Workspace: {workspace}\n\n"
             "Database Schema:\n{schema_text}"),
        ])

    def determine_tables(self, user_query: str, workspace: str) -> dict:
        schema_descriptions = []
        for table_name, info in self.schema_info.items():
            columns_desc = ", ".join(
                f"{c['name']} ({c['type']})" for c in info["columns"]
            )
            schema_descriptions.append(f"Table '{table_name}': {columns_desc}")

        chain = (self.prompt | self.structured_llm).with_retry(stop_after_attempt=3)
        result = chain.invoke({
            "user_query": user_query,
            "workspace": workspace,
            "schema_text": "\n".join(schema_descriptions),
        })
        return result.model_dump()
