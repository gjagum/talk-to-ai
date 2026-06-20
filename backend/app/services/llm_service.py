from openai import OpenAI
from app.config import Config

client = OpenAI(api_key=Config.OPENAI_API_KEY)
conversation_history = []

def get_system_message(persona: str = None):
    custom_behavior = persona if persona and persona.strip() else "Be warm, professional, and conversational."
    return {"role": "system", "content": f"""You are a highly realistic AI assistant answering a phone call.
Follow these rules strictly:
1. Speak exactly like a human on the phone. Use natural conversational fillers appropriately (e.g., "Hmm", "I see", "Got it").
2. Keep your responses extremely concise (1 to 2 sentences max). People do not want to listen to long monologues.
3. Never use markdown, bullet points, asterisks, or emojis. Only output the exact words you will speak out loud.
4. BEHAVIOR/PERSONA: {custom_behavior}"""}

async def generate_greeting(persona: str = None) -> str:
    conversation_history.clear()
    messages = [
        get_system_message(persona),
        {"role": "user", "content": "System: The phone call has just connected. Please say your initial greeting to the caller."}
    ]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=150,
        temperature=0.8
    )
    assistant_response = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": assistant_response})
    return assistant_response

async def generate_response(user_text: str, persona: str = None) -> str:
    conversation_history.append({"role": "user", "content": user_text})
    
    if len(conversation_history) > Config.MAX_CONVERSATION_HISTORY * 2:
        conversation_history.pop(0)
    
    messages = [get_system_message(persona)] + conversation_history
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=150,
        temperature=0.7
    )
    
    assistant_response = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": assistant_response})
    
    return assistant_response
