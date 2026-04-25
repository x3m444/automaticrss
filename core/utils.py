import re

_STOP_RE = re.compile(
    r'\b(?:'
    r'2160p|1080[pi]|720[pi]|480[pi]|4[Kk]|'
    r'blu\.?ray|bluray|bdrip|brrip|web\.?dl|webrip|'
    r'hdtv|dvdrip|dvdscr|dvd|'
    r'remux|proper|repack|retail|extended|theatrical|unrated|'
    r'x\.?264|x\.?265|h\.?264|h\.?265|hevc|avc|xvid|divx|'
    r'dts|aac|ac3|mp3|flac|truehd|atmos|ddp?|eac3|'
    r'hdr10?|dolby|uhd|'
    r'xxx|multi|dual\.?audio|subbed|dubbed|'
    r'\d{3,4}mb|\d+\.?\d*gb'
    r')\b',
    re.IGNORECASE,
)

_URL_RE  = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)
_EP_RE   = re.compile(r'\bS\d{1,2}(?:E\d{1,2})+\b', re.IGNORECASE)
_YEAR_RE = re.compile(r'\b(19\d{2}|20[012]\d)\b')


def get_cleanup_tokens() -> list[str]:
    """Load user-defined display junk tokens from DB."""
    try:
        import json
        from core.db import Session, Setting
        with Session() as s:
            row = s.query(Setting).filter_by(key="title_cleanup_tokens").first()
            if row and row.value:
                return json.loads(row.value)
    except Exception:
        pass
    return []


def clean_title(raw: str, extra_stop: list[str] | None = None) -> str:
    """Return a human-readable display title from a raw torrent name."""
    if not raw:
        return raw

    s = raw.strip()

    # Remove square bracket content first (site watermarks, release tags)
    # Must be before URL removal so www.site.com inside [] doesn't consume the rest
    s = re.sub(r'\[[^\]]{0,80}\]', ' ', s)

    # Remove URLs
    s = _URL_RE.sub(' ', s)

    # Normalize . and _ to spaces (keep -)
    s = re.sub(r'[._]', ' ', s)

    # Strip user-defined junk tokens
    if extra_stop:
        for tok in extra_stop:
            tok = tok.strip()
            if tok:
                s = re.sub(r'\b' + re.escape(tok) + r'\b', ' ', s, flags=re.IGNORECASE)

    # Remove trailing release group "-WORD" at end
    s = re.sub(r'\s*-\s*\w+\s*$', '', s)

    # Strip leading junk (e.g. "-Title" after bracket removal)
    s = re.sub(r'^[\s\-]+', '', s).strip()

    # Find technical stop point
    stop_m = _STOP_RE.search(s)
    if stop_m:
        s = s[:stop_m.start()].strip()

    # Season/episode — keep up to and including it
    ep_m = _EP_RE.search(s)
    if ep_m:
        return s[:ep_m.end()].strip()

    # Year — format as "(YYYY)"
    year_m = _YEAR_RE.search(s)
    if year_m:
        title_part = s[:year_m.start()].strip()
        if title_part:
            return f"{title_part} ({year_m.group(1)})"

    return s.strip() or raw
