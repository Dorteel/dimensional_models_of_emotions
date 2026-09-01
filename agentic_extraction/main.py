from local_llms import chat
from memory import create_memory, remember
from tools import TOOLS
from agent import run_agent, extract_knowledge
import ollama

model="qwen3:4b-instruct"

if __name__ == "__main__":
    ollama.pull(model)
    knowledge = extract_knowledge("apple")
    print(knowledge.model_dump_json(indent=2))