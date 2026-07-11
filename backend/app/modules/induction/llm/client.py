import time
from loguru import logger
from app.core.config import settings
from app.core.exceptions import LLMConnectionError
from app.modules.induction.llm.response_parser import parse_llm_json

class LLMClient:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL
        self.api_key = settings.LLM_API_KEY
        self.audit_logs = []  # Task 6: Audit log collector
        logger.info(f"Initialized LLMClient with provider: {self.provider}, model: {self.model}")

    async def generate_json(self, prompt: str, name: str = "llm_call") -> dict:
        """
        Sends prompt to configured LLM provider and returns parsed JSON dictionary.
        Logs tokens, latency, and raw outputs for analysis (Task 6, 7, 8).
        """
        if not self.api_key:
            raise LLMConnectionError("LLM API Key is not configured. A valid API Key is required for execution.")

        t0 = time.perf_counter()
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You must output JSON only. Ensure the response matches the requested schema exactly and is valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            content = response.choices[0].message.content
            latency = time.perf_counter() - t0

            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage") and response.usage:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

            # Append transaction to audit log (Task 6 & 8)
            self.audit_logs.append({
                "name": name,
                "prompt": prompt,
                "response": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency": latency,
                "status": "success"
            })

            logger.debug(f"Raw LLM Response [{name}]: {content}")
            return parse_llm_json(content)

        except Exception as e:
            latency = time.perf_counter() - t0
            self.audit_logs.append({
                "name": name,
                "prompt": prompt,
                "response": None,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "latency": latency,
                "status": f"failed: {str(e)}"
            })
            logger.error(f"LLM API connection failed or threw error for [{name}]: {str(e)}")
            raise LLMConnectionError(f"Failed to communicate with LLM provider for {name}: {str(e)}")

llm_client = LLMClient()
