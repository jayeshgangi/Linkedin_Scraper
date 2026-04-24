import time, os, logging, random
import pandas as pd
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def setup_logger():
    logger = logging.getLogger("linkedin_about_scraper")
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    log_dir = os.path.join(BASE_DIR,"Logs")
    os.makedirs(log_dir,exist_ok=True)

    log_file_path = os.path.join(log_dir, "linkedin_about_scraper.log")

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()

load_dotenv()

options = Options()
options.add_argument(r"--user-data-dir=C:\Users\addys\AppData\Local\Google\Chrome\User Data\Profile 16")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--start-maximized")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV  = os.path.join(BASE_DIR,"data","Linkedin_about_scraper","input", "Linkedin_id_output.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "data","Linkedin_about_scraper","output","Linkedin_about_output.csv")

class LinkedInScraper:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.driver = webdriver.Chrome(options=options)
        input("Browser opened -> press Enter to continue...")
        self.data = pd.read_csv(csv_path)
        logging.info(f"Loaded {len(self.data)} LinkedIn URLs from {csv_path}")

    def _save_debug_html(self, filename, profile_id):
        safe_name = profile_id.replace("/", "_")
        file_path = f"debug_{safe_name}_{filename}"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.driver.page_source)

        logger.info(f"[{profile_id}] Debug HTML saved → {file_path}")

    def _expand_about(self):
        """Try to click 'see more' in the About section."""
        try:
            see_more = self.driver.find_element(
                By.XPATH,
                "//section[.//span[contains(text(),'About')]]//button"
            )
            self.driver.execute_script("arguments[0].click();", see_more)
            time.sleep(5)
            logging.info("Expanded About section")
        except:
            pass

    def _clean_text(self, text):
        
        if not text:
            logging.warning("Received empty text for About section")
            return text
        
        try:
            text = text.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

        replacements = {
            '\u2018': "'", '\u2019': "'", 
            '\u201c': '"', '\u201d': '"', 
            '\u2013': '-', '\u2014': '-',  
            '\u2026': '...',               
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)

        remove_phrases = [
            "... more",
            ".. more",
            "See more"
        ]
        for phrase in remove_phrases:
            text = text.replace(phrase,"")

        return text.strip()

    def _extract_about_text(self):
        """
        Selectors derived from the actual blocked_page.html structure.
        """
        xpaths = [
            # Strategy 1 — exact match from your real HTML
            "//span[@data-testid='expandable-text-box']",
        
            # Strategy 2 — the <p> inside the About section's content div
            "//section[.//h2[text()='About']]//p/span",
        
            # Strategy 3 — entire About section as fallback
            "//section[.//h2[text()='About']]",
        ]
    
        for i, xpath in enumerate(xpaths, 1):
            try:
                el = self.driver.find_element(By.XPATH, xpath)
                text = el.text.strip()
                if text and len(text) > 10:
                    logging.info(f"About found via strategy {i}")
                    return self._clean_text(text)
            except:
                continue
    
        logging.warning("About not found")
        self._save_debug_html("no_about_debug.html")
        return "NOT FOUND"
    
    
    def get_about_section(self, url,profile_id,retry=True):

        logging.info(f"\n Opening: {url}")
        logger.warning(f"[{profile_id}] Redirect detected")
        self.driver.get(url)

        try:
            WebDriverWait(self.driver, 12).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )
        except:
            logging.warning("Main tag not found")

        time.sleep(5)

        current_url = self.driver.current_url
        logger.info(f"[{profile_id}] Current URL: {current_url}")

        # ── Redirect / hard block check (URL-based, not HTML content) ──────────
        if "linkedin.com/in/" not in current_url:
            if any(s in current_url for s in ["authwall", "checkpoint", "login"]):
                if retry:
                    logging.info("Auth block — going to feed, waiting 20s...")
                    self.driver.get("https://www.linkedin.com/feed/")
                    time.sleep(40)
                    return self.get_about_section(url, retry=False)
                return "BLOCKED"
            self._save_debug_html("redirect_page.html",profile_id)
            return "REDIRECTED"

        # ── Page is good — proceed normally ─────────────────────────────────────
        self._expand_about()

        logger.debug(f"[{profile_id}] Scrolling page")
        for i in range(5):
            self.driver.execute_script(f"window.scrollTo(0, {i * 500});")
            time.sleep(random.uniform(2.5, 3.5))

        return self._extract_about_text()

    def run(self):
        self.driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)

        if "login" in self.driver.current_url:
            input("Please log in manually, then press Enter...")
        else:
            logging.info("Already logged in")

        logging.info("Stabilising session...")
        time.sleep(10)

        results = []

        for idx, row in self.data.iterrows():
            url = row["LinkedIn"]
            profile_id = url.rstrip("/")[-1]

            logger.info(f"[{idx+1}/{len(self.data)}] START profile: {profile_id}")

            try:
                about = self.get_about_section(url,profile_id)
                logger.info(f"[{profile_id}] SUCCESS")
            except Exception as e:
                logger.exception(f"[{profile_id}] ERROR: {e}")
                about = "ERROR"

            results.append({"LinkedIn": url, "About": about})

            # Save incrementally — so you don't lose progress on a crash
            df_row = pd.DataFrame([{"LinkedIn": url, "About": about}])
            write_header = not os.path.exists(OUTPUT_CSV)
            df_row.to_csv(OUTPUT_CSV, mode='a', index=False, header=write_header,encoding = 'utf-8-sig')

            # Random human-like delay between profiles
            delay = random.uniform(15, 35)
            logging.info(f"Waiting {delay:.1f}s before next profile...")
            time.sleep(delay)

        logging.info(f"Done. Results in {OUTPUT_CSV}")
        self.driver.quit()


if __name__ == "__main__":
    scraper = LinkedInScraper(INPUT_CSV)
    scraper.run()