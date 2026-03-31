import asyncio
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import data
import matching

app = FastAPI(title="BrewMatch — AI Coffee Chat Matching App")

# Global interaction store
# requests: { recipient_id: [sender_id, ...] }
# connections: { user_id: [connected_id, ...] }
requests = {}
connections = {}

USERS_FILE = "users.json"
DATA_FILE = "interactions.json"

def load_data():
    global users, requests, connections
    
    # Load Users
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
        except Exception as e:
            print(f"Error loading users: {e}")
            users = {}
            
    # Load Interactions
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                saved_data = json.load(f)
                requests = saved_data.get("requests", {})
                connections = saved_data.get("connections", {})
        except Exception as e:
            print(f"Error loading interactions: {e}")
            requests = {}
            connections = {}

def save_data():
    try:
        # Save Users
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)
            
        # Save Interactions
        with open(DATA_FILE, "w") as f:
            json.dump({"requests": requests, "connections": connections}, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

import os
import json

# Initial load
load_data()

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
    
    if user_id not in users:
        # Initialize empty profile with password if new user
        users[user_id] = {
            "id": user_id,
            "password": password,
            "name": "",
            "role": "",
            "pitch": "",
            "goals": [],
            "resume_text": ""
        }
        save_data()
    else:
        # Verify password
        if users[user_id].get("password") != password:
            raise HTTPException(status_code=401, detail="Invalid password")
            
    # Return profile without password
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
    
    # Preserve password if it exists
    password = users.get(user_id, {}).get("password")
    
    users[user_id] = profile.model_dump()
    
    if password:
        users[user_id]["password"] = password
    
    save_data()
    
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
    
    if not sender_id or not recipient_id:
        raise HTTPException(status_code=400, detail="Missing IDs")
    
    if recipient_id not in requests:
        requests[recipient_id] = []
    
    if sender_id not in requests[recipient_id]:
        requests[recipient_id].append(sender_id)
        save_data()
        
    return {"success": True}

@app.get("/api/interactions/{user_id}")
async def get_interactions(user_id: str):
    user_id = user_id.lower()
    inbound_requests = requests.get(user_id, [])
    user_connections = connections.get(user_id, [])
    
    # Enrich inbound requests with user names
    enriched_requests = []
    for rid in inbound_requests:
        user_data = users.get(rid, {})
        name = user_data.get("name")
        if not name:
            name = f"User ({rid})"
        enriched_requests.append({"id": rid, "name": name})
        
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
        
    return {
        "requests": enriched_requests,
        "connections": enriched_connections
    }

@app.post("/api/respond-request")
async def respond_request(req: Dict):
    user_id = req.get("user_id").lower()
    sender_id = req.get("sender_id").lower()
    action = req.get("action") # 'accept' or 'decline'
    
    if user_id in requests and sender_id in requests[user_id]:
        requests[user_id].remove(sender_id)
        
        if action == 'accept':
            # Add to both connections
            if user_id not in connections: connections[user_id] = []
            if sender_id not in connections: connections[sender_id] = []
            
            if sender_id not in connections[user_id]: connections[user_id].append(sender_id)
            if user_id not in connections[sender_id]: connections[sender_id].append(user_id)
            
        save_data()
        return {"success": True}
        
    return {"success": False, "detail": "Request not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
