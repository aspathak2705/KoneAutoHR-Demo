import os
from jinja2 import Template
from app.modules.induction.llm.client import llm_client

def load_template(name: str) -> Template:
    prompt_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    template_path = os.path.join(prompt_dir, f"{name}.jinja")
    with open(template_path, "r", encoding="utf-8") as f:
        return Template(f.read())

async def generate_transition(context: dict, current_slide: dict, next_slide: dict) -> dict:
    template = load_template("transition")
    prompt = template.render(
        current_slide=current_slide,
        next_slide=next_slide,
        ai_persona=context.get("ai_persona")
    )
    return await llm_client.generate_json(prompt)
