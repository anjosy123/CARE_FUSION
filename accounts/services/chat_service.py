import aiohttp
from django.conf import settings
import asyncio
import json

class MedicalChatService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent"
        
    async def get_response(self, message):
        try:
            # Add a small delay to prevent rapid-fire requests
            await asyncio.sleep(0.5)
            
            # Prepare the request payload
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [{
                        "text": message
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.8,
                    "maxOutputTokens": 1024
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            }
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                ) as response:
                    response_text = await response.text()
                    print(f"API Response Status: {response.status}")
                    print(f"Raw API Response: {response_text}")
                    
                    if response.status == 200:
                        data = json.loads(response_text)
                        if data.get("candidates"):
                            return data["candidates"][0]["content"]["parts"][0]["text"]
                    
                    return "I apologize, but I'm having trouble. Please try again."
            
        except Exception as e:
            print(f"Gemini API Error: {str(e)}")
            return "I apologize, but I'm having trouble with the service. Please try again." 