import os
import requests
import json
import time
import logging
from colorlog import ColoredFormatter
from dotenv import load_dotenv

# Laad .env-bestand
load_dotenv()

# Cloudflare API information
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
ZONE_ID = os.getenv("ZONE_ID")
DNS_RECORD_ID = os.getenv("DNS_RECORD_ID")
DNS_RECORD_NAME = os.getenv("DNS_RECORD_NAME")

# Pushover API information
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

# File to store the last known IP address
IP_FILE = os.getenv("IP_FILE", "/var/tmp/last_ip.txt")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 600))

# Nieuwe configuratie met kleurondersteuning
formatter = ColoredFormatter(
    "%(log_color)s[%(asctime)s] %(message)s",  # Voeg kleur toe aan berichten
    datefmt="%d/%m/%y - %H:%M:%S",  # Houd je bestaande datumformaat
    log_colors={
        "DEBUG": "white",
        "INFO": "cyan",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)

# Instellen van de handler en formatter
handler = logging.StreamHandler()
handler.setFormatter(formatter)

# Logger instellen
logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)  # Stel je gewenste logniveau in


# Function to send Pushover notification
def send_pushover_notification(title, message, priority=0):
    url = "https://api.pushover.net/1/messages.json"
    payload = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "title": title,
        "message": message,
        "priority": priority
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            logger.info("Pushover notification sent successfully.")
        else:
            logger.warning(f"Failed to send Pushover notification: {response.text}")
    except Exception as e:
        logger.error(f"Error sending Pushover notification: {e}")


# Function to get the current public IP address
def get_public_ip():
    try:
        response = requests.get("https://api.ipify.org?format=json")
        return response.json()['ip']
    except Exception as e:
        logger.error(f"Error fetching IP: {e}")
        send_pushover_notification("Error", f"Error fetching IP: {e}", priority=1)
        return None


# Function to update the DNS record on Cloudflare
def update_cloudflare_dns(ip):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{DNS_RECORD_ID}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "type": "A",
        "name": DNS_RECORD_NAME,
        "content": ip,
        "ttl": 120,  # Time to Live (in seconds)
        "proxied": False  # Set to True if you want to use Cloudflare's proxy
    }
    
    try:
        response = requests.put(url, headers=headers, json=data)
        result = response.json()
        if result['success']:
            logger.info(f"DNS record updated successfully to {ip}")
            send_pushover_notification("DNS Update", f"DNS updated to {ip}", priority=0)
        else:
            logger.warning(f"Failed to update DNS: {result}")
            send_pushover_notification("DNS Update Failed", f"Failed to update DNS: {result}", priority=1)
    except Exception as e:
        logger.error(f"Error updating DNS: {e}")
        send_pushover_notification("Error", f"Error updating DNS: {e}", priority=1)


# Function to load the last known IP address from file
def load_last_ip():
    try:
        with open(IP_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


# Function to save the current IP address to file
def save_last_ip(ip):
    with open(IP_FILE, "w") as f:
        f.write(ip)


# Main function to monitor IP changes
def monitor_ip_changes():
    send_pushover_notification("Starting script", "Script is running...")
    while True:
        current_ip = get_public_ip()
        if current_ip:
            last_ip = load_last_ip()
            
            if current_ip != last_ip:
                logger.info(f"IP changed from {last_ip} to {current_ip}. Updating DNS...")
                update_cloudflare_dns(current_ip)
                save_last_ip(current_ip)
            else:
                logger.info("IP has not changed.")
        else:
            logger.warning("Unable to fetch current IP.")
        
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    monitor_ip_changes()
