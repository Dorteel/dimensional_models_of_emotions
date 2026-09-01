from local_llms import chat, extract_json
from memory import create_memory, remember
from tools import TOOLS
from schemas import CommonsenseKnowledge

def run_agent(prompt, model="qwen3:4b"):
    memory = create_memory("You are a helpful local agent.")
    remember(memory, {"role": "user", "content": prompt})
    response = chat(model, memory, list(TOOLS.values()))
    remember(memory, response.message)
    for call in response.message.tool_calls or []:
        result = TOOLS[call.function.name](**call.function.arguments)
        remember(memory, {"role": "tool", "tool_name": call.function.name, "content": str(result)})
    return chat(model, memory, list(TOOLS.values())).message.content

def extract_knowledge(entity, model="qwen3:4b-instruct"):
    messages = [{"role": "user",
        "content": f"Extract commonsense knowledge about: {entity}"}]
    response = extract_json(model, messages, CommonsenseKnowledge)
    return CommonsenseKnowledge.model_validate_json(response.message.content)