import ollama
from pathlib import Path

model = "qwen3-vl:4b-instruct"

def load_llm(model="qwen3:4b"):
    print("Pulling model:", model)
    ollama.pull(model)
    return model

def chat_llm(model, prompt, system_prompt="You are a helpful assistant."):
    response = ollama.chat(model=model, messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ])
    return response.message.content

def analyze_image(image_path, prompt="Describe this image."):
    image_path = str(Path(image_path).expanduser().resolve())
    assert Path(image_path).is_file(), f"Image not found: {image_path}"
    response = ollama.chat(model="qwen3-vl:4b-instruct",
        messages=[{"role":"user", "content":prompt, "images":[image_path]}])
    return response.message.content


if __name__ == "__main__":
    
    load_llm(model)
    img = "/home/user/repos/dimensional_models_of_emotions/imgs/outraged.jpg"
    print(img, type(img))
    print(analyze_image(img, "What emotion can you detect?"))