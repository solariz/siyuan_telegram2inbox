"""
AI-related functionality for the Telegram bot.
"""
import os
import json
import logging
import re
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# Get DEBUG flag from environment
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Configure logging locally to avoid circular imports
logger = logging.getLogger("functions_ai")

# User agent for web scraping
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Maximum content length for OpenAI API requests
MAX_CONTENT_LENGTH = 2048

def get_openai_client():
    """
    Initialize and return an OpenAI client using credentials from environment.
    
    Returns:
        OpenAI: Configured OpenAI client
    """
    api_key = os.getenv("OPENAI_TOKEN")
    if not api_key:
        logger.error("No OpenAI API key found. Set OPENAI_TOKEN in .env file.")
        return None
    
    return OpenAI(api_key=api_key)

def scrape_url_content(url):
    """
    Scrape content from a URL.
    
    Args:
        url: URL to scrape
        
    Returns:
        tuple: (success, content) where content is either the scraped text or error message
    """
    # Log basic info about scraping without revealing the URL
    logger.info("Starting URL scraping")
    
    # Only log the full URL in debug mode
    if DEBUG:
        logger.debug(f"Scraping URL: {url}")
        
    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        if DEBUG:
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response content type: {response.headers.get('Content-Type', 'unknown')}")
        else:
            logger.info(f"Response received: {response.status_code}")
        
        # Use BeautifulSoup to parse HTML and extract text
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get the page title
        page_title = soup.title.string if soup.title else "No title"
        logger.info(f"Page title extracted: {page_title[:50]}{'...' if len(page_title) > 50 else ''}")
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
        
        # Get text
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up the text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Add the URL and title at the beginning for context
        text = f"URL: {url}\nTitle: {page_title}\n\nContent:\n{text}"
        
        # Truncate to fit within MAX_CONTENT_LENGTH
        if len(text) > MAX_CONTENT_LENGTH:
            logger.info(f"Truncating content from {len(text)} to {MAX_CONTENT_LENGTH} chars")
            text = text[:MAX_CONTENT_LENGTH - 3] + "..."
        else:
            logger.info(f"Extracted {len(text)} chars of text")
        
        logger.info("URL scraping successful")
        return True, text
    
    except Exception as e:
        logger.error(f"Error scraping URL: {e}")
        return False, str(e)

def truncate_for_openai(text):
    """
    Truncate text to ensure it's within the OpenAI API limits.
    
    Args:
        text: The text to truncate
        
    Returns:
        str: Truncated text within the API limits
    """
    if len(text) <= MAX_CONTENT_LENGTH:
        return text
    
    logger.info(f"Truncating text from {len(text)} to {MAX_CONTENT_LENGTH} chars for OpenAI API")
    return text[:MAX_CONTENT_LENGTH - 3] + "..."

def generate_summary(text, is_scraped=False):
    """
    Generate a concise summary of the provided text using OpenAI.
    
    Args:
        text: The text to summarize
        is_scraped: Whether the text is from a scraped webpage
        
    Returns:
        tuple: (success, result) where result is either the summary dict or error message
    """
    logger.info("Starting summary generation")
    
    # Check if the entire message is just a URL (trim whitespace)
    clean_text = text.strip()
    
    # Import is_url here to avoid circular imports
    from functions import is_url
    
    # Check if the text is a URL and we haven't already scraped it
    if not is_scraped and is_url(clean_text):
        logger.info("Detected URL, will scrape content first")
        success, content = scrape_url_content(clean_text)
        
        if success:
            logger.info("Successfully scraped URL content")
            # Call generate_summary again with the scraped content and is_scraped=True
            return generate_summary(content, is_scraped=True)
        else:
            logger.error(f"Failed to scrape URL: {content}")
            # Fall back to summarizing the URL itself
            logger.info("Falling back to summarizing the URL directly")
    
    client = get_openai_client()
    if not client:
        return False, "OpenAI API key not configured"
    
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    logger.info(f"Using OpenAI model: {model}")
    
    try:
        # Ensure the text is within limits for the API
        truncated_text = truncate_for_openai(text)
        
        system_prompt = "You are a summarization assistant. Create concise summaries that instantly reveal the relevant ontext when read.."
        user_prompt = f"Return in JSON like: {{\"h\": \"headine, max 2 to 5 words\",\"s\": \"summary, this is a summary telling what the given input is about, 1-3 sentence long.\" }}"
        
        if is_scraped:
            user_prompt += "\n\nThis is output from a scraped HTML page, try your best to tell what the content is about."
        
        user_prompt += f"\n\nContent: {truncated_text}"
        
        logger.info("Sending request to OpenAI API")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        logger.info(f"Generated summary headline: {result['h']}")
        return True, result
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return False, str(e) 

def generate_article(text, is_scraped=False):
    """
    Generate a formatted article from the provided text using OpenAI.
    
    Args:
        text: The text to transform into an article
        is_scraped: Whether the text is from a scraped webpage
        
    Returns:
        tuple: (success, result) where result is either the article dict or error message
    """
    logger.info("Starting article generation")
    
    # Check if the entire message is just a URL (trim whitespace)
    clean_text = text.strip()
    
    # Import is_url here to avoid circular imports
    from functions import is_url
    
    # Check if the text is a URL and we haven't already scraped it
    if not is_scraped and is_url(clean_text):
        logger.info("Detected URL, will scrape content first")
        success, content = scrape_url_content(clean_text)
        
        if success:
            logger.info("Successfully scraped URL content")
            # Call generate_article again with the scraped content and is_scraped=True
            return generate_article(content, is_scraped=True)
        else:
            logger.error(f"Failed to scrape URL: {content}")
            # Fall back to processing the URL itself
            logger.info("Falling back to processing the URL directly")
    
    client = get_openai_client()
    if not client:
        return False, "OpenAI API key not configured"
    
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    logger.info(f"Using OpenAI model: {model}")
    
    try:
        # Ensure the text is within limits for the API
        truncated_text = truncate_for_openai(text)
        
        system_prompt = "You are a personal assistant tasked with writing down given information into a concise article optimised for human readability and well formatted, you can use markdown syntax, emojis and tools needed to format it well. For Lists use bulletpoints."
        user_prompt = f"Return in JSON like: {{\"h\": \"headine, max 2 to 5 words which let the user at first glance understand what this article is about.\",\"s\": \"Article max. 300 words.\" }}"
        
        if is_scraped:
            user_prompt += "\n\nThis is output from a scraped HTML page, transform it into a well-structured article."
        
        user_prompt += f"\n\nContent: {truncated_text}"
        
        logger.info("Sending request to OpenAI API")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        logger.info(f"Generated article headline: {result['h']}")
        return True, result
    except Exception as e:
        logger.error(f"Error generating article: {e}")
        return False, str(e) 
