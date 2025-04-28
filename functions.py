"""
Utility functions for the Telegram bot.
"""
import os
import json
import logging
import subprocess
import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
import socket

# Get DEBUG flag from environment
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Define a constant for basic info logging regardless of DEBUG setting
BASIC_INFO = os.getenv("DEBUG", "False").lower() != "false"

# Get user-facing messages from environment or use defaults
TXT_GENERAL_HELP = os.getenv("TXT_GENERAL_HELP", "Hmm, check /help to see how I may assist you...")
TXT_MISSING_CONTENT = os.getenv("TXT_MISSING_CONTENT", "Please provide content to save after the /s command")
TXT_SEND_FAILED = os.getenv("TXT_SEND_FAILED", "❌ couldn't send to Siyuan")
TXT_SEND_SUCCESS = os.getenv("TXT_SEND_SUCCESS", "✔️ sent")
TXT_SEND_SUCCESS_WITH_TITLE = os.getenv("TXT_SEND_SUCCESS_WITH_TITLE", "✔️ sent as \"{title}\"")
TXT_HELP_TEXT = os.getenv("TXT_HELP_TEXT", """
Available commands:
/help - Show this help message
/s [message] - Save a message to SiYuan
/stats - Get system statistics

You can also send any message, but it won't be saved to SiYuan 
without using the /s command.
""")

# Configure logging
logging_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    format="%(levelname)s: %(message)s",
    level=logging_level,
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler("bot.log")  # File output
    ]
)

# Set telegram library logger to WARNING to reduce noise
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def is_url(text):
    """
    Check if the given text is a URL.
    
    Args:
        text: Text to check
        
    Returns:
        bool: True if text is a URL, False otherwise
    """
    # Simple pattern to detect URLs - more permissive than the previous one
    url_pattern = re.compile(
        r'^https?://[^\s]+\.[^\s]+',
        re.IGNORECASE
    )
    
    # Alternative simpler check as fallback
    is_simple_url = text.strip().startswith(('http://', 'https://'))
    
    result = bool(url_pattern.match(text.strip())) or is_simple_url
    
    # Only log the full URL in debug mode
    if result:
        if DEBUG:
            logger.debug(f"Text identified as URL: {text.strip()}")
        else:
            logger.info("URL detected")
    
    return result

def setup_message_log(filename="messages.log"):
    """
    Set up a file logger for received messages.
    
    Args:
        filename: Name of the log file
    
    Returns:
        logging.Logger: Configured logger instance
    """
    message_logger = logging.getLogger("message_log")
    message_logger.setLevel(logging.INFO)
    
    # Create file handler
    file_handler = logging.FileHandler(filename)
    file_handler.setLevel(logging.INFO)
    
    # Add handler to logger
    message_logger.addHandler(file_handler)
    
    return message_logger

# Initialize message logger
message_logger = setup_message_log()

def is_authorized_user(user_id: int) -> bool:
    """
    Check if the user is authorized based on ALLOWED_USERIDS environment variable.
    
    Args:
        user_id: Telegram user ID to check
        
    Returns:
        bool: True if user is authorized, False otherwise
    """
    allowed_users_str = os.getenv("ALLOWED_USERIDS", "")
    if not allowed_users_str:
        logger.warning("ALLOWED_USERIDS not set in environment variables")
        return False
        
    try:
        allowed_users = [int(uid.strip()) for uid in allowed_users_str.split(",")]
        return user_id in allowed_users
    except ValueError:
        logger.error("Invalid format in ALLOWED_USERIDS environment variable")
        return False

def is_authorized_chat(chat_id: int) -> bool:
    """
    Check if the chat is authorized based on ALLOWED_CHATIDS environment variable.
    
    Args:
        chat_id: Telegram chat ID to check
        
    Returns:
        bool: True if chat is authorized, False otherwise
    """
    allowed_chats_str = os.getenv("ALLOWED_CHATIDS", "")
    if not allowed_chats_str:
        logger.warning("ALLOWED_CHATIDS not set in environment variables")
        return False
        
    try:
        allowed_chats = [int(cid.strip()) for cid in allowed_chats_str.split(",")]
        return chat_id in allowed_chats
    except ValueError:
        logger.error("Invalid format in ALLOWED_CHATIDS environment variable")
        return False

def clean_output(text: str) -> str:
    """
    Clean the output by removing ANSI color codes and non-ASCII characters.
    
    Args:
        text: The text to clean
        
    Returns:
        str: Cleaned text
    """
    # Remove ANSI color codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    
    # Remove non-ASCII characters
    text = ''.join(char for char in text if ord(char) < 128)
    
    # Remove any remaining control characters
    text = ''.join(char for char in text if char.isprintable() or char.isspace())
    
    # Fix disk path formatting
    text = re.sub(r'Disk \(8;;file:////8;;\):', 'Disk (/):', text)
    
    return text

async def get_system_stats() -> str:
    """
    Get system statistics using fastfetch.
    
    Returns:
        str: System statistics output
    """
    try:
        result = subprocess.run(
            ["fastfetch", "-c", "/opt/fastfetch.jsonc"],
            capture_output=True,
            text=True,
            check=True
        )
        return clean_output(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running fastfetch: {e}")
        return "Error getting system statistics"
    except Exception as e:
        logger.error(f"Unexpected error running fastfetch: {e}")
        return "Error getting system statistics"

async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Log incoming messages without sending to SiYuan.
    
    Args:
        update: The update object from Telegram
        context: The context object from Telegram
    """
    # Get message details
    message = update.message
    user = message.from_user.username or message.from_user.first_name
    
    # Log basic message receipt information without content
    logger.info(f"Received message from {user}")
    
    # Only log full message content if DEBUG is enabled
    if DEBUG:
        logger.debug(f"Message content: {message.text}")

def format_siyuan_content(content: str, user: str, hostname: str) -> str:
    """
    Format the message content with markdown template for SiYuan.
    Handles both regular text and URLs.
    
    Args:
        content (str): The raw message content
        user (str): Username of the sender
        hostname (str): Hostname of the sender
        
    Returns:
        str: Formatted markdown content
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    content_stripped = content.strip()
    
    if is_url(content_stripped):
        logger.info("Formatting message as URL bookmark")
        # Format as a clickable link if it's a URL
        return f"""## URL Bookmark
**SUBMIT:** {timestamp}
**BY:** {user}@{hostname}

[{content_stripped}]({content_stripped})
"""
    else:
        logger.info("Formatting message as text message")
        # Regular formatting for normal text
        return f"""## input via telegram
**SUBMIT:** {timestamp}
**BY:** {user}@{hostname}

```
{content}
```"""

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command. Displays available commands and their descriptions.
    
    Args:
        update: The update object from Telegram
        context: The context object from Telegram
    """
    await update.message.reply_text(TXT_HELP_TEXT)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /stats command. Displays system statistics.
    
    Args:
        update: The update object from Telegram
        context: The context object from Telegram
    """
    stats = await get_system_stats()
    await update.message.reply_text(f"```\n{stats}\n```", parse_mode="Markdown")

async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /s command. Saves the following message to SiYuan.
    
    Args:
        update: The update object from Telegram
        context: The context object from Telegram
    """
    # Check if there's any text after the command
    if not context.args:
        await update.message.reply_text(TXT_MISSING_CONTENT)
        return
    
    # Get message details
    message = update.message
    user = message.from_user.username or message.from_user.first_name
    hostname = socket.gethostname()
    
    # Log basic information about save command
    logger.info(f"Save command from {user}")
    
    # Combine all arguments into a single message text
    message_text = ' '.join(context.args)
    
    # Check if the message is a URL
    is_url_message = is_url(message_text)
    
    # Import these here to avoid circular imports
    from functions_ai import generate_summary
    from functions_siyuan import process_telegram_message, push_to_siyuan
    
    # Generate AI summary for longer messages or URLs
    title = None
    ai_used = False
    summary_text = None
    custom_title = None
    
    if len(message_text) > 128 or is_url_message:
        if is_url_message:
            logger.info("Processing URL message")
        else:
            logger.info("Processing long message, generating AI summary")
            
        success, summary_result = generate_summary(message_text)
        
        if success:
            ai_used = True
            summary_text = summary_result['h']
            
            # Format title with date and summary heading
            current_date = datetime.now().strftime("%Y-%m-%d")
            title = f"{current_date} {summary_result['h']}"
            custom_title = summary_result['h']
            
            # Format URL as markdown link if it's a URL
            message_display = message_text
            if is_url_message:
                url = message_text.strip()
                message_display = f"[{url}]({url})"
            
            # Format content with summary
            formatted_content = f"""## {summary_result['h']}
{summary_result['s']}

## input via telegram
**SUBMIT:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**BY:** {user}@{hostname}

{message_display}
"""
            
            # Push to Siyuan with the enhanced content
            success, response = push_to_siyuan(formatted_content, title)
        else:
            logger.error(f"Failed to generate summary: {summary_result}")
            # Format URL for regular processing
            if is_url_message:
                url = message_text.strip()
                # Use the new central formatter
                formatted_content = format_siyuan_content(message_text, user, hostname)
                # Set a simple title for URLs
                url_title = f"URL: {url[:30]}{'...' if len(url) > 30 else ''}"
                custom_title = "URL bookmark"
                success, response = push_to_siyuan(formatted_content, url_title)
            else:
                # Fall back to regular processing if summary generation fails
                success, response = process_telegram_message(message_text, user, hostname)
    else:
        # Process normally for short messages
        if is_url_message:
            url = message_text.strip()
            # Use the new central formatter
            formatted_content = format_siyuan_content(message_text, user, hostname)
            # Set a simple title for URLs
            url_title = f"URL: {url[:30]}{'...' if len(url) > 30 else ''}"
            custom_title = "URL bookmark"
            success, response = push_to_siyuan(formatted_content, url_title)
        else:
            # Regular non-URL processing
            success, response = process_telegram_message(message_text, user, hostname)
    
    if not success:
        logger.error(f"Failed to forward message to Siyuan: {response}")
        await message.reply_text(TXT_SEND_FAILED)
    else:
        logger.info(f"Message successfully forwarded to Siyuan as {custom_title or title or 'message'}")
        
        # Customize success message based on whether AI was used or there's a custom title
        if ai_used and summary_text:
            # Send success message with the AI summary
            await context.bot.send_message(
                chat_id=message.chat_id,
                text=TXT_SEND_SUCCESS_WITH_TITLE.format(title=summary_text)
            )
        elif custom_title:
            # Send success message with the custom title
            await context.bot.send_message(
                chat_id=message.chat_id,
                text=TXT_SEND_SUCCESS_WITH_TITLE.format(title=custom_title)
            )
        else:
            # Send simple emoji message for regular messages
            await context.bot.send_message(
                chat_id=message.chat_id,
                text=TXT_SEND_SUCCESS
            ) 