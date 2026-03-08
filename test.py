import os

from google import genai
from google.genai import errors


api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise SystemExit(
        "GOOGLE_API_KEY is not set. Export it first, for example: "
        "export GOOGLE_API_KEY='your-valid-key'"
    )

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model="models/gemini-2.0-flash",
        contents="Explain quantum computing to a cat.",
    )
    print(response.text)
except errors.ClientError as exc:
    raise SystemExit(
        "Gemini API request failed. This usually means the API key is invalid/expired "
        "or does not have access to this model. Check GOOGLE_API_KEY and retry.\n"
        f"Details: {exc}"
    )