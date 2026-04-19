from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Natural language query")


class QueryResponse(BaseModel):
    user_query: str
    intent: dict
    tables: dict
    pruned_schema: dict
    similar_samples: list
    sql_result: dict
    execution_success: bool
    query_result: list[dict] | None = None
    execution_error: str | None = None
