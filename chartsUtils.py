from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time


def take_tradingview_screenshot(url, save_path):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1280,720")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(url)
        chart_element = driver.find_element("css selector", ".chart-container")  # Adjust the selector as needed
        chart_element.screenshot(save_path)
        print(f"Screenshot saved to {save_path}")
        time.sleep(5)
    finally:
        driver.close()
        driver.quit()
