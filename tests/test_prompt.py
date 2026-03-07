from mAIcro.app.services.ai.prompt import build_prompt

prompt = build_prompt(
    "chat",
    prompt="What is artificial intelligence?"
)

print(prompt)