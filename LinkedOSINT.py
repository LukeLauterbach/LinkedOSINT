import argparse
from seleniumbase import SB, Driver
from seleniumbase.common.exceptions import ElementNotVisibleException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import json
import re
from time import sleep


def main(company="", email_format="{first}.{last}", debug=False, risky_url="", risky_username="", risky_password=""):
    if not company:
        company, email_format, debug, risky_url, risky_username, risky_password = parse_arguments()
    if not company:
        company = input("Please enter the company name: ").strip()

    if not debug:  # Only perform the search if debug mode is disabled. Otherwise, just used cached data.
        if risky_url and risky_username and risky_password:
            users = risky_mode(email_format, risky_url, risky_username, risky_password)
        else:
            users = get_results_from_google(company)  # Returns a dict with 'raw' and 'url'. Raw is the name,URL is to LnkIn

        with open(f'{company}-LinkedInUsers.json', 'w') as json_file:
            json.dump(users, json_file, indent=4)

    # Load from disk
    with open(f'{company}-LinkedInUsers.json', 'r') as json_file:
        users = json.load(json_file)

    users = parse_users(users)  # Get rid of weird things in people's names (e.g. John Doe, DDS).
    #  At this point, users is a dict with 'raw' (raw name), 'url' (to LinkedIn), 'fullname' (their name, formatted),
    #   'firstname', and 'lastname'
    users = format_users(users, email_format)  # Turn names into the email addresses. Will add 'email' to the dict.

    print_output(users)

    # If used by another script, return all of the users in a list, instead of a dict that contains unneeded data
    email_list = convert_users_to_list(users)
    return email_list


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
    print("\nEmail Addresses Found:")
    for user in users:
        print(user['email'])

    print(f"\n{len(users)} users found on LinkedIn.")


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--company", help="Company name")
    parser.add_argument("-e", "--email_format", default="{first}.{last}",
                        help="Email Format. Defaults to {first}.{last}. Example: {f}{last}@EXAMPLE.COM")
    parser.add_argument("-d", "--debug", action="store_true", help="Debug Mode")

    parser.add_argument_group(title="Risky Arguments", description="When these arguments are provided, the script will directly scrape the company's webpage on LinkedIn. This may result in a ban from LinkedIn.")
    parser.add_argument("-rurl", "--risky-url", help="The URL of the first page of the organization's employees on LinkedIn.")
    parser.add_argument("-ru", "--risky-username", help="Your LinkedIn username")
    parser.add_argument("-rp", "--risky-password", help="Your LinkedIn password")

    args = parser.parse_args()

    return args.company, args.email_format, args.debug, args.risky_url, args.risky_username, args.risky_password


def format_users(users, email_format):
    for i in range(len(users)):
        users[i]['email'] = email_format
        users[i]['email'] = users[i]['email'].replace("{f}", users[i]['firstname'][0])
        users[i]['email'] = users[i]['email'].replace("{first}", users[i]['firstname'])
        users[i]['email'] = users[i]['email'].replace("{l}", users[i]['lastname'][0])
        users[i]['email'] = users[i]['email'].replace("{last}", users[i]['lastname'])
    return users


# People put weird things in their LinkedIn names. This fucntion is intended to remove those weird things.
def parse_users(users):
    for i in range(len(users)):
        users[i]['full_name'] = users[i]['raw'].split("-")[0].strip()  # Get rid of the company name and the title
        users[i]['full_name'] = users[i]['full_name'].split("–")[0].strip()  # Get rid of the company name and the title
        users[i]['full_name'] = users[i]['full_name'].split(",")[0].strip()  # Get rid of certifications
        users[i]['full_name'] = re.sub(r"\(.*?\)", "", users[i]['full_name']).strip()  # Eliminate anything in parenthesis
        users[i]['full_name'] = users[i]['full_name'].replace(".", "")
        users[i]['firstname'] = users[i]['full_name'].split(" ")[0].strip()
        users[i]['lastname'] = users[i]['full_name'].split(" ")[-1].strip()
    return users


def get_results_from_google(company=""):
    print("Getting results from Google...\n")
    users = []
    with SB(uc=True, locale_code="en") as sb:
        page = 0
        while True:
            search_url = f"https://www.google.com/search?q=site:linkedin.com/in+%22{company}%22&num=100&start={page * 100}"
            sb.open(search_url)
            sb.sleep(1)
            if sb.is_element_visible("g-raised-button.Hg3NO"):
                sb.click("g-raised-button.Hg3NO")
                sb.sleep(1)
            if sb.is_element_visible("a.ZWOrEc"):
                sb.click("a.ZWOrEc")
            try:
                sb.wait_for_element("div#search")
            except ElementNotVisibleException:
                break
            except NoSuchElementException:
                print(f"Could not load the Google results. This could be a CAPCHA issue.")
                return users

            results = sb.find_elements("div.tF2Cxc")  # Google's search result container

            for result in results:
                title_element = result.find_element("css selector", "h3")
                link_element = result.find_element("css selector", "a")
                title = title_element.text
                url = link_element.get_attribute("href")
                if title_element:
                    users.append({'raw': title, 'url': url})
                else:
                    print(f"Couldn't Parse Name: {url}")

            sb.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            page += 1

    return users


if __name__ == '__main__':
    main()
