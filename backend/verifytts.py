import os
import sys
import asyncio
from loguru import logger

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "backend")))

from app.modules.presentation.speech_engine import speech_engine
from app.modules.presentation.models import NarrationBlock

# Detailed induction session script payload mimicking production output
AUTO_HR_SESSION_SCRIPT = {
    "opening": {
        "greeting": "Good morning everyone! Welcome to today's KONE onboarding session.",
        "presenter_intro": "I am your AI HR Trainer, here to guide you through your induction journey.",
        "employee_welcome": "A warm welcome to our new batch of colleagues joining us today.",
        "audio_check": "Before we begin, can everyone hear me clearly? Please drop a thumbs-up in the chat if you can.",
        "ice_breaker": "To start off, please type the department you are joining in the chat window. It is great to see representatives from Engineering, Sales, and Operations!",
        "session_rules": "A quick note on guidelines: please keep your microphones muted unless asked. You can ask questions anytime in the chat box.",
        "agenda": "Today we will cover company values, safety policies, key benefits, and your next steps."
    },
    "slides": [
        {
            "slide_number": 1,
            "title": "Welcome to KONE",
            "transition_in": "Let us jump right into our first slide.",
            "narration": "KONE's mission is to improve the flow of urban life. We are dedicated to providing the best elevator and escalator experience.",
            "understanding_check": "Does anyone have questions about KONE's global footprint?",
            "transition_out": "Moving on to slide two."
        },
        {
            "slide_number": 2,
            "title": "Safety First",
            "transition_in": "Safety is our number one priority.",
            "narration": "At KONE, safety is a core value. We ensure every employee returns home safely every single day.",
            "understanding_check": "Are safety protocols clear to everyone?",
            "transition_out": "Now, let us wrap up today's induction."
        }
    ],
    "closing": {
        "summary": "To summarize, we covered KONE's global mission, our core safety values, and next steps.",
        "next_steps": "Your next step is to log into the learning portal and complete your compliance modules.",
        "farewell": "Thank you all for joining. Welcome to KONE, and have a fantastic first week!"
    }
}

async def run_detailed_tts_session():
    logger.info("Starting detailed AutoHR TTS Session Simulation...")
    
    # 1. Process Opening Section
    opening = AUTO_HR_SESSION_SCRIPT["opening"]
    for key, text in opening.items():
        logger.info(f"Synthesizing Opening step [{key}]...")
        block = NarrationBlock(
            slide_number=0,
            text=text,
            estimated_duration=max(2.0, round(len(text.split()) / 2.5, 1))
        )
        await speech_engine.speak(block)
        await asyncio.sleep(1) # Gap between speech blocks

    # 2. Process Slides Section
    slides = AUTO_HR_SESSION_SCRIPT["slides"]
    for s in slides:
        slide_num = s["slide_number"]
        logger.info(f"Synthesizing Slide {slide_num} [{s['title']}]...")
        
        # Transition In
        t_in = s["transition_in"]
        await speech_engine.speak(NarrationBlock(slide_number=slide_num, text=t_in, estimated_duration=max(2.0, round(len(t_in.split()) / 2.5, 1))))
        await asyncio.sleep(0.5)

        # Main Narration
        narration = s["narration"]
        await speech_engine.speak(NarrationBlock(slide_number=slide_num, text=narration, estimated_duration=max(2.0, round(len(narration.split()) / 2.5, 1))))
        await asyncio.sleep(0.5)

        # Understanding Check
        u_check = s["understanding_check"]
        await speech_engine.speak(NarrationBlock(slide_number=slide_num, text=u_check, estimated_duration=max(2.0, round(len(u_check.split()) / 2.5, 1))))
        await asyncio.sleep(0.5)

        # Transition Out
        t_out = s["transition_out"]
        await speech_engine.speak(NarrationBlock(slide_number=slide_num, text=t_out, estimated_duration=max(2.0, round(len(t_out.split()) / 2.5, 1))))
        await asyncio.sleep(1)

    # 3. Process Closing Section
    closing = AUTO_HR_SESSION_SCRIPT["closing"]
    for key, text in closing.items():
        logger.info(f"Synthesizing Closing step [{key}]...")
        block = NarrationBlock(
            slide_number=100,
            text=text,
            estimated_duration=max(2.0, round(len(text.split()) / 2.5, 1))
        )
        await speech_engine.speak(block)
        await asyncio.sleep(1)

    logger.info("Detailed AutoHR TTS Session Simulation completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_detailed_tts_session())
