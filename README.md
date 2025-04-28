# Telegram SiYuan Bot

A Telegram bot that logs messages and forwards them to a SiYuan Inbox.

## Configuration

Copy the `sample.env` file to `.env` and edit the values:

```bash
cp sample.env .env
```

Then edit the `.env` file with your specific configuration:

### Required Settings

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from BotFather
- `ALLOWED_USERIDS`: Comma-separated list of Telegram user IDs allowed to use the bot
- `ALLOWED_CHATIDS`: Comma-separated list of Telegram chat IDs where the bot can operate
- `SIYUAN_TOKEN`: Your SiYuan API token

### Optional Settings

- `DEBUG`: Set to "True" to enable debug logging (default: False)
- `OPENAI_TOKEN`: OpenAI API token for summary generation 
- `OPENAI_MODEL`: OpenAI model to use (default: gpt-3.5-turbo)

### Customizable Messages

You can customize these user-facing messages by editing these variables in the `.env` file:

- `TXT_GENERAL_HELP`: Message shown when user sends text without a command
- `TXT_MISSING_CONTENT`: Message shown when /s command is used without content
- `TXT_SEND_FAILED`: Message shown when sending to SiYuan fails
- `TXT_SEND_SUCCESS`: Message shown when sending to SiYuan succeeds
- `TXT_SEND_SUCCESS_WITH_TITLE`: Message shown when sending to SiYuan succeeds with a title (use {title} placeholder)

Note: The help text (`TXT_HELP_TEXT`) is defined in the code and cannot be customized via .env file due to Python-dotenv limitations with multiline values.

## Commands

- `/help` - Show help message
- `/s [message]` - Save a message to SiYuan
- `/stats` - Get system statistics

## Features

- Log messages to a file
- Save messages to SiYuan Inbox
- Generate AI summaries for longer messages
- Handle URL forwarding with auto-summarization
- System statistics with fastfetch

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure the `.env` file
4. Run the bot: `python main.py`

## Create Service User

For security reasons, the bot should run as a non-root user. Here's how to create a limited user:

1. Create a new user with a limited shell:
   ```bash
   sudo useradd -r -s /usr/sbin/nologin telegrambot
   ```

2. Create a directory for the bot and set permissions:
   ```bash
   sudo mkdir -p /opt/solrem_bot
   sudo chown telegrambot:telegrambot /opt/solrem_bot
   ```

3. Copy the bot files to the new directory:
   ```bash
   sudo cp -r * /opt/solrem_bot/
   sudo chown -R telegrambot:telegrambot /opt/solrem_bot
   ```

## Systemd Service Setup

Create a systemd service file to run the bot as a service:

1. Create a file in `/etc/systemd/system/telegram-rem-bot.service`:
   ```
   [Unit]
   Description=Telegram Bot REM
   After=network.target

   [Service]
   Type=simple
   User=telegrambot
   Group=telegrambot
   WorkingDirectory=/opt/solrem_bot/
   ExecStart=/usr/bin/python3 /opt/solrem_bot/main.py
   Restart=on-failure
   StandardOutput=journal
   StandardError=journal
   Environment=PYTHONUNBUFFERED=1

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start the service:
   ```
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-rem-bot.service
   sudo systemctl start telegram-rem-bot.service
   ```

3. Check the service status and logs:
   ```
   sudo systemctl status telegram-rem-bot.service
   sudo journalctl -u telegram-rem-bot.service -f
   ```

## Log File Format

Messages are logged in JSON format with the following fields:
- timestamp
- user_id
- username
- first_name
- last_name
- chat_id
- message_id
- text 

## Advanced Features

### AI Summarization

For messages longer than 128 characters, the bot uses OpenAI to generate a concise summary. This summary is used as the title for the Siyuan note and added to the note content for context.

The title format is: `YYYY-MM-DD Summary Text`

### URL Scraping and Summarization

When a URL is posted in the chat, the bot will:
1. Scrape the web page content
2. Strip HTML tags and extract the text
3. Send the content to OpenAI for summarization
4. Create a Siyuan note with the summary and original URL

This allows you to quickly capture and summarize web content without copying and pasting.

## Requirements

- Python 3.7+
- python-telegram-bot
- python-dotenv
- openai
- requests
- beautifulsoup4 
