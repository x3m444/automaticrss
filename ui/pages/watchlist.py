from nicegui import ui, run
from ui.layout import navbar
from core.db import Session, Watchlist, WatchlistLog, Feed, Setting


def _get_base_dir() -> str:
    with Session() as s:
        row = s.query(Setting).filter_by(key="transmission_download_dir").first()
        return row.value if row and row.value else ""


_INTERVAL_OPTIONS = {
    10:   "10 min",
    15:   "15 min",
    30:   "30 min",
    60:   "1 oră",
    120:  "2 ore",
    240:  "4 ore",
    360:  "6 ore",
    720:  "12 ore",
    1440: "24 ore",
}


def _load_entries():
    with Session() as s:
        rows = s.query(Watchlist).order_by(Watchlist.created_at.desc()).all()
        return [
            {
                "id":                     e.id,
                "name":                   e.name,
                "terms":                  e.terms or [],
                "exclusions":             e.exclusions or [],
                "download_subdir":        e.download_subdir or "",
                "feed_ids":               e.feed_ids or [],
                "is_active":              e.is_active,
                "check_interval_minutes": e.check_interval_minutes or 120,
                "last_run_at":            e.last_run_at,
                "log_level":              e.log_level or "full",
            }
            for e in rows
        ]


def _load_logs(watchlist_id: int, limit: int = 10) -> list[dict]:
    with Session() as s:
        rows = (
            s.query(WatchlistLog)
            .filter_by(watchlist_id=watchlist_id)
            .order_by(WatchlistLog.ran_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "ran_at":        r.ran_at,
                "items_checked": r.items_checked,
                "items_sent":    r.items_sent,
                "items_blocked": r.items_blocked,
                "entries":       r.entries or [],
            }
            for r in rows
        ]


def _load_feeds():
    with Session() as s:
        rows = s.query(Feed).filter_by(is_active=True).order_by(Feed.name).all()
        return {str(f.id): f.name for f in rows}


def _chip_input(label: str, chips: list[str], color: str = "primary"):
    """Chip input: Enter sau paste → chip întreg (fără auto-split pe spații)."""
    ui.label(label).classes("text-sm font-medium")
    row = ui.row().classes("flex-wrap gap-2 min-h-8 items-center")

    def render():
        row.clear()
        with row:
            for chip in chips:
                ui.chip(
                    chip, removable=True, color=color,
                    on_value_change=lambda e, c=chip: (
                        chips.remove(c) if c in chips else None,
                        render(),
                    ),
                ).props("dense")

    render()

    def _add_single(val: str):
        val = val.strip()
        if val and val not in chips:
            chips.append(val)
            render()

    with ui.row().classes("items-center gap-1"):
        inp = ui.input(
            placeholder="scrieți sau lipiți, apoi Enter",
        ).classes("w-72")

        def _add(_=None):
            _add_single(inp.value)
            inp.set_value("")

        inp.on("keydown.enter", _add)
        # paste: valoarea e sincronizată via on_value_change,
        # timerul de 0.1s e suficient pentru un round-trip WebSocket
        inp.on("paste", lambda e: ui.timer(0.1, _add, once=True))
        ui.button(icon="add", on_click=_add).props("flat dense round")

    return render


@ui.page("/watchlist")
def watchlist_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-8"):

        with ui.row().classes("items-center gap-3"):
            ui.label("Watchlist").classes("text-xl font-bold")
            count_badge = ui.badge("0").props("color=primary rounded")

        list_container = ui.column().classes("w-full gap-3")

        base_dir = _get_base_dir()

        def refresh():
            entries = _load_entries()
            count_badge.set_text(str(len(entries)))
            list_container.clear()

            if not entries:
                with list_container:
                    ui.label("Nicio intrare în watchlist.").classes("text-gray-400 text-sm")
                return

            def do_edit(entry: dict):
                feeds_map = _load_feeds()
                cur_terms = list(entry["terms"])
                cur_excl  = list(entry["exclusions"])

                with ui.dialog() as dlg, ui.card().classes("w-full max-w-3xl gap-3"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label("Editează watchlist").classes("text-lg font-bold")
                        ui.button(icon="close", on_click=dlg.close).props("flat dense round")

                    name_inp = ui.input("Nume", value=entry["name"]).classes("w-full")
                    ui.separator()

                    _chip_input("Termeni de căutare (OR)", cur_terms, "primary")
                    ui.separator()

                    _chip_input("Excluderi", cur_excl, "red")
                    ui.separator()

                    with ui.column().classes("w-full gap-1"):
                        ui.label("Director destinație").classes("text-sm font-medium")
                        if base_dir:
                            ui.label(f"Root: {base_dir}").classes("text-xs text-gray-400 font-mono")
                        subdir_inp = ui.input(
                            placeholder="ex: movies/action",
                            value=entry["download_subdir"],
                        ).classes("w-full")

                    ui.separator()

                    with ui.column().classes("w-full gap-1"):
                        ui.label("Aplică pe (gol = toate feed-urile)").classes("text-sm font-medium")
                        feed_checks: dict[int, ui.checkbox] = {}
                        if feeds_map:
                            with ui.row().classes("flex-wrap gap-3"):
                                for fid, fname in feeds_map.items():
                                    cb = ui.checkbox(fname, value=(int(fid) in entry["feed_ids"]))
                                    feed_checks[int(fid)] = cb
                        else:
                            ui.label("Niciun feed activ.").classes("text-xs text-gray-400")

                    active_sw = ui.switch("Activ", value=entry["is_active"])
                    interval_sel = ui.select(
                        _INTERVAL_OPTIONS,
                        label="Interval verificare",
                        value=entry["check_interval_minutes"]
                              if entry["check_interval_minutes"] in _INTERVAL_OPTIONS else 120,
                    ).classes("w-full")
                    log_level_sel = ui.select(
                        {"full":    "Complet (trimise + blocate + excluse)",
                         "sent":    "Doar trimise",
                         "summary": "Sumar (doar cifre)",
                         "verbose": "Verbose — tot (inclusiv fără potrivire)"},
                        label="Nivel log",
                        value=entry["log_level"],
                    ).classes("w-full")
                    ui.label("⚠ Verbose generează sute de înregistrări per rulare — folosiți temporar.") \
                        .classes("text-xs text-orange-400") \
                        .bind_visibility_from(log_level_sel, "value", lambda v: v == "verbose")
                    ui.separator()

                    def save():
                        fids = [fid for fid, cb in feed_checks.items() if cb.value]
                        with Session() as s:
                            row = s.query(Watchlist).filter_by(id=entry["id"]).first()
                            if row:
                                row.name                   = name_inp.value.strip() or entry["name"]
                                row.terms                  = list(cur_terms)
                                row.exclusions             = list(cur_excl)
                                row.download_subdir        = subdir_inp.value.strip() or None
                                row.feed_ids               = fids if fids else []
                                row.is_active              = active_sw.value
                                row.check_interval_minutes = interval_sel.value
                                row.log_level              = log_level_sel.value
                                s.commit()
                        dlg.close()
                        ui.notify("✓ Watchlist actualizat", type="positive")
                        refresh()

                    with ui.row().classes("justify-end gap-2"):
                        ui.button("Anulează", on_click=dlg.close).props("flat")
                        ui.button("Salvează", on_click=save).props("color=primary")

                dlg.open()

            with list_container:
                for e in entries:
                    with ui.card().classes("w-full"):
                        # ── rând principal ─────────────────────────────────
                        with ui.row().classes("w-full items-start justify-between gap-4"):
                            # stânga: info
                            with ui.column().classes("gap-1 flex-1"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(e["name"]).classes("font-bold text-base")
                                    ui.badge(
                                        "activ" if e["is_active"] else "oprit",
                                        color="green" if e["is_active"] else "grey",
                                    )

                                with ui.row().classes("flex-wrap gap-1 items-center"):
                                    ui.label("Caută:").classes("text-xs text-gray-400")
                                    for t in e["terms"]:
                                        ui.chip(t, color="primary").props("dense")

                                if e["exclusions"]:
                                    with ui.row().classes("flex-wrap gap-1 items-center"):
                                        ui.label("Exclude:").classes("text-xs text-gray-400")
                                        for ex in e["exclusions"]:
                                            ui.chip(ex, color="red").props("dense")

                                subdir = e["download_subdir"]
                                dest = f"{base_dir.rstrip('/')}/{subdir}" if subdir and base_dir else \
                                       subdir or base_dir or "director default Transmission"
                                ui.label(f"→ {dest}").classes("text-xs text-gray-500 font-mono")

                                interval_lbl = _INTERVAL_OPTIONS.get(
                                    e["check_interval_minutes"],
                                    f"{e['check_interval_minutes']} min"
                                )
                                last = e["last_run_at"]
                                last_str = last.strftime("%d.%m %H:%M") if last else "niciodată"
                                ui.label(f"⏱ {interval_lbl}  ·  ultima rulare: {last_str}").classes(
                                    "text-xs text-gray-400"
                                )

                            # dreapta: butoane
                            with ui.column().classes("gap-1 items-end shrink-0"):
                                with ui.row().classes("gap-0"):
                                    def toggle(eid=e["id"], cur=e["is_active"]):
                                        with Session() as s:
                                            row = s.query(Watchlist).filter_by(id=eid).first()
                                            if row:
                                                row.is_active = not cur
                                                s.commit()
                                        refresh()

                                    ui.button(
                                        icon="pause" if e["is_active"] else "play_arrow",
                                        on_click=toggle,
                                    ).props("flat dense round")
                                    ui.button(
                                        icon="edit",
                                        on_click=lambda entry=e: do_edit(entry),
                                    ).props("flat dense round color=orange")

                                with ui.row().classes("gap-0"):
                                    run_btn_ref: dict = {}
                                    log_panel_ref: dict = {}

                                    async def run_now(entry=e, _ref=run_btn_ref, _lref=log_panel_ref):
                                        from core.rules_engine import run_watchlist_entry_now
                                        _ref["btn"].props(add="loading")
                                        result = await run.io_bound(
                                            run_watchlist_entry_now, entry["id"]
                                        )
                                        _ref["btn"].props(remove="loading")
                                        t = "positive" if result.startswith("✓") else "info"
                                        ui.notify(result, type=t, timeout=5000)
                                        # refresh log panel inline
                                        if "panel" in _lref:
                                            _render_log_panel(_lref["panel"], entry["id"])

                                    btn = ui.button(
                                        icon="bolt", on_click=run_now,
                                    ).props("flat dense round color=green")
                                    run_btn_ref["btn"] = btn

                                    def delete(eid=e["id"]):
                                        with Session() as s:
                                            row = s.query(Watchlist).filter_by(id=eid).first()
                                            if row:
                                                s.delete(row)
                                                s.commit()
                                        ui.notify("Șters", type="warning")
                                        refresh()

                                    ui.button(icon="delete", on_click=delete).props(
                                        "flat dense round color=red"
                                    )

                        # ── panou expandabil: istoric rulări ───────────────
                        def _render_log_panel(container, wid=e["id"]):
                            container.clear()
                            logs = _load_logs(wid)
                            with container:
                                if not logs:
                                    ui.label("Nicio rulare înregistrată încă.").classes(
                                        "text-xs text-gray-400 italic py-1"
                                    )
                                    return
                                for lg in logs:
                                    ts = lg["ran_at"].strftime("%d.%m %H:%M") if lg["ran_at"] else "?"
                                    sent_n    = lg["items_sent"]
                                    blocked_n = lg["items_blocked"]
                                    checked_n = lg["items_checked"]

                                    color = "green" if sent_n > 0 else "grey"
                                    summary = (
                                        f"{ts}  —  "
                                        f"verificate: {checked_n}  ·  "
                                        f"trimise: {sent_n}  ·  "
                                        f"respinse: {blocked_n}"
                                    )

                                    if lg["entries"]:
                                        with ui.expansion(summary).classes(
                                            "w-full text-xs"
                                        ).props(f"dense header-class='text-{color}-400'"):
                                            icon_map = {
                                                "sent":     ("check_circle", "green"),
                                                "blocked":  ("block",        "orange"),
                                                "excluded": ("remove_circle","red"),
                                                "error":    ("error",        "red"),
                                                "nomatch":  ("remove",       "grey"),
                                            }
                                            display = lg["entries"][:200]
                                            overflow = len(lg["entries"]) - len(display)
                                            for entry_item in display:
                                                action = entry_item.get("action", "")
                                                reason = entry_item.get("reason", "")
                                                title  = entry_item.get("title", "")
                                                icon, icolor = icon_map.get(action, ("info", "grey"))
                                                with ui.row().classes("items-start gap-2 py-0.5"):
                                                    ui.icon(icon, color=icolor).classes("text-sm mt-0.5 shrink-0")
                                                    with ui.column().classes("gap-0"):
                                                        ui.label(title).classes("text-xs leading-tight")
                                                        if reason:
                                                            ui.label(reason).classes("text-xs text-gray-400")
                                            if overflow:
                                                ui.label(f"... și încă {overflow} înregistrări (afișate primele 200)") \
                                                    .classes("text-xs text-gray-500 italic py-1")
                                    else:
                                        ui.label(summary).classes(f"text-xs text-{color}-400 py-0.5")

                        with ui.expansion("Istoric rulări", icon="history").classes(
                            "w-full text-sm"
                        ).props("dense"):
                            log_panel = ui.column().classes("w-full gap-0 pl-2")
                            log_panel_ref["panel"] = log_panel

                            def _on_expand(lp=log_panel, wid=e["id"]):
                                _render_log_panel(lp, wid)

                            # încarcă la prima expandare
                            ui.timer(0, lambda lp=log_panel, wid=e["id"]: _render_log_panel(lp, wid), once=True)

        refresh()
        ui.separator()

        # ── Formular adăugare ──────────────────────────────────────────────
        ui.label("Adaugă intrare watchlist").classes("text-xl font-bold")

        with ui.card().classes("w-full gap-4"):
            name_input = ui.input("Nume watchlist", placeholder="ex: Action Movies").classes("w-full")

            ui.separator()

            terms: list[str] = []
            render_terms = _chip_input("Termeni de căutare (OR — orice potrivire declanșează descărcarea)", terms, "primary")

            ui.separator()

            exclusions: list[str] = []
            render_excl = _chip_input("Excluderi (niciun rezultat cu acești termeni)", exclusions, "red")

            ui.separator()

            # destinatie
            base_dir = _get_base_dir()
            with ui.column().classes("w-full gap-1"):
                ui.label("Director destinație").classes("text-sm font-medium")
                if base_dir:
                    ui.label(f"Root Transmission: {base_dir}").classes("text-xs text-gray-400 font-mono")
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{base_dir.rstrip('/') + '/' if base_dir else ''}").classes(
                        "text-gray-500 font-mono text-sm"
                    )
                    subdir_input = ui.input(
                        placeholder="ex: movies/action",
                    ).classes("flex-1")

            ui.separator()

            # filtru feed-uri (optional)
            feeds_map = _load_feeds()
            selected_feed_ids: list[int] = []

            with ui.column().classes("w-full gap-1"):
                ui.label("Aplică pe (gol = toate feed-urile)").classes("text-sm font-medium")
                if feeds_map:
                    with ui.row().classes("flex-wrap gap-3"):
                        feed_checkboxes: dict[int, ui.checkbox] = {}
                        for fid, fname in feeds_map.items():
                            cb = ui.checkbox(fname)
                            feed_checkboxes[int(fid)] = cb
                else:
                    ui.label("Niciun feed activ.").classes("text-xs text-gray-400")
                    feed_checkboxes = {}

            interval_add = ui.select(
                _INTERVAL_OPTIONS, label="Interval verificare", value=120,
            ).classes("w-48")

            ui.separator()

            def save():
                if not name_input.value.strip():
                    ui.notify("Completează numele", type="warning")
                    return
                if not terms:
                    ui.notify("Adaugă cel puțin un termen de căutare", type="warning")
                    return

                fids = [fid for fid, cb in feed_checkboxes.items() if cb.value]

                with Session() as s:
                    s.add(Watchlist(
                        name=name_input.value.strip(),
                        terms=list(terms),
                        exclusions=list(exclusions),
                        download_subdir=subdir_input.value.strip() or None,
                        feed_ids=fids if fids else [],
                        is_active=True,
                        check_interval_minutes=interval_add.value,
                    ))
                    s.commit()

                name_input.set_value("")
                subdir_input.set_value("")
                terms.clear()
                exclusions.clear()
                render_terms()
                render_excl()
                for cb in feed_checkboxes.values():
                    cb.set_value(False)

                refresh()
                ui.notify("✓ Watchlist adăugat", type="positive", timeout=3000)
                ui.run_javascript("window.scrollTo({top: 0, behavior: 'smooth'})")

            ui.button("Salvează", on_click=save).props("color=primary")
