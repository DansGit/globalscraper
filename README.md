globalscraper
=============

Scrapes sites using openeventdata/scraper's massive list of RSS feeds.


I'm interested in how news varies across the so called 'global north' and 'global south' or across the 'developed'
and 'developing' worlds. I'm planning to investigate this by scraping a very large list of rss feeds, orignally
gathered by the Open Event Data project. I've added a parameter to their dataset describing whether the feed relays
news about the global north or south. I've also deleted feeds that carry international, world, and Americas news 
because they tend to cross the north/south divide.

#ToDo
- [ ] Add more 'global north' news sources, such as the New York Times' domestic feed.
- [ ] Write a script for downloading the articles, removing boilerplate, and storing them in a database.
