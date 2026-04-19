import logging
from typing import Any

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

    def generate_query(self, user_query: str) -> dict[str, Any]:
        """Process a natural language query and return generated SQL + results."""
        results: dict[str, Any] = {"user_query": user_query}

        # Step 1: Determine intent
        intent_result = self.intent_agent.determine_intent(user_query)
        workspace = intent_result["workspaces"][0]
        results["intent"] = intent_result
        logger.info("Intent detected: %s", workspace)

        # Step 2: Determine tables
        table_result = self.table_agent.determine_tables(user_query, workspace)
        tables = table_result["tables"]
        results["tables"] = table_result
        logger.info("Tables identified: %s", ", ".join(tables))

        # Step 3: Prune columns
        column_result = self.column_prune_agent.prune_columns(user_query, tables)
        pruned_schema = column_result["pruned_schema"]
        results["pruned_schema"] = column_result
        logger.info("Pruned schema tables: %s", ", ".join(pruned_schema))

        # Step 4: Find similar sample queries (RAG)
        similar_samples = self.sql_generator.find_similar_samples(user_query)
        results["similar_samples"] = similar_samples
        logger.info("Found %d similar query examples", len(similar_samples))

        # Step 5: Generate SQL
        sql_result = self.sql_generator.generate_sql(
            user_query, workspace, tables, pruned_schema, similar_samples
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
