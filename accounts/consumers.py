import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMessage, Staff, Organizations

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