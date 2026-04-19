import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

WORKSPACES = [
    "customer_analysis",
    "order_processing",
    "inventory_management",
    "sales_analytics",
]


class IntentOutput(BaseModel):
    """Structured output for intent detection."""

    workspaces: list[str] = Field(description="List of relevant workspaces")
    explanation: str = Field(description="Brief explanation of why these workspaces were chosen")


class IntentAgent:
    """Determines the intent / workspace of a user's natural language query."""

    def __init__(self):
        llm = ChatOllama(model=settings.ollama_model, base_url=settings.ollama_host)
        self.chain = (
            ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant that classifies user queries into workspaces."),
                ("human",
                 "Based on the following user query, determine which workspace or workspaces it belongs to.\n"
                 "The available workspaces are: {workspaces}\n\n"
                 "User Query: \"{user_query}\""),
            ])
            | llm.with_structured_output(IntentOutput)
        ).with_retry(stop_after_attempt=3)

    def determine_intent(self, user_query: str) -> dict:
        result = self.chain.invoke({
            "workspaces": ", ".join(WORKSPACES),
            "user_query": user_query,
        })
        return result.model_dump()
