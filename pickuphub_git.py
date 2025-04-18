import time
import os
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz
import json

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
LOGIN_URL = "https://pickuphub.net/login"
PICKUPHUB_URL = "https://pickuphub.net/hub"
GOOGLE_CALENDAR_CREDENTIALS = "service_account.json"
CALENDAR_ID = os.getenv("USERNAME")

def get_driver():
    chrome_options = Options()

    if os.environ.get("GITHUB_ACTIONS") == "true":
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")

    # Optional: Use local chromedriver only if running locally
    current_directory = os.path.dirname(os.path.realpath(__file__))
    chromedriver_path = os.path.join(current_directory, "chromedriver.exe")
    if os.path.exists(chromedriver_path):
        service = Service(chromedriver_path)
        return webdriver.Chrome(service=service, options=chrome_options)
    
    # Fallback: system path
    return webdriver.Chrome(options=chrome_options)

def login_to_pickuphub(driver):
    print("Logging in to PickupHub...")
    driver.get(LOGIN_URL)
    time.sleep(2)

    try:
        username_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")
    except Exception as e:
        print(f"Error finding login fields: {e}")
        driver.quit()
        exit()

    username_field.send_keys(USERNAME)
    password_field.send_keys(PASSWORD)
    password_field.send_keys(Keys.RETURN)
    time.sleep(5)

    if "login" in driver.current_url:
        print("Login failed. Still on login page.")
        driver.quit()
        exit()

    print("Login successful.")

def convert_datetime(date_string):
    date_string = date_string.replace(" @", "").replace(".", "")
    current_year = datetime.datetime.now().year
    date_string_with_year = f"{current_year} {date_string}"
    date_format = "%Y %b %d %I:%M %p"
    return datetime.datetime.strptime(date_string_with_year, date_format)

def convert_clean_list(unclean_String):
    cleaner = unclean_String.split(',')[-1].split('(80 mins)')
    return [i.strip() for i in cleaner]

def fetch_matches(driver):
    driver.get(PICKUPHUB_URL)
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    page_text = soup.get_text(strip=True)

    match_list_unclean = page_text.split("My Schedule")[1].split("Recommended Games")[0].split("(Indoor)")

    matches = []
    if match_list_unclean[0] != 'No scheduled games right now.':
        for i in match_list_unclean:
            if len(i.strip()) > 0:
                clean_event = convert_clean_list(i)
                matches.append({
                    "title": "Volleyball",
                    "datetime": convert_datetime(clean_event[0]),
                    "location": clean_event[1],
                })

    with open("Output.txt", "w") as text_file:
        text_file.write(str(matches))

    return matches

def check_for_existing_event(service, calendar_id, event_start_time):
    tz = pytz.timezone("America/Toronto")
    event_start_time = tz.localize(event_start_time)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=event_start_time.isoformat(),
        q='Volleyball',
        singleEvents=True,
    ).execute()
    
    for event in events_result.get('items', []):
        if 'Volleyball' in event.get('summary', '') and event_start_time.isoformat()==event['start']['dateTime']:
            print(f"Event already exists: {event['summary']} at {event['start']['dateTime']}")
            return False
    print("Event doesn't exist.")
    return True

def add_event_to_calendar(event):
    print(f"\nChecking event to Google Calendar: {event['title']} on {event['datetime']}")
    
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_CALENDAR_CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=credentials)

    event_body = {
        "summary": event["title"],
        "location": event["location"],
        "start": {"dateTime": event["datetime"].isoformat(), "timeZone": "America/Toronto"},
        "end": {"dateTime": (event["datetime"] + datetime.timedelta(minutes=80)).isoformat(), "timeZone": "America/Toronto"},
    }

    if check_for_existing_event(service, CALENDAR_ID, event["datetime"]):
        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        print(f"Event created: {created_event.get('htmlLink')}")

def main():
    print("-" * 30)
    print("Starting script...")

    
    try:
        with open("service_account.json") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        print("Invalid JSON file:", e)
        exit(1)

    driver = get_driver()
    login_to_pickuphub(driver)
    time.sleep(3)
    matches = fetch_matches(driver)

    if not matches:
        print("No matches found.")
        driver.quit()
        return

    for match in matches:
        add_event_to_calendar(match)

    driver.quit()
    print("All matches processed.")
    print("Browser closed.")
    print("-" * 30)

if __name__ == "__main__":
    main()
