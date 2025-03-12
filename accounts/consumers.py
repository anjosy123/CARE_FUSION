import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMessage, Staff, Organizations
from .services.gemini_service import GeminiService
from .services.chat_service import MedicalChatService
import asyncio

class TeamChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.team_id = self.scope['url_route']['kwargs']['team_id']
        self.room_group_name = f'chat_{self.team_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        sender_id = text_data_json['sender_id']
        sender_type = text_data_json['sender_type']

        # Save the message to the database
        await self.save_message(sender_id, sender_type, message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': sender_id,
                'sender_type': sender_type
            }
        )

    async def chat_message(self, event):
        message = event['message']
        sender_id = event['sender_id']
        sender_type = event['sender_type']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'sender_id': sender_id,
            'sender_type': sender_type
        }))

    @database_sync_to_async
    def save_message(self, sender_id, sender_type, message):
        team = Team.objects.get(id=self.team_id)
        if sender_type == 'staff':
            sender = Staff.objects.get(id=sender_id)
            TeamMessage.objects.create(team=team, sender=sender, content=message)
        elif sender_type == 'organization':
            organization = Organizations.objects.get(id=sender_id)
            TeamMessage.objects.create(team=team, organization=organization, content=message)

class PatientChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.chat_service = MedicalChatService()
            await self.accept()
            
            # Send welcome message
            await self.send(json.dumps({
                'type': 'chat_message',
                'message': "Hello! I'm your medical assistant. I can help you with medical information, understanding treatments, and general health questions. How can I assist you today?",
                'is_bot': True
            }))
            
        except Exception as e:
            print(f"Connection error: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get('message', '').strip()
            
            if not message:
                return
            
            # Show typing indicator
            await self.send(json.dumps({
                'type': 'typing_indicator',
                'show': True
            }))
            
            # Get response from Gemini
            response = await self.chat_service.get_response(message)
            
            # Add small delay to simulate natural typing
            await asyncio.sleep(1)
            
            # Hide typing indicator
            await self.send(json.dumps({
                'type': 'typing_indicator',
                'show': False
            }))
            
            # Send response
            await self.send(json.dumps({
                'type': 'chat_message',
                'message': response,
                'is_bot': True
            }))
            
        except Exception as e:
            print(f"Error in receive: {str(e)}")
            await self.send(json.dumps({
                'type': 'error',
                'message': 'I apologize, but I encountered an error. Please try again.'
            }))