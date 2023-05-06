from app import rightmove_scraper, manage_database, DATABASE_TABLE


if __name__ == '__main__':
    # Scrape rightmove
    data = rightmove_scraper.run()
    try:
        manage_database.create_db()
    except:
        pass
    try:
        manage_database.create_table(DATABASE_TABLE)
    except:
        pass
    manage_database.update_house(DATABASE_TABLE, data)
