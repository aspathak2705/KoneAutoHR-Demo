import os
from jinja2 import Template
from app.modules.induction.llm.client import llm_client
from app.modules.induction.llm.response_validator import validate_slide_response

def load_template(name: str) -> Template:
    prompt_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    template_path = os.path.join(prompt_dir, f"{name}.jinja")
    with open(template_path, "r", encoding="utf-8") as f:
        return Template(f.read())

async def generate_slide_elements(context: dict) -> dict:
    """
    Calls the LLM exactly once per slide to generate all narration, transitions,
    and interactive prompt checks. Validates the output response conditionally.
    """
    template = load_template("slide_generation")
    prompt = template.render(**context)

    # Task 6 - Provide custom slide transaction names for logging
    slide_data = context.get("slide", {})
    slide_num = slide_data.get("slide_number", 1)
    data = await llm_client.generate_json(prompt, name=f"slide_{slide_num}")

    # Determine if slide actually has videos (v1.6 context awareness)
    has_video = slide_data.get("has_video", False)

    # Perform immediate context-aware response validation
    validate_slide_response(data, has_video)
    return data
