import os
from jinja2 import Template
from app.modules.induction.llm.client import llm_client

def load_template(name: str) -> Template:
    prompt_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    template_path = os.path.join(prompt_dir, f"{name}.jinja")
    with open(template_path, "r", encoding="utf-8") as f:
        return Template(f.read())

async def generate_slide_elements(context: dict) -> dict:
    """
    Calls the LLM exactly once per slide to generate all narration, transitions,
    and predicted Q&As using the Master Context Contract.
    """
    template = load_template("slide_generation")
    prompt = template.render(**context)
    return await llm_client.generate_json(prompt)
