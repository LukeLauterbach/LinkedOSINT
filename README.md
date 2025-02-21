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
