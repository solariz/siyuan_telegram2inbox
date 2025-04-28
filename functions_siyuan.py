"""
Siyuan Inbox API Integration Module
Provides functions to interact with the Siyuan inbox API for adding cloud shorthand entries.
"""
import os
import logging
import json
import subprocess
import requests
from datetime import datetime
from typing import Tuple, Optional

# Get DEBUG flag from environment
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Configure logging
logger = logging.getLogger(__name__)

# API Configuration
API_URL = "https://liuyun.io/apis/siyuan/inbox/addCloudShorthand"

def check_connectivity() -> bool:
    """
    Check if the Siyuan API is reachable.
    Uses a GET request instead of HEAD to be more lenient with response codes.
    
    Returns:
        bool: True if API is reachable, False otherwise
    """
    try:
        # Use GET instead of HEAD and accept any response code
        response = requests.get(API_URL, timeout=5)
        logger.info(f"API connectivity check: {response.status_code == 200}")
        if DEBUG:
            logger.debug(f"API connectivity check response code: {response.status_code}")
        return True
    except requests.RequestException as e:
        logger.error(f"Connectivity check failed: {str(e)}")
        return False

def push_to_siyuan(content: str, title: Optional[str] = None) -> Tuple[bool, str]:
    """
    Push a message to the Siyuan inbox API.
    
    Args:
        content (str): The message content to send
        title (str, optional): Title for the message. If None, generates one with timestamp
        
    Returns:
        Tuple[bool, str]: (Success status, Response message)
    """
    # Get API token from environment
    api_token = os.getenv("SIYUAN_TOKEN")
    if not api_token:
        logger.error("SIYUAN_TOKEN not found in environment variables")
        return False, "SIYUAN_TOKEN not found in environment variables"

    # Generate title if not provided
    if not title:
        title = f"telegram {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Prepare the payload
    payload = {
        "title": title,
        "content": content
    }

    # Convert payload to JSON string
    payload_json = json.dumps(payload)

    # Log the request details - show title but not full content
    logger.info(f"Sending to Siyuan, title: {title[:50]}{'...' if len(title) > 50 else ''}")
    
    try:
        # Construct curl command
        curl_cmd = [
            "curl",
            "-X", "POST",
            API_URL,
            "-H", f"Authorization: token {api_token.strip()}",
            "-H", "Content-Type: application/json",
            "-d", payload_json,
            "-s"  # Silent mode to suppress progress output
        ]
        
        # Execute curl command
        result = subprocess.run(
            curl_cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        # Log the response
        if result.returncode == 0:
            logger.info("Message successfully sent to Siyuan")
            return True, "Message successfully sent to Siyuan inbox"
        else:
            error_msg = f"Failed to send message: {result.stderr}"
            logger.error(error_msg)
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Failed to execute curl command: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def process_telegram_message(message_text: str, user: str, hostname: str) -> Tuple[bool, str]:
    """
    Process a Telegram message and send it to Siyuan inbox.
    
    Args:
        message_text (str): The message text from Telegram
        user (str): Username of the sender
        hostname (str): Hostname of the sender
        
    Returns:
        Tuple[bool, str]: (Success status, Response message)
    """
    logger.info(f"Processing message from {user}")
    
    # Format the message content using the function from functions.py
    from functions import format_siyuan_content # Import here to avoid circular dependency if functions imports this module
    formatted_content = format_siyuan_content(message_text, user, hostname)
    
    # Generate title
    content_stripped = message_text.strip()
    is_url = content_stripped.startswith(('http://', 'https://'))
    
    if is_url:
        title = f"URL: {content_stripped[:30]}{'...' if len(content_stripped) > 30 else ''}"
        logger.info("Generated URL title")
    else:
        title = f"telegram {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        logger.info("Generated timestamp title")
    
    # Push to Siyuan
    return push_to_siyuan(formatted_content, title) 