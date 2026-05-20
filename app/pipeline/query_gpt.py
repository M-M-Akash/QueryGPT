import asyncio
import logging
from typing import Any, AsyncIterator

import pandas as pd

from app.agents.column_prune import ColumnPruneAgent
from app.agents.intent import IntentAgent
from app.agents.sql_generator import SQLGenerator
from app.agents.table import TableAgent
from app.database.connection import get_connection
from app.database.samples import get_sample_queries
from app.database.schema import get_database_schema
from app.vectorstore.store import get_retriever, index_sample_queries, init_vectorstore

logger = logging.getLogger(__name__)


class QueryGPT:
    """Orchestrates the full NL-to-SQL conversion pipeline."""

    def __init__(self):
        self.schema_info = get_database_schema()
        self.sample_queries = get_sample_queries()

        # Initialise vector store & index samples
        init_vectorstore()
        index_sample_queries(self.sample_queries, self.schema_info)

        # Initialise agents
        self.intent_agent = IntentAgent()
        self.table_agent = TableAgent(self.schema_info)
        self.column_prune_agent = ColumnPruneAgent(self.schema_info)
        self.sql_generator = SQLGenerator(self.schema_info, get_retriever())

    def prepare_query(self, user_query: str) -> dict[str, Any]:
        """Run intent + table detection and return suggested tables for user confirmation."""
        # Step 1: Determine intent
        intent_result = self.intent_agent.determine_intent(user_query)
        workspace = intent_result["workspaces"][0]
        logger.info("Intent detected: %s", workspace)

        # Step 2: Determine tables
        table_result = self.table_agent.determine_tables(user_query, workspace)
        tables = table_result["tables"]
        logger.info("Tables identified: %s", ", ".join(tables))

        return {
            "user_query": user_query,
            "intent": intent_result,
            "suggested_tables": tables,
            "table_explanation": table_result.get("explanation", ""),
        }

    def execute_query(self, user_query: str, intent: dict[str, Any], confirmed_tables: list[str]) -> dict[str, Any]:
        """Run the full pipeline using pre-confirmed tables."""
        results: dict[str, Any] = {"user_query": user_query}
        workspace = intent["workspaces"][0]
        results["intent"] = intent
        results["tables"] = {"tables": confirmed_tables}

        # Step 3: Prune columns
        column_result = self.column_prune_agent.prune_columns(user_query, confirmed_tables)
        pruned_schema = column_result["pruned_schema"]
        results["pruned_schema"] = column_result
        logger.info("Pruned schema tables: %s", ", ".join(pruned_schema))

        # Step 4: Find similar sample queries (RAG)
        similar_samples = self.sql_generator.find_similar_samples(user_query)
        results["similar_samples"] = similar_samples
        logger.info("Found %d similar query examples", len(similar_samples))

        # Step 5: Generate SQL
        sql_result = self.sql_generator.generate_sql(
            user_query, workspace, confirmed_tables, pruned_schema, similar_samples
        )
        results["sql_result"] = sql_result
        logger.info("Generated SQL: %s", sql_result.get("sql"))

        # Step 6: Execute query
        try:
            with get_connection() as conn:
                df = pd.read_sql_query(sql_result["sql"], conn)
            results["execution_success"] = True
            results["query_result"] = df.head(10).to_dict(orient="records")
            logger.info("Query executed successfully, %d rows returned", len(df))
        except Exception as exc:
            results["execution_success"] = False
            results["execution_error"] = str(exc)
            logger.error("Query execution failed: %s", exc)

        return results

    def generate_query(self, user_query: str) -> dict[str, Any]:
        """Process a natural language query end-to-end (legacy single-step path)."""
        prepared = self.prepare_query(user_query)
        return self.execute_query(
            user_query,
            prepared["intent"],
            prepared["suggested_tables"],
        )

    async def astream_execute(self, user_query: str, intent: dict[str, Any], confirmed_tables: list[str]) -> AsyncIterator[dict[str, Any]]:
        """
        Stream the execution half of the pipeline (columns → samples → SQL tokens)
        using pre-confirmed intent and tables from /query/prepare.

        Event shapes
        ------------
        {"event": "columns", "data": {...}}
        {"event": "samples", "data": [...]}
        {"event": "token",   "data": "<str>"}
        {"event": "done",    "data": {}}
        {"event": "error",   "data": "<str>"}
        """
        try:
            # Step 3: prune columns (synchronous → thread)
            column_result = await asyncio.to_thread(
                self.column_prune_agent.prune_columns, user_query, confirmed_tables
            )
            pruned_schema = column_result["pruned_schema"]
            yield {"event": "columns", "data": pruned_schema}

            # Step 4: RAG retrieval (synchronous → thread)
            similar_samples = await asyncio.to_thread(
                self.sql_generator.find_similar_samples, user_query
            )
            yield {"event": "samples", "data": similar_samples}

            # Step 5: stream SQL generation tokens
            async for token in self.sql_generator.astream_sql(
                user_query, pruned_schema, similar_samples
            ):
                yield {"event": "token", "data": token}

            yield {"event": "done", "data": {}}

        except Exception as exc:
            logger.exception("Streaming execute error")
            yield {"event": "error", "data": str(exc)}

    async def astream_query(self, user_query: str) -> AsyncIterator[dict[str, Any]]:
        """
        Run the pipeline and yield SSE-style progress events.

        Event shapes
        ------------
        {"event": "intent",   "data": {...}}
        {"event": "tables",   "data": [...]}
        {"event": "columns",  "data": {...}}
        {"event": "samples",  "data": [...]}
        {"event": "token",    "data": "<str>"}   ← streamed LLM tokens
        {"event": "done",     "data": {}}
        {"event": "error",    "data": "<str>"}
        """
        try:
            # Steps 1-2 are synchronous – run in a thread so the event loop is not blocked
            prepared = await asyncio.to_thread(self.prepare_query, user_query)
            yield {"event": "intent", "data": prepared["intent"]}
            yield {"event": "tables", "data": prepared["suggested_tables"]}

            workspace = prepared["intent"]["workspaces"][0]
            confirmed_tables = prepared["suggested_tables"]

            # Step 3: prune columns (synchronous)
            column_result = await asyncio.to_thread(
                self.column_prune_agent.prune_columns, user_query, confirmed_tables
            )
            pruned_schema = column_result["pruned_schema"]
            yield {"event": "columns", "data": pruned_schema}

            # Step 4: RAG retrieval (synchronous)
            similar_samples = await asyncio.to_thread(
                self.sql_generator.find_similar_samples, user_query
            )
            yield {"event": "samples", "data": similar_samples}

            # Step 5: stream SQL generation tokens
            async for token in self.sql_generator.astream_sql(
                user_query, pruned_schema, similar_samples
            ):
                yield {"event": "token", "data": token}

            yield {"event": "done", "data": {}}

        except Exception as exc:
            logger.exception("Streaming pipeline error")
            yield {"event": "error", "data": str(exc)}
