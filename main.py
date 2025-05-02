#!/usr/bin/env python3
"""
Telegram Bot Service
Listens for incoming Telegram messages and logs them to a file.
"""
import os
import logging
import importlib
import sys
import fcntl
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
from functions import log_message, help_command, stats_command, save_command, article_command, is_url

# Load environment variables
load_dotenv()

# Get DEBUG flag from environment
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

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

# File lock to prevent multiple instances
LOCK_FILE = "/tmp/solrem_bot.lock"
lock_file_handle = None

def acquire_lock():
    """
    Attempt to acquire a file lock to ensure only one instance is running.
    
    Returns:
        bool: True if lock was acquired successfully, False otherwise
    """
    global lock_file_handle
    
    try:
        # Open the lock file (creates it if it doesn't exist)
        lock_file_handle = open(LOCK_FILE, "w")
        
        # Try to acquire an exclusive lock (non-blocking)
        fcntl.flock(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Write PID to lockfile for debugging purposes
        lock_file_handle.write(str(os.getpid()))
        lock_file_handle.flush()
        
        logger.info(f"Lock acquired, PID: {os.getpid()}")
        return True
    except IOError:
        # Lock could not be acquired because another process has it
        if lock_file_handle:
            lock_file_handle.close()
            lock_file_handle = None
        logger.error("Another instance is already running (could not acquire lock)")
        return False

def release_lock():
    """
    Release the file lock if it was acquired.
    """
    global lock_file_handle
    
    if lock_file_handle:
        fcntl.flock(lock_file_handle, fcntl.LOCK_UN)
        lock_file_handle.close()
        logger.info("Lock released")
        # We don't remove the file as it's used for locking

def check_dependencies():
    """
    Check if required dependencies are available.
    """
    missing_deps = []
    
    # Check OpenAI
    try:
        importlib.import_module('openai')
    except ImportError:
        missing_deps.append('openai')
        logger.warning("OpenAI package not found. AI summary features will not work.")
    
    # Check BeautifulSoup
    try:
        importlib.import_module('bs4')
    except ImportError:
        missing_deps.append('beautifulsoup4')
        logger.warning("BeautifulSoup4 package not found. URL scraping features will not work.")
    
    return missing_deps

def main():
    """
    Main function to run the bot.
    """
    # Check if another instance is already running
    if not acquire_lock():
        logger.error("Another instance of the bot is already running. Exiting.")
        sys.exit(1)
    
    try:
        # Check dependencies
        missing_deps = check_dependencies()
        if missing_deps:
            logger.warning(f"Missing dependencies: {', '.join(missing_deps)}. Install with: pip install {' '.join(missing_deps)}")
        
        # Get token from environment variable
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.error("No token found. Set TELEGRAM_BOT_TOKEN in .env file.")
            return
        
        # Check for other required tokens
        if not os.getenv("OPENAI_TOKEN"):
            logger.warning("OPENAI_TOKEN not set. AI summary features will not work.")
        
        # Create the Application
        application = Application.builder().token(token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("s", save_command))
        application.add_handler(CommandHandler("a", article_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
        
        # Start the Bot
        logger.info("Bot started")
        application.run_polling()
    finally:
        # Always release the lock when exiting
        release_lock()

if __name__ == "__main__":
    main()
