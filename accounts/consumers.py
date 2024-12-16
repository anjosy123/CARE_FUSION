import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMessage, Staff, Organizations

class TeamChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.team_id = self.scope['url_route']['kwargs']['team_id']
        self.room_group_name = f'team_{self.team_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender_id = data['sender_id']
        sender_type = data['sender_type']

        # Save message to database
        await self.save_message(message, sender_id, sender_type)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': sender_id,
                'sender_type': sender_type,
                'sender_name': await self.get_sender_name(sender_id, sender_type)
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_type': event['sender_type'],
            'sender_name': event['sender_name']
        }))

    @database_sync_to_async
    def save_message(self, message, sender_id, sender_type):
        team = Team.objects.get(id=self.team_id)
        if sender_type == 'staff':
            sender = Staff.objects.get(id=sender_id)
            TeamMessage.objects.create(
                team=team,
                sender=sender,
                content=message,
                sender_type='staff'
            )
        else:
            organization = Organizations.objects.get(id=sender_id)
            TeamMessage.objects.create(
                team=team,
                organization=organization,
                content=message,
                sender_type='organization'
            )

    @database_sync_to_async
    def get_sender_name(self, sender_id, sender_type):
        if sender_type == 'staff':
            sender = Staff.objects.get(id=sender_id)
            return sender.get_full_name()
        else:
            organization = Organizations.objects.get(id=sender_id)
            return organization.org_name