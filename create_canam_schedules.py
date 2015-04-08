from collections import namedtuple, defaultdict
import logging
import re
import datetime

from ics import Calendar, Event
import requests
import requests_cache
from bs4 import BeautifulSoup, NavigableString
import arrow


requests_cache.install_cache('local_cache')

# Current Year
year = 2015

# Url and month as int
urls = [('http://www.canamleague.com/schedule/may.php', 5),
        ('http://www.canamleague.com/schedule/june.php', 6),
        ('http://www.canamleague.com/schedule/july.php', 7),
        ('http://www.canamleague.com/schedule/august.php', 8),
        ('http://www.canamleague.com/schedule/september.php', 9), ]

# Teams to generate a calendar for
ical_teams = ['Rockland', 'Trois-Rivières', 'Québec', 'New Jersey', 'Sussex County', 'Garden State Grays', 'Ottawa']

# Pattern to parse game descriptions
game_re = re.compile('(?P<away>.*?) at (?P<home>.*?) (?P<tod>[0-9:amp]+)')

Game = namedtuple('Game', ['home', 'away', 'time'])


def clean_team(name):
    'Take a "dirty" name and clean it'

    name = name.strip()
    d = {
        'Quebec': 'Québec',
        'Rockland (DH)': 'Rockland',
        'Sussex': 'Sussex County',
    }
    return d[name] if name in d else name


def clean_time(year, month, day, time_string):
    'Take a "dirty" time (and year, month and day as int) and return a US/Eastern Time'

    tss = time_string.split(':')
    hours = int(tss[0])
    minutes = int(''.join(filter(lambda x: x.isdigit(), tss[1])))
    # Assume all games start between 9 am and 9pm
    if 9 >= hours >= 1:
        hours += 12
    return arrow.get(datetime.datetime(year, month, day, hours, minutes, 0), 'US/Eastern')


games = []

for url, month in urls:
    response = requests.get(url)
    soup = BeautifulSoup(response.content)
    table = soup.findAll('table', bordercolor='#2b5da0')[1]
    for row in table.findAll('tr'):
        day_cell, games_cell = row.findAll('td')
        day = int(''.join(filter(lambda x: x.isdigit(), day_cell.text)))
        for game_string in filter(lambda x: type(x) == NavigableString, games_cell.contents):
            try:
                game_match = game_re.match(game_string.strip()).groupdict()
            except AttributeError:
                logging.error('Could not parse game: %s' % game_string.strip())

            game = Game(clean_team(game_match['home']),
                        clean_team(game_match['away']),
                        clean_time(year, month, day, game_match['tod']),
            )
            logging.info('Parsed: %s' % str(game))

            games.append(game)

# Collect games by team
teams = defaultdict(list)

for g in games:
    teams[g.home].append(g)
    teams[g.away].append(g)

# Create calendars
for team in ical_teams:
    c = Calendar()
    for g in teams[team]:
        e = Event()
        e.name = g.away if g.home == team else '@ %s' % g.home
        e.begin = g.time
        e.duration = {'hours': 3}
        c.events.append(e)
        with open('%s.ics' % team, 'w') as ical:
            ical.writelines(c)