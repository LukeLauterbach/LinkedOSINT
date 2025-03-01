import argparse
from seleniumbase import SB
from seleniumbase.common.exceptions import ElementNotVisibleException, NoSuchElementException
import json
import re


def main(company="", email_format="{first}.{last}", debug=False):
    if not company:
        company, email_format, debug = parse_arguments()
    if not company:
        company = input("Please enter the company name: ").strip()

    if not debug:  # Only perform the search if debug mode is disabled. Otherwise, just used cached data.
        users = get_results_from_google(company)  # Returns a dict with 'raw' and 'url'. Raw is the name,URL is to LnkIn
        with open(f'{company}-LinkedInUsers.json', 'w') as json_file:
            json.dump(users, json_file, indent=4)

    # Write what we found to disk
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

    args = parser.parse_args()

    return args.company, args.email_format, args.debug


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
