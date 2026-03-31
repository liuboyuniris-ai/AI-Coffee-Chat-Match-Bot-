# ☕ BrewMatch — AI-Driven Coffee Chat Matching

BrewMatch is a premium networking application that uses **AI Avatars (AI Twins)** to facilitate meaningful human connections. Instead of blindly matching, BrewMatch lets your AI representatives "chat it out" first, providing you with a compatibility report before you decide to meet in person.

![BrewMatch UI Concept](https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&q=80&w=1000)

## 🚀 The Networking Funnel

BrewMatch implements a unique 4-stage funnel to ensure high-quality networking:

1.  **Discover**: Browse profiles of interesting people. When you find a potential match, click **"Request Bot Chat"**.
2.  **Bot Match**: Once accepted, your AI Twin and their AI Twin engage in a real-time, simulated discovery conversation. You get a detailed **Synergy Report** including:
    *   Match Score (0-100)
    *   3 Key Reasons why you should connect
    *   2 Personal Icebreakers for your actual meeting
3.  **Human Request**: After reviewing the AI's analysis, you can choose to send a **"Human Chat Request"**. 
4.  **Connections**: Once mutually agreed, you enter a real-time human chat room to finalize your coffee chat details. Your **AI Insights** remain accessible in the chat sidebar as a handy reference.

## ✨ Key Features

*   **Real-time AI Chat Simulation**: Watch the bots converse in real-time using Server-Sent Events (SSE).
*   **Persistent AI Reports**: Match results are saved and can be revisited even during the human conversation.
*   **Aesthetic Glassmorphism UI**: A modern, responsive design with smooth transitions and premium typography.
*   **Self-Contained Logic**: No complex database setup required — uses structured JSON for persistent storage.

## 🛠 Tech Stack

*   **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.9+)
*   **AI Engine**: [Google Gemini](https://ai.google.dev/) (via OpenAI-compatible API)
*   **Frontend**: Vanilla HTML5, CSS3 (Modern Hooks & Flexbox), and JavaScript
*   **Streaming**: Server-Sent Events (SSE) for lag-free bot dialogues
*   **Persistence**: JSON-based local data store (`users.json`, `interactions.json`, `messages.json`)

## 🚦 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/brewmatch.git
cd brewmatch
```

### 2. Set up a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory:
```env
LLM_API_KEY="your_gemini_api_key_here"
LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
LLM_MODEL="gemini-1.5-flash"
```

### 4. Run the Application
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Visit `http://localhost:8000` in your browser.

## 📁 Project Structure

*   `main.py`: FastAPI application, endpoints, and data persistence logic.
*   `matching.py`: AI Twin conversation logic and compatibility evaluation.
*   `data.py`: Pre-seeded event attendee data and initial profiles.
*   `static/index.html`: Self-contained frontend application.
*   `interactions.json`: Stores requests, connections, and AI reports.
*   `users.json`: Stores user profile data and hashed credentials.
*   `messages.json`: Stores human-to-human chat history.

## 📝 License
MIT License. Feel free to use and adapt this for your own networking events!
