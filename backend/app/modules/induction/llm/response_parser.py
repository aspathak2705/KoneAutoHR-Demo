import json
import re
from app.core.exceptions import LLMResponseParseError

def parse_llm_json(content: str) -> dict:
    """
    Parses and extracts the JSON object from raw LLM output.
    1. Removes Markdown code fences (```json ... ```)
    2. Trims whitespace
    3. Locates the first '{'
    4. Locates the last '}'
    5. Extracts only that portion
    6. Parses JSON structure via json.loads
    """
    if not content or not content.strip():
        raise LLMResponseParseError("Empty response returned from LLM provider.")

    cleaned = content.strip()

    # 1. Strip markdown code block wrappers
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # 2. Extract first matching outer JSON object
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")

    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        raise LLMResponseParseError(
            f"Could not locate a valid JSON object starting with '{{' and ending with '}}' in raw content: {cleaned[:300]}..."
        )

    json_str = cleaned[start_idx:end_idx + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise LLMResponseParseError(
            f"Failed to decode extracted JSON structure. Decode Error: {str(e)}. Extracted substring: {json_str[:300]}"
        )
