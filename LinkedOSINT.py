import argparse
from seleniumbase import SB, Driver
from seleniumbase.common.exceptions import ElementNotVisibleException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import json
import re
from patchright.sync_api import Playwright, sync_playwright, expect
from patchright._impl._errors import TimeoutError
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from os import getenv
import requests
from time import sleep


def main(company="", email_format="{first}.{last}", debug=False, risky_url="", risky_username="", risky_password="", brave_api_key="", brave_max=100):
    if not company:
        company, email_format, debug, risky_url, risky_username, risky_password, brave_api_key, brave_max = parse_arguments()
    if not company:
        company = input("Please enter the company name: ").strip()
    if not brave_api_key:
        brave_api_key = getenv("BRAVE_API_KEY")

    if not debug:  # Only perform the search if debug mode is disabled. Otherwise, just used cached data.
        users = []

        if risky_url and risky_username and risky_password:
            users.extend(risky_mode(email_format, risky_url, risky_username, risky_password))
        else:
            users.extend(get_results_from_google(company))  # Returns a dict with 'raw' and 'url'. Raw is the name,URL is to LnkIn

        users.extend(get_results_from_duckduckgo(company))
        users.extend(get_results_from_brave(brave_api_key, company, max_calls=brave_max))

        with open(f'{company}-LinkedInUsers.json', 'w') as json_file:
            json.dump(users, json_file, indent=4)

    # Load from disk
    with open(f'{company}-LinkedInUsers.json', 'r') as json_file:
        users = json.load(json_file)

    users = parse_users(users)  # Get rid of weird things in people's names (e.g. John Doe, DDS).
    #  At this point, users is a dict with 'raw' (raw name), 'url' (to LinkedIn), 'fullname' (their name, formatted),
    #   'firstname', and 'lastname'
    users = format_users(users, email_format)  # Turn names into the email addresses. Will add 'email' to the dict.
    users = remove_duplicates(users)

    print_output(users)

    # If used by another script, return all of the users in a list, instead of a dict that contains unneeded data
    email_list = convert_users_to_list(users)
    return email_list


def remove_duplicates(users):
    by_email = {}

    for item in users:
        email_raw = str(item.get("email", "")).strip()
        email_key = email_raw.lower()
        source = str(item.get("source", "")).strip()

        if not email_key:
            continue

        if email_key not in by_email:
            by_email[email_key] = {"email": email_raw, "sources": []}

        if source and source not in by_email[email_key]["sources"]:
            by_email[email_key]["sources"].append(source)

    result = [
        {"email": rec["email"], "source": ",".join(rec["sources"])}
        for rec in by_email.values()
    ]
    return result


def is_valid_linkedin_url(url: str) -> bool:
    """
    Returns True if the URL points to linkedin.com or www.linkedin.com.
    Handles DuckDuckGo/Bing redirect URLs and normal LinkedIn links.
    """
    parsed = urlparse(url)

    # If this is a redirect (like DuckDuckGo ads), pull out "u" or "u3" params
    query_params = parse_qs(parsed.query)
    candidate = url
    for key in ("u", "u3"):
        if key in query_params:
            candidate = unquote(query_params[key][0])
            break

    # Now parse the candidate
    target = urlparse(candidate)
    hostname = target.hostname or ""

    return hostname.lower() in ("linkedin.com", "www.linkedin.com")


def risky_mode(email_format, risky_url, risky_username, risky_password):
    driver = Driver(uc=True, headless=False)
    driver.get(risky_url)

    driver.find_element("id", "username").send_keys(risky_username)
    sleep(2)
    driver.find_element("id", "password").send_keys(risky_password)
    sleep(2)
    driver.find_element("xpath", "//button[@type='submit']").click()
    sleep(5)

    extracted_names = []

    while True:
        # Extract all name elements
        name_elements = driver.find_elements("xpath", "//span[@dir='ltr']/span[@aria-hidden='true']")
        names = [el.text.strip() for el in name_elements if el.text.strip()]
        extracted_names.extend(names)

        print(f"Extracted Names: {names}")

        try:
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'artdeco-pagination__button--next')]"))
            )
            driver.execute_script("arguments[0].scrollIntoView();", next_button)  # Scroll into view
            sleep(1)
            next_button.click()
            sleep(3)
        except Exception:
            break

    extracted_names = format_risky_users(extracted_names)

    return extracted_names

def format_risky_users(users):
    formatted_users = []
    for user in users:
        formatted_users.append({'raw': user, "url": ""})

    return formatted_users


def convert_users_to_list(users):
    email_list = []
    for user in users:
        email_list.append(user['email'].lower())

    return email_list


def print_output(users):
    if not users:
        print("No users found. Something is probably not working correctly."
              )
    print("\nEmail Addresses Found:")
    for user in users:
        print(user['email'])

    print(f"\n{len(users)} users found on LinkedIn.")
    count_google = sum(1 for u in users if "google" in u["source"].lower())
    if count_google > 0:
        print(f"Users from Google: {count_google}")
    count_duckduckgo = sum(1 for u in users if "duckduckgo" in u["source"].lower())
    if count_google > 0:
        print(f"Users from DuckDuckGo: {count_duckduckgo}")
    count_brave = sum(1 for u in users if "brave" in u["source"].lower())
    if count_google > 0:
        print(f"Users from Brave: {count_brave}")


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--company", help="Company name")
    parser.add_argument("-e", "--email_format", default="{first}.{last}",
                        help="Email Format. Defaults to {first}.{last}. Example: {f}{last}@EXAMPLE.COM")
    parser.add_argument("-d", "--debug", action="store_true", help="Debug Mode")
    parser.add_argument(
        "-bk", "--brave-key",
        help="Brave Search API key. If not provided, the script will check the BRAVE_API_KEY environment variable."
    )
    parser.add_argument("-bm", "--brave-max", type=int,
                        help="Maximum Brave Search queries to run (defaults to 100). Warning: more than 2000 searches in a month can result in charges.")

    parser.add_argument_group(title="Risky Arguments", description="When these arguments are provided, the script will directly scrape the company's webpage on LinkedIn. This may result in a ban from LinkedIn.")
    parser.add_argument("-rurl", "--risky-url", help="The URL of the first page of the organization's employees on LinkedIn.")
    parser.add_argument("-ru", "--risky-username", help="Your LinkedIn username")
    parser.add_argument("-rp", "--risky-password", help="Your LinkedIn password")

    args = parser.parse_args()

    return args.company, args.email_format, args.debug, args.risky_url, args.risky_username, args.risky_password, args.brave_key, args.brave_max


def format_users(users, email_format):
    _TOKEN_RE = re.compile(r"\{(f|first|l|last)\}")
    formatted = []
    for user in users:
        first = (user.get("firstname") or "").strip()
        first = re.sub(r"[^a-z0-9]", "", first.lower())
        last  = (user.get("lastname")  or "").strip()
        last = re.sub(r"[^a-z0-9]", "", last.lower())

        replacements = {
            "f": first[:1],
            "first": first,
            "l": last[:1],
            "last": last,
        }

        email = _TOKEN_RE.sub(lambda m: replacements.get(m.group(1), ""), email_format)
        user = {**user, "email": email}
        formatted.append(user)

    return formatted


# People put weird things in their LinkedIn names. This fucntion is intended to remove those weird things.
def parse_users(users):
    # Remove any results that aren't from LinkedIn
    users = [u for u in users if is_valid_linkedin_url(u["url"])]

    for i in range(len(users)):
        users[i]['full_name'] = users[i]['raw'].split("-")[0].strip()  # Get rid of the company name and the title
        users[i]['full_name'] = users[i]['full_name'].split("–")[0].strip()  # Get rid of the company name and the title
        users[i]['full_name'] = users[i]['full_name'].split(",")[0].strip()  # Get rid of certifications
        users[i]['full_name'] = re.sub(r"\(.*?\)", "", users[i]['full_name']).strip()  # Eliminate anything in parenthesis
        users[i]['full_name'] = users[i]['full_name'].replace(".", "")
        users[i]['firstname'] = users[i]['full_name'].split(" ")[0].strip()
        users[i]['lastname'] = users[i]['full_name'].split(" ")[-1].strip()
    return users


def initialize_playwright(playwright, headless=False):
    patchright_cmd = Path(sys.executable).parent / "patchright"

    # Only needed for the first time run, but won't error on later runs
    subprocess.run([patchright_cmd, "install"], stdout=subprocess.DEVNULL)

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.route("**/*.{png,jpg,jpeg,svg,gif}", lambda route: route.abort())

    return browser, context, page


def get_results_from_google(company=""):
    print("Getting results from Google...", end="\r", flush=True)
    users = []
    with sync_playwright() as playwright:
        browser, context, page = initialize_playwright(playwright)
        page.goto(
            f"https://www.google.com/search?q=site:linkedin.com/in+%22{company}%22&udm=14")

        while True:
            sleep(3)
            results = page.locator("div.tF2Cxc")
            count = results.count()

            for i in range(count):
                result = results.nth(i)
                try:
                    title_element = result.locator("h3")
                    link_element = result.locator("a")

                    # Ensure elements exist
                    if title_element.count() > 0 and link_element.count() > 0:
                        title = title_element.first.inner_text()
                        url = link_element.first.get_attribute("href")
                        users.append({'raw': title, 'url': url, 'source': 'google'})
                    else:
                        url = link_element.first.get_attribute("href") if link_element.count() > 0 else 'N/A'
                        print(f"Couldn't Parse Name: {url}")
                except Exception as e:
                    print(f"Error parsing result {i}: {e}")

            try:
                with page.expect_navigation():
                    page.get_by_text("Next").click()
            except TimeoutError:
                break

        context.close()
        browser.close()

        print(f"Getting results from Google...{len(users)} found.")

    return users


def parse_brave_quota(headers):
    """
    Extracts Brave Search API quota info, ignoring the short-window values.
    Converts reset time from seconds to days.
    """
    def pick_second(header_name):
        raw = headers.get(header_name)
        if not raw:
            return None
        parts = [p.strip() for p in raw.split(",")]
        return parts[1] if len(parts) > 1 else parts[0]

    try:
        limit = int(pick_second("X-RateLimit-Limit"))
        remaining = int(pick_second("X-RateLimit-Remaining"))
        reset_secs = int(pick_second("X-RateLimit-Reset"))
        reset_days = round(reset_secs / 86400, 2)  # 86400 secs in a day
    except (ValueError, TypeError):
        return None

    print(f"  - {remaining} Brave queries remaining. Resets in {reset_days} days.")

    return {
        "limit": limit,
        "remaining": remaining,
        "reset_in_days": reset_days
    }


def get_results_from_brave(brave_api_key, company, max_calls=100):
    """
    Fetches Brave Search results in pages (default 10 per call) and keeps paging
    until the API returns no results or max_calls is reached.

    Args:
        brave_api_key (str): Brave Search API key.
        company (str): Company name to search for.
        per_page (int): Results per API call (Brave supports up to ~20).
        max_calls (int|None): Optional cap on the number of API calls. None = no cap.

    Returns:
        list[dict]: List of {'raw': title, 'url': url, 'source': 'brave'}
    """
    if not brave_api_key:
        return []

    print("Getting results from Brave...", end="\r", flush=True)

    users = []
    calls_made = 0
    resp = None

    while True:
        if max_calls is not None and calls_made >= max_calls:
            break

        try:
            resp = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": brave_api_key,
                },
                params={
                    "q": f'site:linkedin.com/in "{company}"',
                    "safesearch": "off",
                    "spellcheck": "false",
                    "offset": calls_made,    # advance the window
                },
                timeout=20,
            )
            # If you prefer to handle 429s yourself, you can skip this and check status codes
            resp.raise_for_status()

            data = resp.json()
            results = data.get("web", {}).get("results", [])

            if not results:
                # No more results
                break

            users.extend(
                {"raw": item.get("title", ""), "url": item.get("url", ""), "source": "brave"}
                for item in results
            )

            calls_made += 1

            # live-update the same line with total found so far
            print(f"\rGetting results from Brave... {len(users)} found.", end="", flush=True)

        except requests.exceptions.HTTPError as e:
            # Handle rate-limit (429) or other server issues gracefully
            status = getattr(e.response, "status_code", None)
            if status == 429:
                # Optional: use header to sleep; fall back to 1s
                reset_hdr = (e.response.headers or {}).get("X-RateLimit-Reset", "1")
                # Headers may be "short,long" – take the long window (second) if present
                reset_secs = reset_hdr.split(",")[-1].strip()
                try:
                    sleep_for = max(1, int(reset_secs))
                except ValueError:
                    sleep_for = 1
                sleep(min(sleep_for, 5))  # don't stall too long; brief backoff
                continue
            else:
                print(f"\nBrave API HTTP error: {e}")
                break
        except requests.exceptions.RequestException as e:
            print(f"\nBrave API request failed: {e}")
            break

    # finalize status line
    print(f"\rGetting results from Brave... {len(users)} found.")
    if resp:
        parse_brave_quota(resp.headers)

    return users


def get_results_from_duckduckgo(company: str = ""):
    """
    Scrape DuckDuckGo SPA results for LinkedIn profiles matching a company name.
    Keeps paginating until the "More results" button disappears.
    """
    print("Getting results from DuckDuckGo...", end="\r", flush=True)
    users = []

    query = f'site:linkedin.com/in "{company}"'
    url = f"https://duckduckgo.com/?q={quote_plus(query)}"

    with sync_playwright() as playwright:
        browser, context, page = initialize_playwright(playwright)
        page.set_default_timeout(15000)

        page.goto(url)
        page.wait_for_selector("a[data-testid='result-title-a']")

        while True:
            # Collect results
            results = page.locator("a[data-testid='result-title-a']")
            count = results.count()

            for i in range(count):
                try:
                    link = results.nth(i)
                    title = link.inner_text()
                    href = link.get_attribute("href")
                    if href:
                        users.append({"raw": title, "url": href, "source": "duckduckgo"})
                except Exception as e:
                    print(f"Error parsing result {i}: {e}")

            # Look for "More results" button
            btn = page.locator("button#more-results")
            if btn.count() == 0 or not btn.first.is_visible():
                break

            try:
                with page.expect_response(lambda r: "duckduckgo.com" in r.url and r.status == 200):
                    btn.first.click()
                # Wait for new batch to load
                page.wait_for_selector("a[data-testid='result-title-a']")
                sleep(0.5)
            except TimeoutError:
                break

        context.close()
        browser.close()

        print(f"Getting results from DuckDuckGo...{len(users)} found.")

    return users


if __name__ == '__main__':
    main()
