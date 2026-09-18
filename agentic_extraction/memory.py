def create_memory(system_prompt):
    return [
        {"role": "system", "content": system_prompt}
    ]

def remember(memory, message):
    memory.append(message)
