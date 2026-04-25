# AutomaticRSS

A self-hosted torrent automation tool — a lightweight alternative to Flexget, built around a NiceGUI web interface and Transmission.

## Features

- **RSS Feeds** — monitor any RSS/Atom feed and auto-download matching torrents based on keyword filters
- **Watchlist** — schedule recurring searches across multiple sources; new matches are downloaded automatically
- **Search** — search across multiple torrent sources simultaneously and send results directly to Transmission
- **Downloads** — browse active torrents (with progress, speed, ETA) and completed files on disk; delete files and remove from Transmission in one click
- **Disk Cleanup** — automatically remove the oldest seeded torrents when free space drops below a configurable threshold
- **Multi-instance** — run on multiple machines sharing a single Supabase database; each instance has its own Transmission connection and settings

## Built-in scrapers

| Source | Type |
|---|---|
| The Pirate Bay | General |
| 1337x | General |
| YTS | Movies |
| TheRARBG | General |
| MyPornClub | Adult |

FlareSolverr support included for Cloudflare-protected sources.

## Stack

- **UI** — [NiceGUI](https://nicegui.io) (FastAPI + WebSockets)
- **Database** — PostgreSQL via [Supabase](https://supabase.com) (free tier)
- **Scheduler** — APScheduler
- **Torrent client** — Transmission (via `transmission-rpc`)
- **ORM / migrations** — SQLAlchemy + Alembic

## Installation

### Linux

```bash
git clone https://github.com/x3m444/automaticrss.git
cd automaticrss
chmod +x install.sh
./install.sh
```

### Windows

```powershell
git clone https://github.com/x3m444/automaticrss.git
cd automaticrss
.\install.ps1
```

Both scripts set up a virtual environment, configure the database connection, generate a unique instance ID, optionally configure Transmission, run Alembic migrations, and register the app as a system service.

### Docker

```bash
cp .env.example .env   # fill in DB credentials
docker compose up -d
```

## Requirements

- Python 3.10+
- Transmission (daemon or desktop) accessible via RPC
- A free [Supabase](https://supabase.com) project for the database

## Updating (Linux service install)

```bash
~/automaticrss/update.sh
```

## Screenshots

_Coming soon_
