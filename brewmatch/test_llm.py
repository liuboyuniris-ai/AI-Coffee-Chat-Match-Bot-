import asyncio, os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_BASE_URL"))

async def main():
    prompt = """Your profile: You are Angela Yu, PR Junior @ USC. Pitch: Interested in Tech PR.
You are talking to: Name: Iris Liu. Role: Business of Cinematic Arts Freshmen@USC. Pitch: I am a freshmen at USC majoring in BCA.

Instructions for this message:
Reply enthusiastically and relate their point back to your own background.
Keep it short (2-3 sentences), natural, and highly conversational. Do NOT output your own name prefix.
IMPORTANT: Ensure your output is a complete, well-formed sentence. Do not stop mid-sentence.

Conversation History:
Iris Liu: Hi Angela, I saw you're a PR junior at USC and I'm really curious to hear about your experiences...

Your complete response:"""
    try:
        res = await client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        print("OUTPUT:", res.choices[0].message.content)
    except Exception as e:
        print("ERROR:", e)

asyncio.run(main())
