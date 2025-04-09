from telethon import TelegramClient, events
import requests
import json
import asyncio
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Your API credentials from my.telegram.org
API_ID = os.getenv('API_ID')  # Get from env or use default
API_HASH = os.getenv('API_HASH')  # Get from env or use default

# Define the mapping between Telegram channel IDs and Discord webhook URLs
# This will be our central configuration for routing messages
CHANNEL_WEBHOOK_MAPPING = {
    # Example format:
    # telegram_channel_id: "discord_webhook_url",
    1001667394379: "https://discord.com/api/webhooks/1359470961115791502/YGoimsjTocmsXNB3E-hlo4NL-7C02JxklFQVO_0b8fZ_JGOHYcgqSm2eK8KYF1f37vBC",
    1001048910279: "https://discord.com/api/webhooks/1359471095622926417/Oli3qnS_4xMJjXv1DOmSfI_3aiJINsrN5l55z91Cn7y1IS3OmZux8GOSAxpWrTwjvoGj",
}

# Default webhook URL for development/testing or for channels not in the mapping
DEFAULT_WEBHOOK_URL = os.getenv('DEFAULT_DISCORD_WEBHOOK', '')

# Initialize the Telegram client
client = TelegramClient('telegram_to_discord_session', API_ID, API_HASH)

async def get_channel_info():
    """Helper function to get channel IDs - run this once to find IDs"""
    logger.info("Scanning for available channels, groups, and chats...")
    
    channels_found = []
    
    async for dialog in client.iter_dialogs():
        # Check if it's a channel, group, or chat
        entity_type = "Channel" if dialog.is_channel else "Group" if dialog.is_group else "Chat"
        
        # Get entity info
        entity_info = {
            "name": dialog.name,
            "id": dialog.id,
            "type": entity_type,
            "username": dialog.entity.username if hasattr(dialog.entity, 'username') else "No username"
        }
        channels_found.append(entity_info)
        
        # Print information to console
        logger.info(f"{entity_type}: {dialog.name} | ID: {dialog.id} | Username: {entity_info['username']}")
    
    logger.info(f"Found {len(channels_found)} entities.")
    
    # If we specifically want to find entities with specific keywords
    keywords = ["lokerbumn", "lowongan", "kerja", "job"]
    for entity in channels_found:
        for keyword in keywords:
            if keyword in entity["name"].lower() or (entity["username"] and keyword in entity["username"].lower()):
                logger.info(f"Found potential match: {entity['name']} with ID {entity['id']} (Type: {entity['type']})")
                break
    
    return channels_found

@client.on(events.NewMessage)
async def handle_new_message(event):
    """Process new messages from all sources and route them to the appropriate Discord webhook"""
    try:
        # Get the chat this message is from
        chat = await event.get_chat()
        chat_id = chat.id
        
        # Determine which Discord webhook to use for this channel
        # If the channel is in our mapping, use its specific webhook, otherwise use default
        webhook_url = CHANNEL_WEBHOOK_MAPPING.get(chat_id, DEFAULT_WEBHOOK_URL)
        
        # If no webhook is available for this channel, skip processing
        if not webhook_url:
            # Optionally log that we're skipping this channel
            logger.debug(f"No webhook configured for channel ID {chat_id}, skipping message")
            return
        
        # Get channel/group/chat name
        if hasattr(chat, 'title'):
            source_name = chat.title
        elif hasattr(chat, 'first_name'):
            source_name = f"{chat.first_name} {chat.last_name if hasattr(chat, 'last_name') else ''}"
        else:
            source_name = f"Chat ID: {chat_id}"
        
        # Get message content
        message = event.message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Handle sender information
        sender = await event.get_sender()
        sender_name = "Unknown"
        if sender:
            if hasattr(sender, 'first_name'):
                sender_name = f"{sender.first_name} {sender.last_name if hasattr(sender, 'last_name') and sender.last_name else ''}"
            elif hasattr(sender, 'title'):
                sender_name = sender.title
            else:
                sender_name = str(sender.id)
        
        # Get thread or category information if available
        thread_info = ""
        if hasattr(message, 'reply_to') and message.reply_to:
            try:
                replied_msg = await client.get_messages(chat, ids=message.reply_to.reply_to_msg_id)
                if replied_msg:
                    thread_info = f"(In reply to: {replied_msg.sender.first_name if hasattr(replied_msg.sender, 'first_name') else 'Unknown'})"
            except Exception:
                pass
        
        # Determine message type and content - with safer attribute checking
        content = ""
        message_type = "Unknown"
        
        if hasattr(message, 'text') and message.text:
            content = message.text
            message_type = "Text"
        elif hasattr(message, 'photo') and message.photo:
            content = message.caption if hasattr(message, 'caption') and message.caption else "[Photo with no caption]"
            message_type = "Photo"
        elif hasattr(message, 'video') and message.video:
            content = message.caption if hasattr(message, 'caption') and message.caption else "[Video with no caption]"
            message_type = "Video"
        elif hasattr(message, 'document') and message.document:
            file_name = "Unnamed"
            if hasattr(message.document, 'attributes'):
                for attr in message.document.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        file_name = attr.file_name
                        break
            
            content = f"[Document: {file_name}]"
            if hasattr(message, 'caption') and message.caption:
                content += f"\n{message.caption}"
            message_type = "Document"
        elif hasattr(message, 'sticker') and message.sticker:
            emoji = message.sticker.emoji if hasattr(message.sticker, 'emoji') and message.sticker.emoji else "Unknown"
            content = f"[Sticker: {emoji}]"
            message_type = "Sticker"
        elif hasattr(message, 'poll') and message.poll:
            content = f"[Poll: {message.poll.question}]"
            message_type = "Poll"
        else:
            content = "[Unsupported message type]"
        
        # Create Discord message payload with more detailed information
        discord_message = {
            "content": f"**New {message_type} Message**\n**From:** {source_name}\n**Sender:** {sender_name} {thread_info}\n\n{content}\n\n*Forwarded at {timestamp}*"
        }
        
        # Add message link if available
        if hasattr(chat, 'username') and chat.username and hasattr(message, 'id'):
            try:
                message_link = f"https://t.me/{chat.username}/{message.id}"
                discord_message["content"] += f"\n[View original message]({message_link})"
            except Exception:
                pass
        
        # Send to the appropriate Discord webhook
        response = requests.post(
            webhook_url,
            data=json.dumps(discord_message),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        logger.info(f"Successfully forwarded message from {source_name} to Discord webhook")
    
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")
        # Print more detailed error info
        import traceback
        logger.error(traceback.format_exc())

async def main():
    # Start the client
    await client.start()
    logger.info("Client started successfully!")
    
    # First run: Scan for available channels and their IDs
    channels = await get_channel_info()
    
    # Check if we have any channel-webhook mappings configured
    if not CHANNEL_WEBHOOK_MAPPING and not DEFAULT_WEBHOOK_URL:
        logger.warning("No channel-webhook mappings or default webhook URL configured. Messages will be scanned but not forwarded.")
    else:
        logger.info(f"Configured to monitor {len(CHANNEL_WEBHOOK_MAPPING)} specific channels with dedicated webhooks.")
        if DEFAULT_WEBHOOK_URL:
            logger.info("Default webhook URL is set for any non-mapped channels.")
    
    # Run the client until disconnected
    await client.run_until_disconnected()

if __name__ == '__main__':
    # Run the main function
    asyncio.run(main())
