import logging
from typing import Any, AsyncIterator

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class SQLOutput(BaseModel):
    """Structured output for SQL generation."""

    sql: str = Field(description="The generated SQL query")
    explanation: str = Field(description="Step-by-step explanation of how the query works")


class SQLGenerator:
    """Generates SQL from natural language using LLM with RAG-based few-shot examples."""

    def __init__(self, schema_info: dict[str, Any], retriever):
        self.schema_info = schema_info
        self.retriever = retriever
        llm = ChatOllama(model=settings.ollama_model, base_url=settings.ollama_host, temperature=0, num_ctx=settings.ollama_num_ctx)
        self.structured_llm = llm.with_structured_output(SQLOutput)
        # Keep a plain (non-structured) LLM instance for token streaming
        self.streaming_llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0,
            num_ctx=settings.ollama_num_ctx,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert SQL query generator. Your task is to convert "
             "natural language questions into accurate SQL queries."),
            ("human",
             "Database Schema:\n{schema_text}\n\n"
             "Here are some examples of questions and their corresponding SQL queries:\n"
             "{samples_text}\n\n"
             "Now, generate an SQL query for the following question:\n"
             "Question: {user_query}"),
        ])

    def find_similar_samples(self, user_query: str) -> list[str]:
        """Retrieve similar sample queries from the vector store."""
        results = self.retriever.retrieve(user_query)
        return [r.node.text for r in results]

    def _build_schema_text(self, pruned_schema: dict[str, list[str]]) -> str:
        schema_text = ""
        for table_name, columns in pruned_schema.items():
            if table_name not in self.schema_info:
                continue
            column_info = [
                col
                for col in self.schema_info[table_name]["columns"]
                if col["name"] in columns
            ]
            column_desc = ", ".join(f"{c['name']} ({c['type']})" for c in column_info)
            schema_text += f"Table '{table_name}': {column_desc}\n"
        return schema_text

    def _build_samples_text(self, similar_samples: list[str]) -> str:
        samples_text = ""
        for i, sample in enumerate(similar_samples):
            samples_text += f"Example {i + 1}:\n{sample}\n\n"
        return samples_text

    def generate_sql(
        self,
        user_query: str,
        workspace: str,
        tables: list[str],
        pruned_schema: dict[str, list[str]],
        similar_samples: list[str],
    ) -> dict:
        """Generate SQL query using LLM."""
        schema_text = self._build_schema_text(pruned_schema)
        samples_text = self._build_samples_text(similar_samples)

        chain = (self.prompt | self.structured_llm).with_retry(stop_after_attempt=3)
        result = chain.invoke({
            "schema_text": schema_text,
            "samples_text": samples_text,
            "user_query": user_query,
        })
        return result.model_dump()

    async def astream_sql(
        self,
        user_query: str,
        pruned_schema: dict[str, list[str]],
        similar_samples: list[str],
    ) -> AsyncIterator[str]:
        """Stream raw LLM tokens for SQL generation one chunk at a time."""
        schema_text = self._build_schema_text(pruned_schema)
        samples_text = self._build_samples_text(similar_samples)

        chain = self.prompt | self.streaming_llm
        async for chunk in chain.astream({
            "schema_text": schema_text,
            "samples_text": samples_text,
            "user_query": user_query,
        }):
            if chunk.content:
                yield chunk.content
