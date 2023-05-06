# Property-Scraper
- Property web scraper that polls rightmove to track house prices and new listings
- Tracks all new houses for a given criteria and updates an SQLLite3 database
- Currently set up to track property in London Zone 2 & 1
- Sends an email detailing price decreases and new property listings.
- scraper_main.py scrapes the Rightmove public API endpoint for all available listings, adding new entries to a database
- email_main.py sends an email detailing new properties added over the last 24 hours, as well as any price change history of these houses.
- Recommended to run scraper_main.py intra-day and email_main once daily, though this could be easily configured to run multiple times