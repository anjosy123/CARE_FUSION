import google.generativeai as genai
from django.conf import settings
import asyncio

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
        
    async def get_response(self, message):
        try:
            # Add a small delay to prevent rapid-fire requests
            await asyncio.sleep(0.5)
            
            response = await self.model.generate_content_async(
                f"You are a helpful medical assistant chatbot. Respond to: {message}"
            )
            if response and response.text:
                return response.text
            return "I apologize, but I couldn't generate a response. Please try again."
            
        except Exception as e:
            print(f"Gemini API Error: {str(e)}")  # Log the error
            return "I apologize, but I'm having trouble connecting to the service. Please try again in a moment." 