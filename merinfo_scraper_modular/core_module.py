import requests
from bs4 import BeautifulSoup

class RobustMerinfoScraper:
    def scrape(self, first_name, last_name, city):
        url = f"https://www.merinfo.se/search?q={first_name}+{last_name}+{city}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        print(f"Scraping Merinfo.se for {first_name} {last_name} in {city}")
        print(soup.prettify())

