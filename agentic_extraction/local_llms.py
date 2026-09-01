import ollama

def chat(model, messages, tools=None):
    return ollama.chat(
        model=model,
        messages=messages,
        tools=tools or []
    )

def extract_json(model, messages, schema):
    return ollama.chat(
        model=model,
        messages=messages,
        format=schema.model_json_schema(),
        options={"temperature": 0}
    )