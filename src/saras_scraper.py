import time, logging, os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# =========================================================
# CONFIG
# =========================================================

BASE_URL = "https://saras.cbse.gov.in/SARAS/AffiliatedList/ListOfSchdirReport"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = os.path.join(BASE_DIR, "../data/Cbse_scraper/output")
LOG_DIR = os.path.join(BASE_DIR, "../Logs")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "cbse_scraper.log")

HEADLESS = False

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger("CBSE_SCRAPER")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


# =========================================================
# DRIVER
# =========================================================

def get_driver():
    options = webdriver.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--start-maximized")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


# =========================================================
# HELPERS
# =========================================================

def wait_clickable(driver, by, value, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )

def wait(driver, by, value, t=20):
    return WebDriverWait(driver, t).until(
        EC.presence_of_element_located((by, value))
    )


def debug_page(driver):
    path = os.path.join(LOG_DIR, "debug_page.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    logger.info(f"Saved debug page: {path}")


# =========================================================
# SCRAPER CORE
# =========================================================

def scrape_current_page(driver):

    table_id = get_table_id(driver)

    table = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, table_id)))
    rows = table.find_elements(By.TAG_NAME, "tr")

    data = []

    for r in rows[1:]:
        cols = r.find_elements(By.TAG_NAME, "td")
        if len(cols) < 6:
            continue

        data.append({
            "sno": cols[0].text,
            "aff_no_school_code": cols[1].text,
            "state_district": cols[2].text,
            "school_head_name": cols[3].text,
            "address": cols[4].text,
            "website": cols[5].text
        })

    return data


def scrape_all_pages(driver):

    all_data = []
    page_no = 1

    while True:

        logger.info(f"Page {page_no}")

        all_data.extend(scrape_current_page(driver))

        logger.info(f"Total rows so far: {len(all_data)}")

        try:
            next_btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "myTable_next"))
            )

            classes = next_btn.get_attribute("class")

            if "disabled" in classes:
                logger.info("Last page reached")
                break

            driver.execute_script("arguments[0].click();", next_btn)

            time.sleep(3)
            page_no += 1

        except Exception as e:
            logger.error(f"Pagination error: {e}")
            break

    return all_data

# =========================================================
# REGION FINDER (ROBUST)
# =========================================================

def set_max_entries(driver):

    try:
        logger.info("Setting entries per page to 100")

        dropdown = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "myTable_length"))
        )

        driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)

        Select(dropdown).select_by_visible_text("100")

        time.sleep(3)

    except Exception as e:
        logger.error(f"Failed setting page size: {e}")

def find_region_radio(driver):

    radios = driver.find_elements(By.XPATH, "//input[@type='radio']")

    for r in radios:
        try:
            label = driver.execute_script(
                "return arguments[0].parentElement.innerText;",
                r
            ).lower()

            if "region" in label:
                return r

        except:
            continue

    return None


def find_region_dropdown(driver):

    selects = driver.find_elements(By.TAG_NAME, "select")

    for s in selects:
        try:
            options = [o.text.lower() for o in Select(s).options]

            if any("region" in o for o in options):
                return s

        except:
            continue

    return None

def get_table_id(driver):

    tables = driver.find_elements(By.TAG_NAME, "table")

    for t in tables:
        tid = t.get_attribute("id")
        if tid and "table" in tid.lower():
            return tid

    return "myTable"


def find_search_button(driver):

    # covers ALL possible CBSE variations
    elements = driver.find_elements(
        By.XPATH,
        "//button | //input[@type='button'] | //input[@type='submit']"
    )

    for el in elements:

        try:
            text = (el.text or el.get_attribute("value") or "").strip().lower()

            if "search" in text:
                return el

        except:
            continue

    return None

# =========================================================
# REGION WISE SCRAPER (FINAL CLEAN)
# =========================================================

def handle_region_wise(driver):

    logger.info("Starting REGION WISE scrape")

    time.sleep(3)

    # STEP 1: CLICK RADIO (CORRECT ID)
    region_radio = wait_clickable(
        driver,
        By.ID,
        "SearchMainRadioRegion_wise"
    )

    driver.execute_script("arguments[0].click();", region_radio)

    logger.info("Clicked Region Wise radio")

    # STEP 2: WAIT FOR DROPDOWN TO APPEAR
    WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.ID, "Region"))
    )

    time.sleep(2)

    # STEP 3: SELECT REGION
    region_dropdown = driver.find_element(By.ID, "Region")
    select = Select(region_dropdown)

    print("\nAvailable Regions:\n")
    for opt in select.options:
        print(opt.text)

    region_name = input("\nEnter Region EXACTLY: ").strip()
    select.select_by_visible_text(region_name)

    logger.info(f"Selected region: {region_name}")

    time.sleep(2)

    # STEP 4: CLICK SEARCH
    search_btn = find_search_button(driver)
    if search_btn is None:
        debug_page(driver)
        raise Exception("Search button not found after region selection")

    driver.execute_script("arguments[0].click();", search_btn)

    logger.info("Search clicked successfully")

    time.sleep(5)

    set_max_entries(driver)

    data = scrape_all_pages(driver)
    return data, region_name

# =========================================================
# SAVE
# =========================================================

def save(data, region_name):

    safe_region = region_name.replace(" ", "_")

    output_file = os.path.join(
        OUTPUT_DIR,
        f"cbse_schools_data_{safe_region}.csv"
    )

    df = pd.DataFrame(data)

    df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    logger.info(f"Saved {len(df)} rows")
    logger.info(f"Saved file at: {os.path.abspath(output_file)}")


# =========================================================
# MAIN
# =========================================================

def main():

    print("\n1.State Wise\n2.Region Wise")
    c = input("Choice: ")

    driver = get_driver()

    try:
        driver.get(BASE_URL)
        time.sleep(5)

        if c == "2":
            data,region_name = handle_region_wise(driver)
        else:
            print("Only region wise enabled")
            return

        save(data, region_name)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()