from rich.console import Console
from rich.panel import Panel
import argparse
from merinfo_scraper import RobustMerinfoScraper, print_search_result

console = Console()

def main():
    console.print(Panel("MerinfoScraper", title="Welcome"))
    parser = argparse.ArgumentParser(description='MerinfoScraper Client')
    parser.add_argument('--first_name', type=str, help='First name')
    parser.add_argument('--last_name', type=str, help='Last name')
    parser.add_argument('--city', type=str, help='City')
    args = parser.parse_args()

    if not args.first_name or not args.last_name or not args.city:
        console.print("[bold red]Please provide all required arguments: --first_name, --last_name, --city[/bold red]")
        return

    scraper = RobustMerinfoScraper()
    with console.status("[bold green]Scraping Merinfo.se...[/bold green]"):
        result = scraper.search_person(
            förnamn=args.first_name,
            efternamn=args.last_name,
            ort=args.city,
        )
    print_search_result(result)

if __name__ == '__main__':
    main()
