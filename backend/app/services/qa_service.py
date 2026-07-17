from sqlalchemy.orm import Session as DBSession
from typing import List, Dict, Any
from app.models.runtime_message import RuntimeMessage
from app.models.session import Session
from app.models.organization_config import OrganizationConfig
from app.repositories.presentation_question_repository import presentation_question_repository
from app.modules.induction.llm.client import llm_client
from loguru import logger
import datetime

class QaService:
    def get_conversation_history(self, db: DBSession, session_id: str) -> List[RuntimeMessage]:
        return db.query(RuntimeMessage).filter(RuntimeMessage.session_id == session_id).order_by(RuntimeMessage.timestamp.asc()).all()

    async def ask_question(
        self,
        db: DBSession,
        session_id: str,
        speaker_name: str,
        question_text: str
    ) -> Dict[str, Any]:
        """
        Sprint 4: Implements the live Q&A matching, memory, and moderation constraints.
        """
        # 1. Verify Session & Fetch assets
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise ValueError("Session not found.")

        # 2. Fetch prepared FAQs list
        faq_record = None
        if session.presentation_id:
            faq_record = presentation_question_repository.get_active(db, session.presentation_id)
        
        prepared_faqs = []
        if faq_record and faq_record.questions_content:
            prepared_faqs = faq_record.questions_content

        # 3. Fetch Company Configuration
        config = db.query(OrganizationConfig).first()
        if not config:
            config = OrganizationConfig(
                company_name="KONE",
                company_domain="kone.com",
                ai_trainer_name="KONE Trainer",
                vocal_tone="Professional",
                communication_style="Direct"
            )

        # 4. Load Conversation Memory
        history = self.get_conversation_history(db, session_id)
        history_str = ""
        for msg in history[-6:]: # Keep last 6 exchanges
            history_str += f"{msg.speaker_name}: {msg.message_text}\n"

        # 5. Build Moderator Rules
        # Filter obvious off-topic prompts
        off_topic_indicators = ["weather", "capital of", "recipe", "hack", "bypass", "joke", "song"]
        is_off_topic = any(word in question_text.lower() for word in off_topic_indicators)

        answer_text = ""
        if is_off_topic:
            answer_text = (
                f"I am {config.ai_trainer_name}, your KONE onboarding assistant. "
                "I can only help with KONE onboarding details and general HR questions."
            )
        else:
            # First, check if there's a close string overlap match in prepared FAQs
            matched_faq = None
            for item in prepared_faqs:
                q = item.get("question", "").lower()
                if q in question_text.lower() or question_text.lower() in q:
                    matched_faq = item.get("answer")
                    break

            if matched_faq:
                answer_text = matched_faq
                logger.info(f"QaService | FAQ Match found for: '{question_text}'")
            elif llm_client.api_key:
                # Direct LLM generation using context, memory, and persona
                prompt = f"""
                You are {config.ai_trainer_name}, an AI Onboarding Assistant at {config.company_name}.
                Answer the employee's onboarding question based on the prepared FAQs context, previous conversation history, and persona guidelines.

                Company Name: {config.company_name}
                Trainer Name: {config.ai_trainer_name}
                Vocal Tone: {config.vocal_tone}
                Style: {config.communication_style}

                Context Prepared FAQs:
                {prepared_faqs}

                Previous History:
                {history_str}

                Moderation Rule: If the question does not relate to KONE onboarding or general HR guidelines, politely state that you can only answer onboarding/HR questions.

                Employee ({speaker_name}) asks: "{question_text}"
                AI Assistant Response:
                """
                try:
                    res = await llm_client.generate(prompt, name=f"qa_{session_id}")
                    if res:
                        answer_text = res.strip()
                except Exception as e:
                    logger.warning(f"LLM Q&A generation failed, falling back to general matching: {e}")

            if not answer_text:
                # General fallback
                answer_text = (
                    "I am currently reviewing our company guidelines. Let me log this question "
                    "for your HR coordinator to follow up with you after this call."
                )

        # 6. Persist Employee's Question
        emp_msg = RuntimeMessage(
            session_id=session_id,
            speaker_name=speaker_name,
            message_text=question_text
        )
        db.add(emp_msg)

        # 7. Persist AI's Answer
        ai_msg = RuntimeMessage(
            session_id=session_id,
            speaker_name=config.ai_trainer_name,
            message_text=answer_text
        )
        db.add(ai_msg)

        db.commit()

        return {
            "question": {
                "speaker": speaker_name,
                "text": question_text
            },
            "answer": {
                "speaker": config.ai_trainer_name,
                "text": answer_text
            }
        }

qa_service = QaService()
