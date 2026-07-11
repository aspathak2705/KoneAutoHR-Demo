import os
from jinja2 import Template
from app.modules.induction.llm.client import llm_client
from app.modules.induction.llm.response_validator import validate_introduction_response

def load_template(name: str) -> Template:
    prompt_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    template_path = os.path.join(prompt_dir, f"{name}.jinja")
    with open(template_path, "r", encoding="utf-8") as f:
        return Template(f.read())

async def generate_introduction(context: dict) -> dict:
    """
    Generates welcome flows using the Master Context Contract and validates response schema.
    """
    template = load_template("introduction")
    prompt = template.render(**context)
    data = await llm_client.generate_json(prompt, name="welcome")

    # Perform immediate response validation
    validate_introduction_response(data)
    return data
