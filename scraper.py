import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from hcad_variables import hcad_cookies, hcad_headers, hcad_params
from webdriver_manager.chrome import ChromeDriverManager

import json
import datetime

if "logs" not in st.session_state:
    st.session_state["logs"] = []

with open("list_types.json", "r") as f:
    list_types = json.load(f)

list_type_options = [f"{key} - {value}" for key, value in list_types]

def wait_for_loading_to_finish(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: d.find_element(By.ID, "ctl00_UpdateProgressMaster").get_attribute("aria-hidden") == "true"
    )

def scrape_hctx(start_date, end_date, doc_type):
    url = "https://www.cclerk.hctx.net/Applications/WebSearch/RP_R.aspx?ID=PtRyJzbPPV9CWT5QJ8WvKEFVAr+pwQL/1XGVmC/aHdfP+DIXvYNpdnX9R8yeQC2XXgkUgoYdO2y3PRZ2zTfJGhb/6xRICV2VPFSofHebrWv7hxYW2UwdAi1h77pFQpJntC2qr8qMihkZHUM/4mzhH1C9e7qmkcSdI3sSSVXPAtA="
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager(driver_version="120.0.6099.224").install())
    # service = Service(ChromeDriverManager(driver_version="134.0.6998.89").install())
    driver = webdriver.Chrome(options=options, service=service)
    driver.get(url)
    
    # Wait for the date input fields to be present
    wait = WebDriverWait(driver, 10)
    
    # Fill in the start date
    start_date_input = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtDateN")))
    start_date_input.send_keys(start_date)
    
    # Fill in the end date
    end_date_input = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDateTo")
    end_date_input.send_keys(end_date)
    
    # Fill in the document type
    doc_type_input = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtType")
    doc_type_input.send_keys(doc_type)
    
    # Click the search button
    button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btnSearch")))
    button.click()
    time.sleep(5)
    all_data = []  # To store all rows from all pages
    page = 1
    while True:
        try:
            print("Waiting for results to load...")
            log_message("Waiting for results to load...", "⏳")
            wait_for_loading_to_finish(driver)
            # Wait for the table to appear
            response = driver.page_source
            soup = BeautifulSoup(response, 'lxml')
            table = soup.find('table', {'id': 'itemPlaceholderContainer'})
            df = pd.read_html(str(table))[0]  # Extract table using BeautifulSoup
            length = len(list(df["Legal Description"].dropna()))
            
            all_data += list(df["Legal Description"].dropna())
            log_message(f"Scraping page {page}, got {length} with a total of {len(all_data)}")
            page += 1
        except Exception:
            print("No records found. Stopping.")
            break
        
        # Try clicking the next button using JavaScript
        try:
            next_button = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_BtnNext")
            if next_button.is_enabled():
                print("Clicking Next button...")
                next_button.click()
                time.sleep(5)
                wait_for_loading_to_finish(driver)
            else:
                print("Next button is disabled. Stopping.")
                break
        except Exception as e:
            print("Error clicking Next button:", e)
            break
    
    # finally:
    #     print(driver.page_source)
    #     driver.quit()
    
    return all_data

def get_date_range(option):
    today = datetime.date.today()
    if option == "Last Week":
        start_date = today - datetime.timedelta(days=7)
    elif option == "Last Month":
        start_date = today - datetime.timedelta(days=30)
    elif option == "Last 3 Months":
        start_date = today.replace(day=1) - datetime.timedelta(days=90)

    return start_date.strftime('%m/%d/%Y'), today.strftime('%m/%d/%Y')

# Function to convert string for legal description
def convert_string(input_string):
    # Extract the components using regex
    desc_match = re.search(r"Desc:\s*(\S.*?)(?=\sSec:)", input_string)
    sec_match = re.search(r"Sec:\s*(\d+)", input_string)
    lot_match = re.search(r"Lot:\s*(\d+)", input_string)
    block_match = re.search(r"Block:\s*(\d+)", input_string)
    
    # If all components are found, format them as required
    if desc_match and sec_match and lot_match and block_match:
        description = desc_match.group(1).strip().upper()
        sec = "SEC " + sec_match.group(1)
        lot = "LT " + lot_match.group(1)
        block = "BLK " + block_match.group(1)
        
        # Create the final string
        result = f"{lot} {block} {description} {sec}"
        return result
    else:
        return "Invalid input format"

# Function to initialize the headless WebDriver
def get_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    service = Service(ChromeDriverManager(driver_version="120.0.6099.224").install())
    # service = Service(ChromeDriverManager(driver_version="134.0.6998.89").install())
    driver = webdriver.Chrome(options=options, service=service)
    return driver

# Function to get the page source using Selenium
def get_page_source(driver, url):
    driver.get(url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    page_source = driver.page_source
    return page_source

# Function to extract Owner Name
def get_owner_name(html):
    soup = BeautifulSoup(html, 'html.parser')
    td_elements = soup.find_all('tr')
    for td in td_elements:
        if "Owner Name" in td.text:
            result = td
    return result

# Function to log messages with icons in a single text area
def log_message(msg, icon="📝"):
    st.session_state["logs"].append(f"{icon} {msg}")
    st.session_state["logs"] = st.session_state["logs"][-10:]
    log_text = "\n".join(st.session_state["logs"])
    log_area.text_area("Logs", log_text, height=260)

# Function to extract Property Address
def get_property_address(html):
    soup = BeautifulSoup(html, 'html.parser')
    td_elements = soup.find_all('tr')
    for td in td_elements:
        if "Property Address:" in td.text:
            result = td
    return result

# Streamlit App
st.title("Real-Time Property Scraping")

selected_list_type = st.selectbox("Choose a document type", list_type_options)
selected_period = st.radio("Select period", ["Last Week", "Last Month", "Last 3 Months"])

# Create a placeholder for logs
log_area = st.empty()

# Create a placeholder for the dataframe
df_placeholder = st.empty()

# Create a progress bar
progress_bar = st.progress(0)

legal_desc = []

# Function to start scraping when the button is clicked
def start_scraping(doc_key, start_date, end_date):
    log_message("Search initiated, waiting for results...", "⏳")
    legal_desc = scrape_hctx(start_date, end_date, doc_key)
    # Initialize an empty list for results
    results = []

    # Initialize the WebDriver (headless mode)
    driver = get_driver()

    black_list = {}
    # Loop over the records in the dataframe
    total_records = len(legal_desc)
    for i, row in enumerate(legal_desc):
        # Update progress bar
        progress_bar.progress((i + 1) / total_records, text = f"Processing {i + 1} out of {total_records}")


        # Get the legal description from the row
        legal_description = row  # Modify this based on actual column name

        # Convert the string to the required format
        converted_desc = convert_string(legal_description)

        # Pass the converted description to the params
        hcad_params['desc'] =  converted_desc  # Modify this with your actual params
        
        if converted_desc in black_list.keys():
            continue
        else:
            response = requests.get(
                'https://public.hcad.org/records/Real/AdvancedResults.asp',
                params=hcad_params,
                cookies=hcad_cookies,
                headers=hcad_headers,
            )
            soup = BeautifulSoup(response.content, 'html.parser')
            # Get the page source
            try:
                page_source = get_page_source(driver, "https://public.hcad.org" + soup.find('a')["href"])
            except:
                continue
            
            # Get owner name and property address
            owner_name = "\n".join([line.strip().replace("\xa0", " ") for line in get_owner_name(page_source).find("th").text.strip().splitlines() if line.strip()]) if get_owner_name(page_source) else "N/A"
            property_address = get_property_address(page_source).find("th").text.strip() if get_property_address(page_source) else "N/A"
            black_list[converted_desc] = {
                "owner_name": owner_name,
                "property_address": property_address
            }
        # Append the result to the list
        results.append({
            'Legal Description': converted_desc,
            'Owner Name & mailing address': owner_name,
            'Property Address': property_address
        })

        # Update the dataframe display in real-time
        df_placeholder.dataframe(pd.DataFrame(results))

        # Add a time delay of 1 second to avoid rate limiting
        time.sleep(1)

    # Final DataFrame display after the loop finishes
    final_df = pd.DataFrame(results)
    df_placeholder.dataframe(final_df)

    # Close the WebDriver after the scraping is done
    driver.quit()

# Streamlit button to start the scraping process
if st.button('Start Scraping'):
    doc_key = selected_list_type.split(" - ")[0]
    start_date, end_date = get_date_range(selected_period)
    start_scraping(doc_key, start_date, end_date)
