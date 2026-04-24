import pandas as pd
import re,os,logging,time,requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SERPER_API_KEY")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

os.makedirs(os.path.join(BASE_DIR, "Logs"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR,"data","Linkedin_id_scraper","output"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR,"data","Linkedin_id_scraper","input"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR,"data","Linkedin_about_scraper","input"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR,"data","Linkedin_about_scraper","output"), exist_ok=True)
log_file = os.path.join(BASE_DIR,"logs","linkedin_profile_scraper.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logging.info("Starting scraper....")

if API_KEY:
    logging.info(f"Using API Key: {API_KEY[:4]}****{API_KEY[-4:]}")  # Log partial API key for verification
else:
    logging.error("API Key not found. Please set SERPER_API_KEY in your .env file.")
    exit(1)


def search_google(query):
    url = "https://google.serper.dev/search"

    payload = {
        "q": query,
        "num": 5
    }

    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()


def score_result(title, snippet, school):
    score = 0
    text = (title + " " + snippet).lower()

    if "principal" in text:
        score += 3
    if "head" in text:
        score += 2
    if "director" in text:
        score += 2

    if school.lower() in text:
        score += 3

    if "linkedin.com/in/" in text:
        score += 5

    return score


# ---------- EXTRACT NAME ----------

def extract_name(title):

    title = re.sub(r"\|.*", "", title)

    parts = re.split(r"[-–|]", title)

    name = parts[0].strip()

    name = re.sub(r"(principal|director|head).*", "", name, flags=re.I)

    return name.strip()

# ---------- FIND BEST MATCH ----------

def find_best_linkedin(results, school):
    best = None
    best_score = 0

    if "organic" not in results:
        return None, None, None

    for res in results["organic"]:
        link = res.get("link", "")
        title = res.get("title", "")
        snippet = res.get("snippet", "")

        score = score_result(title, snippet, school)

        if "linkedin.com/in/" in link:
            score += 5

        logging.info(f"Checking: {title} | Score: {score}")

        if score > best_score:
            best_score = score
            best = (link, title, snippet)

    if best:
        link, title, snippet = best
        name = extract_name(title)

        # Detect role
        text = (title + snippet).lower()
        if "principal" in text:
            role = "Principal"
        elif "head" in text:
            role = "Head"
        elif "director" in text:
            role = "Director"
        else:
            role = "Unknown"

        return link, name, role

    return None, None, None


def find_person(school):
    queries = [
        f'{school} principal linkedin',
        f'{school} head of school linkedin',
        f'{school} director linkedin'
    ]

    best_name = None

    for query in queries:
        logging.info(f"Searching: {query}")

        results = search_google(query)

        for r in results.get("organic", []):
            logging.info(f"Result: {r.get('title', '')} | {r.get('link', '')}")

        link, name, role = find_best_linkedin(results, school)

        if name and not best_name:
            best_name = name

        if link:
            return link, name, role

        time.sleep(2)

    if best_name:
        logging.info(f"Fallback search for name: {best_name}")

        results = search_google(f"{best_name} linkedin")
        link, _, _ = find_best_linkedin(results, school)

        return link, best_name, "Unknown"

    return None, best_name, None

def main():
    input_file = os.path.join(BASE_DIR,"data","Linkedin_id_scraper", "input", "school.csv")
    df = pd.read_csv(input_file)

    output = []

    for _, row in df.iterrows():
        school = row["School Name"]

        logging.info(f"\nProcessing: {school}")

        try:
            link, name, role = find_person(school)

            output.append({
                "School": school,
                "Name": name,
                "Role": role,
                "LinkedIn": link})

            logging.info(f"Found: {name} | {role} | {link}")

        except Exception as e:
            logging.error(f"Error for {school}: {e}")

            output.append({
                "School": school,
                "Name": None,
                "Role": None,
                "LinkedIn": None
            })

    output_file = os.path.join(BASE_DIR,"data","Linkedin_id_scraper", "output", "Linkedin_id_output.csv")
    about_input_file = os.path.join(BASE_DIR,"data","Linkedin_about_scraper", "input", "Linkedin_id_output.csv")
    new_df = pd.DataFrame(output)

    if os.path.exists(output_file):
        existing_df = pd.read_csv(output_file)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=["School"], keep="last")
        combined_df.to_csv(output_file, index=False)
        combined_df.to_csv(about_input_file, index=False)
        logging.info("Appended to existing Linkedin_id_output.csv")
    else:
        new_df.to_csv(output_file, index=False)
        new_df.to_csv(about_input_file, index=False)
        logging.info("Created new Linkedin_id_output.csv")

if __name__ == "__main__":
    main()