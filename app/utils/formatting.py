import json

from app.config import settings


def format_llm_output(llm_output: str) -> dict:
    """Parse LLM output string into a dictionary.

    Tries direct JSON parsing first, then falls back to extracting
    a JSON object from within the string.
    """
    try:
        return json.loads(llm_output)
    except json.JSONDecodeError:
        pass

    start_idx = llm_output.find("{")
    end_idx = llm_output.rfind("}")
    if start_idx != -1 and end_idx != -1:
        extracted = llm_output[start_idx : end_idx + 1]
        try:
            return json.loads(extracted)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse LLM output: {exc}") from exc

    raise ValueError("LLM output is not valid JSON and could not be parsed.")
