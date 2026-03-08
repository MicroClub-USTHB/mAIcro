from google import genai

client = genai.Client(api_key="AIzaSyAnmElA9P35lUUHdquILJ-M3NZOw8T1I98")

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Say hello in one short sentence."
)

print(response.text)