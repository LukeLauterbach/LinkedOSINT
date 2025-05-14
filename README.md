<p align="center"><img src="icon.png" width="150" height="150" /></p>

There are many tools for scraping usernames from LinkedIn. However, many of them result in bans from LinkedIn or try to pull information from Google without success. LinkedOSINT is built with Selenium, a browser automation framework, to scrape results from Google.

Because Google only allows between 300-400 results for a search, the script will only be able to find approximately 300-400 users per company.

## Installation
LinkedOSINT is not available on PyPi, but is compatabile with pipx. 

```bash
pipx install git+https://github.com/LukeLauterbach/LinkedOSINT
```
The script can also be downloaded and run normally. The only requirement is seleniumbase.
```bash
git clone https://github.com/LukeLauterbach/LinkedOSINT
pip install -r requirements.txt
```
## Usage
```python
linkedosint -c "Example Company, Inc" -e "{f}{last}@example.com"
```
## Risky Mode
By default, LinkedOSINT scrapes results from LinkedIn. This doesn't cary much risk to it. At worst, Google might throw CAPCHAs your way for a few hours. However, sometimes company names make it hard to find results on Google (e.g. "Smith Inc" is going to return a lot of results for people with the last name Smith). 
LinkedOSINT offers an optional "Risky" mode, which allows you to directly log into LinkedIn with your credentials and scrape the Employees pages of an organization's LinkedIn page. This automated behavior may result in a ban on LinkedIn.
### Risky Mode - Required Arguments
* `-rurl` - The URL of the organization's first Employees page (for example: https://www.linkedin.com/search/results/people/?currentCompany=%5B%2213562%22%5D&origin=COMPANY_PAGE_CANNED_SEARCH&sid=Yvg)
* `-ru` - Username of your LinkedIn account
* `-rp` - Password of your LinkedIn account.

I am not responsible if Risky mode gets you banned from LinkedIn. 
