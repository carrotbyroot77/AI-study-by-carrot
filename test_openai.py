from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
resp = client.responses.create(
    model="gpt-4o-mini",
    input=[{"role":"user","content":"한 문장으로 인사해줘."}],
)
print(getattr(resp, "output_text", resp.output[0].content[0].text))
