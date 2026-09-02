import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

response = client.models.generate_content(
    model=os.getenv("SUMMARIZE_MODEL"),
    contents="Summarize this sentence: Python is a programming language used for web development, data analysis, and machine learning."
)

print(response.text)