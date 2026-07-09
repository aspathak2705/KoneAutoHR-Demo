import os
from jinja2 import Template
from app.modules.induction.llm.client import llm_client

def load_template(name: str) -> Template:
    prompt_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    template_path = os.path.join(prompt_dir, f"{name}.jinja")
    with open(template_path, "r", encoding="utf-8") as f:
        return Template(f.read())

async def generate_introduction(context: dict, slide_knowledge: list[dict]) -> dict:
    template = load_template("introduction")
    prompt = template.render(
        meeting_context=context.get("meeting_context"),
        audience_summary=context.get("audience_summary"),
        ai_persona=context.get("ai_persona"),
        slide_knowledge=slide_knowledge
    )
    return await llm_client.generate_json(prompt)
