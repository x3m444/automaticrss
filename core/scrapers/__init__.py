from core.scrapers.mypornclub import MyPornClub
from core.scrapers.thepiratebay import ThePirateBay
from core.scrapers.yts import YTS
from core.scrapers.x1337x import X1337x
from core.scrapers.therarbg import TheRARBG

SCRAPERS: dict[str, type] = {
    "thepiratebay": ThePirateBay,
    "yts":          YTS,
    "1337x":        X1337x,
    "therarbg":     TheRARBG,
    "mypornclub":   MyPornClub,
}


def get_scraper(indexer_id: str):
    cls = SCRAPERS.get(indexer_id)
    return cls() if cls else None
