import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import data
import matching

# Import Supabase
try:
    from supabase_client import supabase
except ImportError:
    supabase = None

app = FastAPI(title="BrewMatch — AI Coffee Chat Matching App")

# Global interaction store - Fallbacks for local dev without Supabase
users = {}
requests = {} # { recipient_id: [sender_id, ...] } for Bot Chat
requests_human = {} # { recipient_id: [sender_id, ...] } for Human Chat
connections = {}
bot_chats = {} 
reports = {} # { "user_id:person_id": {score, verdict, reasons, conversation, etc.} }
messages = {} # { chat_id: [{sender: id, text: str, time: str}, ...] }

# --- Data Layer with Supabase support ---

def get_supabase_data():
    """Fallback to local if no Supabase, otherwise use DB as truth."""
    if not supabase: return False
    return True

async def sync_users():
    global users
    if not get_supabase_data(): return
    try:
        res = supabase.table("users").select("*").execute()
        for u in res.data:
            users[u['id']] = u
    except Exception as e:
        print(f"Sync users error: {e}")

async def sync_interactions(user_id: str = None):
    global requests, requests_human, connections, bot_chats, reports
    if not get_supabase_data(): return
    try:
        # Reset local maps to avoid duplicates on re-sync
        requests = {}; requests_human = {}; connections = {}; bot_chats = {}; reports = {}
        
        query = supabase.table("interactions").select("*")
        if user_id:
            # We need both rows where user is the sender OR the target
            # Using or filter if complex or just fetch relevant subset
            # For simplicity in this demo, we fetch all relevant but we could optimize
            query = query.execute()
        else:
            query = query.execute()
        
        # Merge results into global state carefully
        for row in query.data:
            uid = row['user_id']
            tid = row['target_id']
            itype = row['type']
            idata = row.get('data', {})
            
            if itype == 'bot_request':
                if tid not in requests: requests[tid] = []
                if uid not in requests[tid]: requests[tid].append(uid)
            elif itype == 'human_request':
                if tid not in requests_human: requests_human[tid] = []
                if uid not in requests_human[tid]: requests_human[tid].append(uid)
            elif itype == 'connection':
                if uid not in connections: connections[uid] = []
                if tid not in connections[uid]: connections[uid].append(tid)
            elif itype == 'bot_chat':
                if uid not in bot_chats: bot_chats[uid] = []
                if tid not in bot_chats[uid]: bot_chats[uid].append(tid)
            elif itype == 'report':
                key = ":".join(sorted([uid, tid]))
                reports[key] = idata
    except Exception as e:
        print(f"Sync interactions error: {e}")

# Legacy JSON loader for local compatibility
USERS_FILE = "users.json"
DATA_FILE = "interactions.json"
MESSAGES_FILE = "messages.json"

def load_local_data():
    global users, requests, requests_human, connections, bot_chats, messages, reports
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f: users = json.load(f)
        except: users = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                saved_data = json.load(f)
                requests = saved_data.get("requests", {})
                requests_human = saved_data.get("requests_human", {})
                connections = saved_data.get("connections", {})
                bot_chats = saved_data.get("bot_chats", {})
                reports = saved_data.get("reports", {})
        except: pass

@app.on_event("startup")
async def startup_event():
    if get_supabase_data():
        await sync_users()
        await sync_interactions()
    else:
        load_local_data()

class UserProfile(BaseModel):
    id: Optional[str] = None
    name: str = ""
    role: str = ""
    pitch: str = ""
    goals: List[str] = []
    resume_text: str = ""

class AuthRequest(BaseModel):
    username: str
    password: str

@app.get("/", response_class=HTMLResponse)
async def read_index():
    static_file_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(static_file_path, "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/auth")
async def auth(req: AuthRequest):
    """Simple login/register by username and password."""
    user_id = req.username.lower().strip()
    password = req.password
    
    # 1. Try Supabase
    if get_supabase_data():
        res = supabase.table("users").select("*").eq("id", user_id).execute()
        if not res.data:
            new_user = {
                "id": user_id, "password": password, "name": "", "role": "", 
                "pitch": "", "goals": [], "resume_text": ""
            }
            supabase.table("users").insert(new_user).execute()
            users[user_id] = new_user
            return new_user
        else:
            db_user = res.data[0]
            if db_user["password"] != password:
                raise HTTPException(status_code=401, detail="Invalid password")
            profile = db_user.copy()
            profile.pop("password", None)
            users[user_id] = db_user
            return profile
            
    # 2. Local Fallback
    if user_id not in users:
        users[user_id] = {
            "id": user_id, "password": password, "name": "", "role": "", 
            "pitch": "", "goals": [], "resume_text": ""
        }
        # save_data() - will skip for local in Vercel mode
    else:
        if users[user_id].get("password") != password:
            raise HTTPException(status_code=401, detail="Invalid password")
            
    profile = users[user_id].copy()
    profile.pop("password", None)
    return profile

@app.get("/api/me/{user_id}")
async def get_me(user_id: str):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")
    return users[user_id]

@app.post("/api/create-avatar")
async def create_avatar(profile: UserProfile):
    """Stores or updates the user profile."""
    if not profile.id:
        raise HTTPException(status_code=400, detail="User ID required")
    user_id = profile.id.lower().strip()
    
    # 1. Update Supabase
    if get_supabase_data():
        update_data = profile.model_dump()
        update_data["id"] = user_id
        supabase.table("users").upsert(update_data).execute()
        users[user_id] = update_data
        return {"success": True, "profile": update_data}
        
    # 2. Local fallback
    password = users.get(user_id, {}).get("password")
    users[user_id] = profile.model_dump()
    if password: users[user_id]["password"] = password
    return {
        "success": True, 
        "avatar_summary": f"Your AI Twin for {profile.name} ({profile.role}) is ready for coffee chats.",
        "profile": users[user_id]
    }

@app.post("/api/match")
async def match_person(match_request: Dict):
    """Runs a bot conversation between current user and a target person."""
    other_person_id = match_request.get("person_id")
    user_id = match_request.get("user_id")
    
    my_profile = users.get(user_id) if user_id else None
    
    if not my_profile or not my_profile.get("name"):
        # For demo purposes, we can use a mock profile if none created or empty
        my_profile = {
            "name": "Alex Chen",
            "role": "CS Student @ UCLA",
            "pitch": "Junior at UCLA interested in SWE and startups.",
            "goals": ["Internship tips", "Career advice"],
            "resume_text": "Alex Chen, CS Junior at UCLA. No real resume yet."
        }
        
    if not other_person_id:
        raise HTTPException(status_code=400, detail="Missing target person")
        
    other_person = next((p for p in data.PEOPLE if p["id"].lower() == other_person_id.lower()), None)
    if not other_person:
        # Check event people too
        other_person = next((p for p in data.EVENT_PEOPLE if p["id"].lower() == other_person_id.lower()), None)
        
    # Also check other real users in the memory/JSON storage!
    if not other_person and other_person_id.lower() in users:
        u_data = users[other_person_id.lower()]
        other_person = {
            "name": u_data.get("name") or f"User ({other_person_id})",
            "role": u_data.get("role", "BrewMatch User"),
            "pitch": u_data.get("pitch", ""),
            "resume_text": u_data.get("resume_text", "")
        }
        
    if not other_person:
        raise HTTPException(status_code=404, detail=f"Person {other_person_id} not found")
        
    result = await matching.run_bot_conversation(my_profile, other_person)
    return result

@app.get("/api/stream-match")
async def stream_match(user_id: str, person_id: str):
    """Streams a live bot conversation between current user and a target person."""
    my_profile = users.get(user_id) if user_id else None
    
    if not my_profile or not my_profile.get("name"):
        my_profile = {
            "name": "Alex Chen",
            "role": "CS Student @ UCLA",
            "pitch": "Junior at UCLA interested in SWE and startups.",
            "goals": ["Internship tips", "Career advice"],
            "resume_text": "Alex Chen, CS Junior at UCLA. No real resume yet."
        }
        
    if not person_id:
        raise HTTPException(status_code=400, detail="Missing target person")
        
    other_person = next((p for p in data.PEOPLE if p["id"].lower() == person_id.lower()), None)
    if not other_person:
        other_person = next((p for p in data.EVENT_PEOPLE if p["id"].lower() == person_id.lower()), None)
        
    if not other_person and person_id.lower() in users:
        u_data = users[person_id.lower()]
        other_person = {
            "name": u_data.get("name") or f"User ({person_id})",
            "role": u_data.get("role", "BrewMatch User"),
            "pitch": u_data.get("pitch", ""),
            "resume_text": u_data.get("resume_text", "")
        }
        
    if not other_person:
        raise HTTPException(status_code=404, detail=f"Person {person_id} not found")
        
    return StreamingResponse(matching.stream_live_conversation(my_profile, other_person), media_type="text/event-stream")

@app.post("/api/event-match")
async def event_match(profile: Dict):
    """Runs matching against all 9 event attendees in parallel."""
    # Ensure profile for matching is valid
    if not profile.get("name"):
         return {"error": "Profile incomplete"}
    
    tasks = []
    for attendee in data.EVENT_PEOPLE:
        tasks.append(matching.run_bot_conversation(profile, attendee))
    
    # Run all in parallel
    results_list = await asyncio.gather(*tasks)
    
    # Mix the results with attendee data
    final_results = []
    for i, res in enumerate(results_list):
        attendee_res = data.EVENT_PEOPLE[i].copy()
        attendee_res["match_data"] = res # Full bot conversation data
        attendee_res["score"] = res.get("score", 50) # Use the AI score
        final_results.append(attendee_res)
        
    # Sort by score descending
    final_results.sort(key=lambda x: x["score"], reverse=True)
    return final_results

@app.get("/api/people")
async def get_people():
    # Start with original people list
    people_list = data.PEOPLE.copy()
    
    # Add actual users who have filled out their names
    for user_id, user_data in users.items():
        if user_data.get("name") and user_data.get("role"):
            # Ensure we don't duplicate if someone uses a name already in data.PEOPLE (optional)
            # Find if this user is already in the list by some unique attribute, or just append
            
            # Create a profile format compatible with Discover UI
            user_profile = {
                "id": user_id,
                "name": user_data["name"],
                "role": user_data["role"],
                "emoji": "☕", # Default emoji for new users
                "pitch": user_data.get("pitch", ""),
                "tags": user_data.get("goals", []),
                "resume_text": user_data.get("resume_text", "")
            }
            people_list.append(user_profile)
            
    return people_list

@app.get("/api/event-people")
async def get_event_people():
    return data.EVENT_PEOPLE

# --- Interaction Endpoints ---

@app.post("/api/request-chat")
async def request_chat(req: Dict):
    sender_id = req.get("sender_id")
    recipient_id = req.get("recipient_id")
    request_type_raw = req.get("request_type", "bot") # 'bot' or 'human'
    
    if not sender_id or not recipient_id:
        raise HTTPException(status_code=400, detail="Missing IDs")
    
    # 1. Supabase
    if get_supabase_data():
        itype = "bot_request" if request_type_raw == "bot" else "human_request"
        supabase.table("interactions").insert({
            "user_id": sender_id, "target_id": recipient_id, "type": itype
        }).execute()
        
    # 2. Update memory for current instance
    target_requests = requests_human if request_type_raw == 'human' else requests
    if recipient_id not in target_requests: target_requests[recipient_id] = []
    if sender_id not in target_requests[recipient_id]:
        target_requests[recipient_id].append(sender_id)
        
    return {"success": True}

@app.post("/api/record-bot-chat")
async def record_bot_chat(req: Dict):
    user_id = req.get("user_id").lower()
    person_id = req.get("person_id").lower()
    
    # 1. Supabase
    if get_supabase_data():
        supabase.table("interactions").insert({
            "user_id": user_id, "target_id": person_id, "type": "bot_chat"
        }).execute()
        
    # 2. Local memory
    if user_id not in bot_chats: bot_chats[user_id] = []
    if person_id not in bot_chats[user_id]:
        bot_chats[user_id].append(person_id)
        
    return {"success": True}

# --- Human Chat Endpoints ---

@app.get("/api/messages/{user1}/{user2}")
async def get_messages(user1: str, user2: str):
    if get_supabase_data():
        return await sync_messages(user1, user2)
    chat_id = "_".join(sorted([user1.lower(), user2.lower()]))
    return messages.get(chat_id, [])

@app.post("/api/send-message")
async def send_message(req: Dict):
    sender = req.get("sender").lower()
    recipient = req.get("recipient").lower()
    text = req.get("text")
    if not sender or not recipient or not text:
        raise HTTPException(status_code=400, detail="Missing fields")
    
    chat_id = "_".join(sorted([sender, recipient]))
    msg_time = datetime.now().strftime("%H:%M")
    msg_obj = {"sender": sender, "text": text, "time": msg_time}
    
    # 1. Supabase
    if get_supabase_data():
        supabase.table("messages").insert({
            "chat_id": chat_id, "sender": sender, "recipient": recipient,
            "text": text, "time": msg_time
        }).execute()
    
    # 2. Local memory
    if chat_id not in messages: messages[chat_id] = []
    messages[chat_id].append(msg_obj)
    return msg_obj

@app.get("/api/interactions/{user_id}")
async def get_interactions(user_id: str):
    user_id = user_id.lower()
    
    # 0. Fresh sync for this user
    await sync_users()
    await sync_interactions(user_id) 
    
    inbound_bot_requests = requests.get(user_id, [])
    inbound_human_requests = requests_human.get(user_id, [])
    user_connections = connections.get(user_id, [])
    
    # Enrich inbound requests
    def enrich_request_list(r_list):
        enriched = []
        for rid in r_list:
            u_data = users.get(rid, {})
            name = u_data.get("name") or f"User ({rid})"
            enriched.append({"id": rid, "name": name})
        return enriched

    enriched_bot_reqs = enrich_request_list(inbound_bot_requests)
    enriched_human_reqs = enrich_request_list(inbound_human_requests)
        
    enriched_connections = []
    for cid in user_connections:
        # Try finding in data.PEOPLE
        person = next((p for p in data.PEOPLE if p["id"].lower() == cid), None)
        if not person:
             person = next((p for p in data.EVENT_PEOPLE if p["id"].lower() == cid), None)
             
        # Try finding in users.json
        if not person and cid in users:
            uid_data = users[cid]
            person = {
                "id": cid,
                "name": uid_data.get("name") or f"User ({cid})",
                "role": uid_data.get("role") or "New BrewMatch User",
                "emoji": "☕",
                "pitch": uid_data.get("pitch", "Hasn't written a pitch yet."),
                "tags": uid_data.get("goals", []),
                "resume_text": uid_data.get("resume_text", "")
            }
            
        if person:
            enriched_connections.append(person)
            
    # Enrich bot chats
    user_bot_chats = bot_chats.get(user_id, [])
    enriched_bot_chats = []
    for bid in user_bot_chats:
        # Only include if NOT already in connections
        if bid in connections.get(user_id, []):
            continue
            
        person = next((p for p in data.PEOPLE if p["id"].lower() == bid), None)
        if not person:
             person = next((p for p in data.EVENT_PEOPLE if p["id"].lower() == bid), None)
        
        if not person and bid in users:
            uid_data = users[bid]
            person = {
                "id": bid,
                "name": uid_data.get("name") or f"User ({bid})",
                "role": uid_data.get("role") or "New BrewMatch User",
                "emoji": "☕",
                "pitch": uid_data.get("pitch", ""),
                "tags": uid_data.get("goals", []),
                "resume_text": uid_data.get("resume_text", "")
            }
        
        if person:
            enriched_bot_chats.append(person)
        
    # Calculate outbound requests
    outbound_requests = []
    for rid, senders in requests.items():
        if user_id in senders: outbound_requests.append(rid)
    
    outbound_human_requests = []
    for rid, senders in requests_human.items():
        if user_id in senders: outbound_human_requests.append(rid)

    return {
        "requests": enriched_bot_reqs,
        "human_requests": enriched_human_reqs,
        "outbound_requests": outbound_requests,
        "outbound_human_requests": outbound_human_requests,
        "connections": enriched_connections,
        "bot_chats": enriched_bot_chats,
        "reports": reports # All reports (will filter on frontend)
    }

@app.post("/api/save-report")
async def save_report(req: Dict):
    user_id = req.get("user_id").lower()
    person_id = req.get("person_id").lower()
    report_data = req.get("report")
    
    if not user_id or not person_id or not report_data:
        return {"success": False}
    
    # 1. Supabase
    if get_supabase_data():
        supabase.table("interactions").upsert({
            "user_id": user_id, "target_id": person_id, 
            "type": "report", "data": report_data
        }, on_conflict="user_id,target_id,type").execute()
    
    # 2. Local memory
    key = ":".join(sorted([user_id, person_id]))
    reports[key] = report_data
    return {"success": True}

@app.post("/api/respond-request")
async def respond_request(req: Dict):
    user_id = req.get("user_id").lower()
    sender_id = req.get("sender_id").lower()
    action = req.get("action") # 'accept' or 'decline'
    
    # 1. Check Bot Match requests
    if user_id in requests and sender_id in requests[user_id]:
        requests[user_id].remove(sender_id)
        if get_supabase_data():
            # Delete the request and add connection if accepted
            supabase.table("interactions").delete().match({"user_id": sender_id, "target_id": user_id, "type": "bot_request"}).execute()
            if action == 'accept':
                supabase.table("interactions").insert([
                    {"user_id": user_id, "target_id": sender_id, "type": "bot_chat"},
                    {"user_id": sender_id, "target_id": user_id, "type": "bot_chat"}
                ]).execute()
        
        if action == 'accept':
            if user_id not in bot_chats: bot_chats[user_id] = []
            if sender_id not in bot_chats: bot_chats[sender_id] = []
            bot_chats[user_id].append(sender_id)
            bot_chats[sender_id].append(user_id)
        return {"success": True}

    # 2. Check Human Chat requests
    if user_id in requests_human and sender_id in requests_human[user_id]:
        requests_human[user_id].remove(sender_id)
        if get_supabase_data():
            supabase.table("interactions").delete().match({"user_id": sender_id, "target_id": user_id, "type": "human_request"}).execute()
            if action == 'accept':
                supabase.table("interactions").insert([
                    {"user_id": user_id, "target_id": sender_id, "type": "connection"},
                    {"user_id": sender_id, "target_id": user_id, "type": "connection"}
                ]).execute()

        if action == 'accept':
            if user_id not in connections: connections[user_id] = []
            if sender_id not in connections: connections[sender_id] = []
            connections[user_id].append(sender_id)
            connections[sender_id].append(user_id)
        return {"success": True}
        
    return {"success": False, "detail": "Request not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
