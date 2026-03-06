from app.services.ai.promt import build_prompt

prompt = build_prompt(
    "chat",
    prompt="What is artificial intelligence?"
)

print(prompt)