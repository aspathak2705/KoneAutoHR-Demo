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
        logger.info(f"Initialized LLMClient with provider: {self.provider}, model: {self.model}")

    async def generate_json(self, prompt: str) -> dict:
        """
        Sends prompt to configured LLM provider and returns parsed JSON dictionary.
        Raises LLMConnectionError if the connection fails.
        """
        if not self.api_key:
            raise LLMConnectionError("LLM API Key is not configured. A valid API Key is required for execution.")

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

            # Problem 6 - Log raw response before parsing
            logger.debug(f"Raw LLM Response content: {content}")

            # Problem 5 - Clean and parse raw content into JSON dict
            return parse_llm_json(content)

        except Exception as e:
            logger.error(f"LLM API connection failed or threw error: {str(e)}")
            raise LLMConnectionError(f"Failed to communicate with LLM provider: {str(e)}")

llm_client = LLMClient()
