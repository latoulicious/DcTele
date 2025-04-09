from telethon import TelegramClient, events
import requests
import json
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Your API credentials from my.telegram.org
API_ID = 123456    # Replace with your actual api_id (integer)
API_HASH = ''  # Replace with your actual api_hash (string)

# Discord webhook URL
DISCORD_WEBHOOK_URL = ''

# We'll identify channels by ID instead of username
# This will be populated by the get_channel_info function
CHANNELS_TO_MONITOR = []  # We'll fill this with IDs after running get_channel_info

# Initialize the Telegram client
client = TelegramClient('telegram_to_discord_session', API_ID, API_HASH)

async def get_channel_info():
    """Helper function to get channel IDs - run this once to find IDs"""
    logger.info("Scanning for available channels...")

    # Create a list to store channel information
    channels_found = []

    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            channel_info = {
                "name": dialog.name,
                "id": dialog.id,
                "username": dialog.entity.username if hasattr(dialog.entity, 'username') else "No username"
            }
            channels_found.append(channel_info)

            # Print information to console
            logger.info(f"Channel: {dialog.name} | ID: {dialog.id} | Username: {channel_info['username']}")

    logger.info(f"Found {len(channels_found)} channels.")

    # If we specifically want to find a channel with a name containing "lokerbumn"
    for channel in channels_found:
        if "lokerbumn" in channel["name"].lower() or (channel["username"] and "lokerbumn" in channel["username"].lower()):
            logger.info(f"Found potential match: {channel['name']} with ID {channel['id']}")

    return channels_found

@client.on(events.NewMessage(chats=CHANNELS_TO_MONITOR))
async def handle_new_message(event):
    """Process new messages from the monitored channels"""
    try:
        # Get channel information
        chat = await event.get_chat()
        channel_title = chat.title

        # Get message content
        message = event.message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Determine message type and content
        if message.text:
            content = message.text
            message_type = "Text"
        elif message.photo:
            content = message.caption if message.caption else "[Photo with no caption]"
            message_type = "Photo"
        elif message.video:
            content = message.caption if message.caption else "[Video with no caption]"
            message_type = "Video"
        elif message.document:
            content = f"[Document: {message.file.name if message.file and hasattr(message.file, 'name') else 'Unnamed'}]"
            content += f"\n{message.caption}" if message.caption else ""
            message_type = "Document"
        else:
            content = "[Other content type]"
            message_type = "Other"

        # Create Discord message payload
        discord_message = {
            "content": f"**New {message_type} Message from {channel_title}**\n{content}\n\n*Forwarded at {timestamp}*"
        }

        # Add message link if available
        if hasattr(message, 'id'):
            try:
                message_link = f"https://t.me/{chat.username}/{message.id}" if chat.username else f"Telegram channel: {channel_title}"
                discord_message["content"] += f"\n[View original message]({message_link})"
            except:
                pass

        # Send to Discord webhook
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(discord_message),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        logger.info(f"Successfully forwarded message from {channel_title} to Discord")

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")

async def main():
    # Start the client
    await client.start()
    logger.info("Client started successfully!")

    # First run: Scan for available channels and their IDs
    channels = await get_channel_info()

    # After running this function once and identifying the channels you want to monitor,
    # you should update the CHANNELS_TO_MONITOR list with the appropriate IDs
    # and comment out the get_channel_info() line for regular operation

    # Example of how you would update CHANNELS_TO_MONITOR after identifying your channels
    # global CHANNELS_TO_MONITOR
    # CHANNELS_TO_MONITOR = [1234567890, 9876543210]  # Replace with actual channel IDs

    # Run the client until disconnected
    await client.run_until_disconnected()

if __name__ == '__main__':
    # Run the main function
    asyncio.run(main())
