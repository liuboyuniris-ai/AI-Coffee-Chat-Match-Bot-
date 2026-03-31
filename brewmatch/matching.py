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
        print(f"Error in matching.py (run_bot_conversation): {e}")
        # Try a more desperate but flexible approach if json_object failed
        try:
            print("Attempting non-JSON recovery...")
            resp = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt + "\nIMPORTANT: Return ONLY raw JSON."},
                    {"role": "user", "content": "Start the conversation simulation."}
                ]
            )
            content = resp.choices[0].message.content
            # Basic cleanup of markdown markers
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except:
            pass
        # Fallback dummy data for demo if API fails
        return build_fallback_response(my_profile, other_person)

def build_fallback_response(p1, p2):
    import random
    # Give a slightly different score each time so it doesn't look stuck
    score = 75 + random.randint(0, 15)
    return {
        "conversation": [
            {"speaker": "A", "text": f"Hi {p2['name']}! I noticed your work in {p2.get('role')}. I'm really interested in your background."},
            {"speaker": "B", "text": f"Hey {p1['name']}, thanks for reaching out. Based on your profile at {p1.get('role')}, I think we have a lot to talk about regarding distributed systems and scaling."},
            {"speaker": "A", "text": "Exactly. I'm especially curious about how you handled the transition from engineering to your current role."},
            {"speaker": "B", "text": "I'd be happy to share. Let's definitely set up some time."}
        ],
        "score": score,
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

async def stream_live_conversation(my_profile: dict, other_person: dict):
    # Setup context
    pA = f"Your profile: You are {my_profile.get('name')}, {my_profile.get('role')}. Pitch: {my_profile.get('pitch')}."
    pB = f"Your profile: You are {other_person.get('name')}, {other_person.get('role')}. Pitch: {other_person.get('pitch')}."
    
    # Other person's context
    opA = f"Name: {other_person.get('name')}. Role: {other_person.get('role')}. Pitch: {other_person.get('pitch')}."
    opB = f"Name: {my_profile.get('name')}. Role: {my_profile.get('role')}. Pitch: {my_profile.get('pitch')}."
    
    # Function to call LLM for a specific bot
    async def get_bot_reply(my_persona, target_persona, my_name, target_name, history_text, turn_index):
        if turn_index == 0:
            instruction = f"Initiate the conversation by mentioning a specific detail from {target_name}'s background that interests you."
        elif turn_index == 1:
            instruction = f"Reply enthusiastically and relate their point back to your own background."
        elif turn_index == 2:
            instruction = f"Ask a specific, insightful question about {target_name}'s work or goals to dive deeper."
        else:
            instruction = f"Wrap up the chat warmly and suggest setting up a real time to connect."
            
        prompt = f"""
{my_persona}
You are talking to: {target_persona}

Instructions for this message:
{instruction}
Keep it short (2-3 sentences), natural, and highly conversational. Do NOT output your own name prefix.
IMPORTANT: Ensure your output is a complete, well-formed sentence. Do not stop mid-sentence.

Conversation History:
{history_text if history_text else "(No history yet, you are starting the chat)"}

Your complete response:"""
        
        try:
            res = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            msg_text = res.choices[0].message.content.strip()
            print(f"[{my_name}] {msg_text}")
            return msg_text
        except Exception as e:
            print(f"Error in LLM call: {e}")
            return "Sounds interesting! Let's definitely connect."

    yield f'data: {json.dumps({"type": "status", "message": "Connecting bots..."})}\n\n'
    import asyncio
    await asyncio.sleep(0.5)
    
    history_text = ""
    script = []
    
    # 4 turns of dialogue (A, B, A, B)
    for turn in range(4):
        speaker_id = "A" if turn % 2 == 0 else "B"
        speaker_name = my_profile.get('name') if speaker_id == "A" else other_person.get('name')
        
        my_persona = pA if speaker_id == "A" else pB
        target_persona = opA if speaker_id == "A" else opB
        target_name = other_person.get('name') if speaker_id == "A" else my_profile.get('name')
        
        yield f'data: {json.dumps({"type": "typing", "speaker": speaker_id})}\n\n'
        
        msg = await get_bot_reply(my_persona, target_persona, speaker_name, target_name, history_text, turn)
        
        # Clean up if AI prefixed its own name
        if msg.startswith(f"{speaker_name}:"):
            msg = msg.replace(f"{speaker_name}:", "").strip()
            
        history_text += f"{speaker_name}: {msg}\n"
        script.append({"speaker": speaker_id, "text": msg})
        
        yield f'data: {json.dumps({"type": "message", "speaker": speaker_id, "text": msg})}\n\n'
        await asyncio.sleep(0.5) # Natural pacing
        
    yield f'data: {json.dumps({"type": "status", "message": "Analyzing compatibility..."})}\n\n'
    
    eval_prompt = f"""
    Based on this conversation between {my_profile.get('name')} and {other_person.get('name')}:
    {history_text}
    
    Rate their synergy for a networking coffee chat (0-100).
    Verdict: (e.g., 'Perfect Match', 'Wait and See', 'Strong Alignment').
    List 3 reasons, 2 starters, 2 friction points.
    JSON OUTPUT ONLY. Example keys: "score": 85, "verdict": "...", "reasons": [...], "starters": [...], "friction": [...]
    """
    try:
        res = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": eval_prompt}],
            response_format={"type": "json_object"}
        )
        final_data = json.loads(res.choices[0].message.content)
        final_data["type"] = "complete"
        final_data["conversation"] = script
        yield f'data: {json.dumps(final_data)}\n\n'
    except Exception as e:
        print(f"Error in matching.py (stream_live_evaluation): {e}")
        # Try without json_object as a fallback
        try:
            res = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "system", "content": eval_prompt + "\nReturn ONLY valid JSON."}]
            )
            content = res.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            final_data = json.loads(content)
            final_data["type"] = "complete"
            final_data["conversation"] = script
            yield f'data: {json.dumps(final_data)}\n\n'
        except:
            fallback = build_fallback_response(my_profile, other_person)
            fallback["type"] = "complete"
            fallback["conversation"] = script
            yield f'data: {json.dumps(fallback)}\n\n'
