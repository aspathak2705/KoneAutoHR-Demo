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
        Determines the best answer for employee's question.
        Knowledge Sources:
        1. Presentation JSON Script
        2. Organization Policies / Handbooks
        3. Pre-prepared database FAQ list (primary match target)
        
        If confidence is low or query falls outside knowledge sources, routes safely to HR.
        """
        company = presenter.get("company_name", "KONE")
        trainer = presenter.get("ai_trainer_name", "KONE Trainer")

        # Knowledge Source 1: Pre-seeded database FAQs lookup
        norm_q = question_text.lower().strip()
        for item in faq_records:
            item_q = item.get("question", "").lower().strip()
            if item_q and (item_q in norm_q or norm_q in item_q):
                ans = item.get("answer", "")
                if ans:
                    logger.info(f"QAAgent | Found exact match answer in pre-seeded FAQs: '{question_text}'")
                    return ans

        # Knowledge Source 2: Optional LLM check matching policies or handbook context
        faq_context = "\n".join([f"Q: {item.get('question')}\nA: {item.get('answer')}" for item in faq_records])
        prompt = f"""
        Answer the following employee question about company {company} policies and handbook.
        Question: "{question_text}"
        
        Knowledge Base:
        {faq_context}
        
        Instructions:
        - If the question can be resolved directly from the Knowledge Base or general KONE policies, provide a short professional answer.
        - If the question is outside this scope or you are unsure, set confidence to "low" and answer: "I'll forward that question to HR."
        - Avoid hallucinations. Do not invent policies.
        
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
                    logger.info(f"QAAgent | Low confidence resolved. Routing to HR.")
            except Exception as e:
                logger.error(f"QAAgent | LLM QA call failed: {e}")

        # Fallback response
        logger.info(f"QAAgent | Fallback: Routing question to human HR.")
        return "I'll forward that question to HR."

qa_agent = QAAgent()
