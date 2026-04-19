import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class ColumnPruneOutput(BaseModel):
    """Structured output for column pruning."""

    pruned_schema: dict[str, list[str]] = Field(
        description="Mapping of table names to lists of relevant column names"
    )
    explanation: str = Field(description="Brief explanation of why these columns were chosen")


class ColumnPruneAgent:
    """Prunes irrelevant columns from selected tables."""

    def __init__(self, schema_info: dict[str, Any]):
        self.schema_info = schema_info
        llm = ChatOllama(model=settings.ollama_model, base_url=settings.ollama_host)
        self.structured_llm = llm.with_structured_output(ColumnPruneOutput)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a database expert that identifies which columns are relevant to answer a query."),
            ("human",
             "Based on the following user query and the tables that have been selected, "
             "determine which columns are relevant to answer the query.\n\n"
             "User Query: \"{user_query}\"\n\n"
             "Selected Tables Schema:\n{schema_text}\n\n"
             "For each table, return only the columns that are necessary to answer the query."),
        ])

    def prune_columns(self, user_query: str, tables: list[str]) -> dict:
        schema_descriptions = []
        for table_name in tables:
            if table_name in self.schema_info:
                columns_desc = ", ".join(
                    f"{c['name']} ({c['type']})"
                    for c in self.schema_info[table_name]["columns"]
                )
                schema_descriptions.append(f"Table '{table_name}': {columns_desc}")

        chain = (self.prompt | self.structured_llm).with_retry(stop_after_attempt=3)
        result = chain.invoke({
            "user_query": user_query,
            "schema_text": "\n".join(schema_descriptions),
        })
        return result.model_dump()
