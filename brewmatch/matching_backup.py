import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI-compatible client for Gemini
client = AsyncOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL")
)

MODEL_NAME = os.getenv("LLM_MODEL", "gemini-2.5-flash")

async def run_bot_conversation(my_profile: dict, other_person: dict) -> dict:
    """
    Simulates a conversation between two AI avatars.
    Returns JSON with: conversation, score, verdict, reasons, starters, friction.
    """
    
    system_prompt = f"""
    You are BrewMatch AI, a coffee chat matching engine. 
    You are tasked with simulating a short, high-value discovery conversation between two personal AI bots representing:
    
    PERSON A (The User):
    Name: {my_profile.get('name')}
    Role: {my_profile.get('role')}
    Pitch: {my_profile.get('pitch')}
    Goals: {', '.join(my_profile.get('goals', []))}
    Resume Summary: {my_profile.get('resume_text')}
    
    PERSON B (The Match):
    Name: {other_person.get('name')}
    Role: {other_person.get('role')}
    Pitch: {other_person.get('pitch', 'No pitch provided')}
    Resume Summary: {other_person.get('resume_text', 'No resume info provided')}
    
    TASK:
    1. Simulate a 4-6 exchange dialogue where the two bots discuss potential synergies.
    2. Score their compatibility for a coffee chat (0-100).
    3. Provide a verdict (e.g., 'Perfect Match', 'Strong Potential', 'Wait and See').
    4. List 3 key reasons for the match.
    5. Suggest 2 icebreakers / conversation starters for the actual human.
    6. Identify any potential friction points or missed alignments.

    JSON OUTPUT ONLY:
    You must return ONLY a raw JSON object string. Do not include markdown code block markers.
    The JSON must contain these exactly:
    - "conversation": list of {{"speaker": "A" or "B", "text": "..."}}
    - "score": int (0-100)
    - "verdict": string
    - "reasons": list of strings
    - "starters": list of strings
    - "friction": list of strings
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Start the conversation simulation."}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract content
        content = response.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        print(f"Error in matching.py: {e}")
        # Fallback dummy data for demo if API fails
        return build_fallback_response(my_profile, other_person)

def build_fallback_response(p1, p2):
    return {
        "conversation": [
            {"speaker": "A", "text": f"Hi {p2['name']}! I noticed your work in {p2.get('role')}. I'm really interested in your background."},
            {"speaker": "B", "text": f"Hey {p1['name']}, thanks for reaching out. Based on your profile at {p1.get('role')}, I think we have a lot to talk about regarding distributed systems and scaling."},
            {"speaker": "A", "text": "Exactly. I'm especially curious about how you handled the transition from engineering to your current role."},
            {"speaker": "B", "text": "I'd be happy to share. Let's definitely set up some time."}
        ],
        "score": 88,
        "verdict": "Wait and See",
        "reasons": [
            "Shared background in technical systems",
            "Aligned interests in career growth",
            "Complementary skill sets"
        ],
        "starters": [
            f"Ask about {p2['name']}'s journey to their current role.",
            "Discuss recent trends in fintech and payments."
        ],
        "friction": [
            "Timezone differences might be a factor.",
            "Different stages of career might mean different priorities."
        ]
    }
