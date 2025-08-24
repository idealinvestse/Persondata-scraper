# MerinfoScraper

A Python-based web scraper for extracting information from Merinfo.se, a Swedish people search website.

## Features

* Scrapes data from Merinfo.se based on search queries (first name, last name, city)
* Prints search results in a formatted manner
* Modular design with separate modules for core functionality, caching, logging, and utilities

## Requirements

* Python3.x
* requests library
* beautifulsoup4 library

## Usage

1. Clone the repository:git clone https://github.com/your-username/MerinfoScraper.git`
2. Navigate to the project directory:cd MerinfoScraper`
3. Run the client script: client.py --first_name John --last_name Doe --city Stockholm`

## Command-Line Arguments

* `--first_name`: First name of the person to search for
* `--last_name`: Last name of the person to search for
* `--city`: City where the person is located

## Modules

*merinfo_scraper_modular`: Modular package containing the core functionality
*client.py`: Simple command-line client for interacting with the scraper
*merinfo_scraper.py`: Script that performs a search and prints the results

## Notes

* This project is for educational purposes only. Please respect Merinfo.se's terms of service and robots.txt directives.
* The scraper may break if Merinfo.se changes its website structure or implements anti-scraping measures.

