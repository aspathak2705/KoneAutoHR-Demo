import json
import re
from loguru import logger
from app.core.config import settings

class LLMClient:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL
        self.api_key = settings.LLM_API_KEY
        logger.info(f"Initialized LLMClient with provider: {self.provider}, model: {self.model}")

    async def generate_json(self, prompt: str) -> dict:
        """
        Sends prompt to configured LLM provider and returns parsed JSON.
        Falls back to high-fidelity template simulator if provider is 'mock' or API call fails.
        """
        if self.provider == "mock" or not self.api_key:
            return self._simulate_mock_response(prompt)

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
            return json.loads(content)
        except Exception as e:
            logger.warning(f"LLM API call failed: {str(e)}. Falling back to high-fidelity mock simulator.")
            return self._simulate_mock_response(prompt)

    def _simulate_mock_response(self, prompt: str) -> dict:
        """
        Simulated generation matching the final polished Induction Package schema.
        """
        prompt_lower = prompt.lower()

        # 1. Introduction/Welcome flow
        if "welcome elements" in prompt_lower or "self introduction" in prompt_lower:
            return {
                "greeting": "Good morning and a very warm welcome to KONE. We are absolutely thrilled to have you join our team today as you begin your career journey with us.",
                "wait_message": "Before we dive in, let's give everyone just another minute to make sure all participants have successfully joined the meeting bridge.",
                "audio_check": "In the meantime, could someone quickly drop a message in the chat or unmute to confirm that my audio is clear and you can see the opening slide?",
                "ice_breaker": "To start off, I'd love to know where everyone is joining us from today. Please type your city in the chat box!",
                "agenda": [
                    "KONE Company Vision & Core Values",
                    "HR Policies, Work Hours & Leaves Structure",
                    "Safety and Compliance Guidelines",
                    "Next Steps for Onboarding & IT Portal Setup"
                ],
                "meeting_join_message": "Hello everyone. Welcome. I am the KONE AI Induction Officer. Please connect your audio.",
                "participant_wait_timeout": 60,
                "late_joiner_message": "Welcome to the joiners who just connected. We are doing a quick ice breaker now.",
                "start_confirmation": "All ready. Let's start the presentation."
            }

        # 2. Transition
        elif "transition script" in prompt_lower or "bridge sentence" in prompt_lower:
            return {
                "transition": "Now that we have covered this section, let us move on to the next slide to explore our core policies in more detail."
            }

        # 3. Expected Questions
        elif "predict the questions" in prompt_lower or "expected questions" in prompt_lower:
            slide_match = re.search(r"slide number:\s*(\d+)", prompt_lower)
            slide_num = int(slide_match.group(1)) if slide_match else 1
            return {
                "expected_questions": [
                    {
                        "question": "What is the policy for claiming remote internet reimbursement?",
                        "answer": "You can submit remote working claims through the KONE HR portal under the Expense Reimbursement section before the 25th of each month.",
                        "confidence": 0.95,
                        "reference_slide": slide_num,
                        "follow_up_questions": [
                            "How do I access the expense page on my phone?",
                            "Is there a maximum claim limit?"
                        ]
                    },
                    {
                        "question": "Where can I find the holidays calendar for my location?",
                        "answer": "The official KONE holiday list is available on the intranet home page under the local HR guidelines link.",
                        "confidence": 0.90,
                        "reference_slide": slide_num,
                        "follow_up_questions": [
                            "Do remote workers follow regional holiday calendars?"
                        ]
                    }
                ]
            }

        # 4. Closing script
        elif "closing script" in prompt_lower or "conclude the induction" in prompt_lower:
            return {
                "summary": "Today we have walked through KONE's corporate history, safety principles, core HR benefits, and IT portal setup.",
                "congratulations": "Once again, congratulations and welcome to KONE! We are excited to support you as you grow with us.",
                "next_steps": "Please complete your mandatory onboarding compliance modules in the training portal by the end of this week, and submit your bank details on the IT desk."
            }

        # 5. Narration (Slide description)
        else:
            title_match = re.search(r"title:\s*([^\n]+)", prompt_lower)
            slide_title = title_match.group(1).strip() if title_match else "this topic"

            slide_match = re.search(r"slide number:\s*(\d+)", prompt_lower)
            slide_num = int(slide_match.group(1)) if slide_match else 1

            # Mock video script if prompt mentions videos or slide is number 2
            video_script = None
            if "video" in prompt_lower or slide_num == 2:
                video_script = {
                    "before_video": "Before we watch this short video, please focus on our safety guidelines.",
                    "after_video": "I hope that safety video was helpful. Let's discuss it.",
                    "pause_after_video": True,
                    "resume_message": "Let's resume the slide presentation."
                }

            return {
                "narration": f"On this slide, we will be discussing {slide_title}. This represents one of KONE's key focus areas. To give you some context, we operate on a model where team collaboration is central. We want to ensure that every new hire understands how these policies apply to their daily work, and we encourage you to align with your team leader to set milestones.",
                "interactive_prompt": f"Does anyone have any initial thoughts on {slide_title}, or is this policy clear to everyone so far?",
                "learning_objective": f"Understand the core elements and background of {slide_title}.",
                "key_takeaways": [
                    f"Understanding KONE policies regarding {slide_title}.",
                    f"Applying collaborative strategies to {slide_title}."
                ],
                "story_example": f"For instance, last year, an engineering team utilized these exact principles to successfully deploy a new project in record time.",
                "video_script": video_script
            }

llm_client = LLMClient()
