from typing import List, Dict, Any
from app.modules.induction.llm.client import llm_client
from app.core.config import settings
from loguru import logger

class QAAgent:
    async def answer_question(
        self,
        question_text: str,
        faq_records: List[Dict[str, Any]],
        presenter: Dict[str, Any]
    ) -> str:
        """
        Determines the best answer for employee's question based on company policies and FAQ records.
        """
        company = presenter.get("company_name", "KONE")
        trainer = presenter.get("ai_trainer_name", "KONE Trainer")

        # 1. Deterministic local exact keyword match search on FAQs
        norm_q = question_text.lower().strip()
        for item in faq_records:
            item_q = item.get("question", "").lower().strip()
            if item_q and (item_q in norm_q or norm_q in item_q):
                ans = item.get("answer", "")
                if ans:
                    logger.info(f"QAAgent | Found exact match answer in pre-generated FAQs for: '{question_text}'")
                    return ans

        # 2. Invoke LLM if available
        faq_context = "\n".join([f"Q: {item.get('question')}\nA: {item.get('answer')}" for item in faq_records])
        prompt = f"""
        Answer the following employee question about company {company}.
        Question: "{question_text}"
        
        Available Knowledge Base:
        {faq_context}
        
        Rules:
        - If the question can be answered clearly from the Knowledge Base, provide a short, accurate answer.
        - If the question is outside the Knowledge Base or you are unsure, set confidence to "low" and answer: "I'll forward that question to HR."
        - Do not hallucinate or guess any details.
        
        Respond ONLY in the following JSON format:
        {{
            "answer": "Answer text here",
            "confidence": "high|low"
        }}
        """

        if settings.LLM_API_KEY:
            try:
                res = await llm_client.generate_json(prompt, name="qa_agent")
                conf = res.get("confidence", "low")
                ans = res.get("answer", "")
                if conf == "high" and ans:
                    logger.info(f"QAAgent | High-confidence LLM answer generated for: '{question_text}'")
                    return ans
                else:
                    logger.info(f"QAAgent | Low-confidence answer resolved. Routing to HR.")
            except Exception as e:
                logger.error(f"QAAgent | LLM QA generation failed: {e}.")

        # Fallback response
        logger.info(f"QAAgent | Fallback: Routing question to HR.")
        return "I'll forward that question to HR."

qa_agent = QAAgent()
