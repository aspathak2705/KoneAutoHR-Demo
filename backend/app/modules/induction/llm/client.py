import time
from typing import Callable, Optional
from loguru import logger
from app.core.config import settings
from app.core.exceptions import (
    LLMConnectionError,
    LLMResponseParseError,
    LLMResponseValidationError,
    InvalidResponseError
)
from app.modules.induction.llm.response_parser import parse_llm_json
from app.modules.induction.llm.prompts import SYSTEM_JSON_PROMPT

class LLMClient:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL
        self.api_key = settings.LLM_API_KEY
        self.audit_logs = []
        logger.info(f"Initialized LLMClient with provider: {self.provider}, model: {self.model}")

    async def _call_api(self, prompt: str, system_prompt: str = SYSTEM_JSON_PROMPT, retry_user_msg: str = None) -> tuple[str, float, int, int]:
        if not self.api_key:
            logger.error("API request failed: LLM API Key is not configured.")
            raise LLMConnectionError("LLM API Key is not configured. A valid API Key is required for execution.")

        t0 = time.perf_counter()
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            if retry_user_msg:
                messages.append({"role": "user", "content": retry_user_msg})

            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.2
            }

            is_openrouter = "openrouter.ai" in self.base_url
            is_nvidia = self.provider == "nvidia" or "nvidia.com" in self.base_url

            if is_openrouter:
                kwargs["extra_body"] = {"reasoning": {"enabled": True}}
            elif is_nvidia:
                kwargs["extra_body"] = {
                    "chat_template_kwargs": {"enable_thinking": True},
                    "reasoning_budget": 16384
                }
            else:
                kwargs["response_format"] = {"type": "json_object"}

            response = await client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            latency = time.perf_counter() - t0

            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage") and response.usage:
                prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
                completion_tokens = getattr(response.usage, "completion_tokens", 0)

            return content, latency, prompt_tokens, completion_tokens

        except Exception as e:
            logger.error(f"API request failed (network/provider issue): {str(e)}")
            raise LLMConnectionError(f"Failed to communicate with LLM provider: {str(e)}")

    async def generate_json(self, prompt: str, schema_validator: Optional[Callable[[dict], None]] = None, name: str = "llm_call") -> dict:
        """
        Generates JSON structure with extraction, schema validation, and single automatic retry.
        """
        # Attempt 1
        raw_content = None
        try:
            raw_content, latency, p_tokens, c_tokens = await self._call_api(prompt)

            # Case: Empty response
            if not raw_content or not raw_content.strip():
                logger.warning(f"Empty response returned for [{name}] on attempt 1.")
                raise LLMResponseParseError("Empty response returned from LLM provider.")

            logger.debug(f"Raw LLM Response [{name}] Attempt 1: {raw_content[:200]}")

            # Extraction & Parsing
            parsed_data = parse_llm_json(raw_content)

            # Schema Validation
            if schema_validator:
                schema_validator(parsed_data)

            self.audit_logs.append({
                "name": name,
                "prompt": prompt,
                "response": raw_content,
                "prompt_tokens": p_tokens,
                "completion_tokens": c_tokens,
                "latency": latency,
                "status": "success"
            })
            return parsed_data

        except (LLMResponseParseError, LLMResponseValidationError, Exception) as attempt1_err:
            # Determine specific logging case
            if isinstance(attempt1_err, LLMResponseParseError):
                logger.warning(f"Invalid JSON returned for [{name}] on attempt 1: {attempt1_err}")
            elif isinstance(attempt1_err, LLMResponseValidationError):
                logger.warning(f"JSON validation failed for [{name}] on attempt 1: {attempt1_err}")
            else:
                logger.warning(f"Parsing or validation error for [{name}] on attempt 1: {attempt1_err}")

            # Step 3 — Add One Retry
            logger.info(f"Retrying JSON generation once for [{name}]...")
            try:
                retry_msg = "Your previous response was not valid JSON. Return ONLY valid JSON."
                raw_content_retry, latency_r, p_tokens_r, c_tokens_r = await self._call_api(prompt, retry_user_msg=retry_msg)

                if not raw_content_retry or not raw_content_retry.strip():
                    logger.error(f"Empty response returned for [{name}] on retry attempt.")
                    raise InvalidResponseError("The AI returned an empty response format. Please try again.")

                parsed_data_retry = parse_llm_json(raw_content_retry)

                if schema_validator:
                    schema_validator(parsed_data_retry)

                self.audit_logs.append({
                    "name": name,
                    "prompt": prompt,
                    "response": raw_content_retry,
                    "prompt_tokens": p_tokens_r,
                    "completion_tokens": c_tokens_r,
                    "latency": latency_r,
                    "status": "success_on_retry"
                })
                logger.info(f"Successfully generated valid JSON for [{name}] on retry attempt.")
                return parsed_data_retry

            except Exception as attempt2_err:
                logger.error(f"JSON generation failed on retry attempt for [{name}]: {attempt2_err}")
                raise InvalidResponseError("The AI returned an invalid response format. Please try again.")

llm_client = LLMClient()
