# careem_all_banner_hrefs.py
import time
import re
import json
import csv
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

#URL = "https://www.careem.com/"
URL = "https://www.careem.com/en-AE/groceries/"

# -------- CONFIG ----------
HEADLESS = False      # set True to run headless; False while debugging
MAX_WAIT = 20
SCROLL_STEP = 800
SCROLL_PAUSE = 0.4
# --------------------------

options = Options()
if HEADLESS:
    # newer headless flag
    options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1400")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, MAX_WAIT)

def extract_urls_from_text(txt):
    """Return list of URLs found inside JS/text (handles absolute/protocol-relative and relative)."""
    if not txt:
        return []
    urls = []
    # absolute or protocol-relative in quotes: 'https://...' or "//..."
    urls += re.findall(r"""['"]((?:https?:)?//[^'"]+)['"]""", txt)
    # absolute http(s) without quotes
    urls += re.findall(r"(https?://[^\s'\";,)]+)", txt)
    # relative paths in quotes like '/some/path'
    urls += re.findall(r"""['"](/[^'"]+)['"]""", txt)
    return urls

try:
    driver.get(URL)

    # wait until at least one candidate banner exists
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='category-item']")))

    # scroll slowly to trigger lazy loading
    last_height = driver.execute_script("return document.body.scrollHeight")
    steps = 0
    while True:
        driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
        time.sleep(SCROLL_PAUSE)
        new_height = driver.execute_script("return document.body.scrollHeight")
        steps += 1
        if new_height == last_height or steps > 50:
            break
        last_height = new_height

    # small wait for any final lazy loads
    time.sleep(1.0)

    # find candidate banner elements
    banner_elements = driver.find_elements(By.CSS_SELECTOR, "div[class*='category-item']")
    print(f"Found {len(banner_elements)} candidate banner elements.")

    results = []
    for idx, el in enumerate(banner_elements, start=1):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.25)

            found = []
            seen = set()

            # 1) collect from <a> tags and their common lazy attributes
            a_nodes = el.find_elements(By.TAG_NAME, "a")
            for a in a_nodes:
                for attr in ("href", "data-href", "data-url", "ng-href"):
                    val = a.get_attribute(attr)
                    if val:
                        # skip anchors that are only javascript
                        if val.strip().lower().startswith("javascript:") or val.strip() in ("#", ""):
                            continue
                        full = urljoin(URL, val)
                        if full not in seen:
                            seen.add(full)
                            found.append(full)
                # onclick might contain URL
                onclick = a.get_attribute("onclick")
                if onclick:
                    for u in extract_urls_from_text(onclick):
                        full = urljoin(URL, u)
                        if full not in seen:
                            seen.add(full); found.append(full)

            # 2) scan all descendant nodes for href-like attributes (some links are on non-<a> elements)
            descendants = el.find_elements(By.CSS_SELECTOR, "*")
            for node in descendants:
                for attr in ("href", "data-href", "data-url", "ng-href", "data-src", "src", "data-srcset", "srcset"):
                    val = node.get_attribute(attr)
                    if not val:
                        continue
                    # handle srcset: pick last/ largest candidate
                    if attr in ("srcset", "data-srcset"):
                        parts = [p.strip().split(" ")[0] for p in val.split(",") if p.strip()]
                        if parts:
                            val = parts[-1]
                    # skip JS pseudo-hrefs
                    if val.strip().lower().startswith("javascript:") or val.strip() in ("#", ""):
                        continue
                    full = urljoin(URL, val)
                    if full not in seen:
                        seen.add(full); found.append(full)

                # also check onclick on any node
                onclick = node.get_attribute("onclick")
                if onclick:
                    for u in extract_urls_from_text(onclick):
                        full = urljoin(URL, u)
                        if full not in seen:
                            seen.add(full); found.append(full)

            # 3) check computed style background-image on container and descendants
            url_pattern = re.compile(r'url\(["\']?(.*?)["\']?\)')
            # container
            bg = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).getPropertyValue('background-image')",
                el
            )
            if bg and bg != "none":
                m = url_pattern.search(bg)
                if m:
                    u = m.group(1)
                    full = urljoin(URL, u)
                    if full not in seen:
                        seen.add(full); found.append(full)
            # descendants backgrounds
            for node in descendants:
                bg = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).getPropertyValue('background-image')",
                    node
                )
                if bg and bg != "none":
                    m = url_pattern.search(bg)
                    if m:
                        u = m.group(1)
                        full = urljoin(URL, u)
                        if full not in seen:
                            seen.add(full); found.append(full)

            # 4) check pseudo elements ::before/::after on container (some sites use them for banners)
            for pseudo in ("::before", "::after"):
                try:
                    bg = driver.execute_script(
                        "return window.getComputedStyle(arguments[0], arguments[1]).getPropertyValue('background-image')",
                        el, pseudo
                    )
                except Exception:
                    bg = None
                if bg and bg != "none":
                    m = url_pattern.search(bg)
                    if m:
                        u = m.group(1)
                        full = urljoin(URL, u)
                        if full not in seen:
                            seen.add(full); found.append(full)

            # placement name / visible text
            placement = el.text.strip() or None

            results.append({
                "index": idx,
                "placement_name": placement,
                "hrefs": found
            })

        except Exception as e:
            print(f"Error processing banner {idx}: {e}")
            continue

    # print results
    for r in results:
        print("\n" + "="*60)
        print(f"Banner #{r['index']}")
        print("Placement:", r['placement_name'])
        print("Found hrefs:")
        for h in r['hrefs']:
            print(" -", h)

    # save to JSON and CSV
    with open("careem_banner_links.json", "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)
    with open("careem_banner_links.csv", "w", newline="", encoding="utf-8") as cf:
        writer = csv.writer(cf)
        writer.writerow(["index", "placement_name", "hrefs_joined"])
        for r in results:
            writer.writerow([r["index"], r["placement_name"], " || ".join(r["hrefs"])])

    print("\nSaved careem_banner_links.json and careem_banner_links.csv")

finally:
    driver.quit()
