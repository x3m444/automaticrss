from nicegui import ui
from ui.layout import navbar
from core.db import Session, Watchlist, Feed, Setting


def _get_base_dir() -> str:
    with Session() as s:
        row = s.query(Setting).filter_by(key="transmission_download_dir").first()
        return row.value if row and row.value else ""


def _load_entries():
    with Session() as s:
        rows = s.query(Watchlist).order_by(Watchlist.created_at.desc()).all()
        return [
            {
                "id":             e.id,
                "name":           e.name,
                "terms":          e.terms or [],
                "exclusions":     e.exclusions or [],
                "download_subdir": e.download_subdir or "",
                "feed_ids":       e.feed_ids or [],
                "is_active":      e.is_active,
            }
            for e in rows
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
                )

    render()

    def _add_single(val: str):
        val = val.strip()
        if val and val not in chips:
            chips.append(val)
            render()

    with ui.row().classes("items-center gap-1"):
        # on_value_change=lambda e: None forțează NiceGUI să sincronizeze
        # valoarea pe server la fiecare keystroke/paste
        inp = ui.input(
            placeholder="scrieți sau lipiți, apoi Enter",
            on_value_change=lambda e: None,
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

        def refresh():
            entries = _load_entries()
            count_badge.set_text(str(len(entries)))
            list_container.clear()

            if not entries:
                with list_container:
                    ui.label("Nicio intrare în watchlist.").classes("text-gray-400 text-sm")
                return

            with list_container:
                for e in entries:
                    with ui.card().classes("w-full"):
                        with ui.row().classes("w-full items-start justify-between gap-4"):
                            # left: info
                            with ui.column().classes("gap-1 flex-1"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(e["name"]).classes("font-bold text-base")
                                    ui.badge(
                                        "activ" if e["is_active"] else "oprit",
                                        color="green" if e["is_active"] else "grey",
                                    )

                                # termeni
                                with ui.row().classes("flex-wrap gap-1 items-center"):
                                    ui.label("Caută:").classes("text-xs text-gray-400")
                                    for t in e["terms"]:
                                        ui.chip(t, color="primary").props("dense")

                                # excluderi
                                if e["exclusions"]:
                                    with ui.row().classes("flex-wrap gap-1 items-center"):
                                        ui.label("Exclude:").classes("text-xs text-gray-400")
                                        for ex in e["exclusions"]:
                                            ui.chip(ex, color="red").props("dense")

                                # destinatie
                                base = _get_base_dir()
                                subdir = e["download_subdir"]
                                if subdir:
                                    full = f"{base.rstrip('/')}/{subdir}" if base else subdir
                                    ui.label(f"→ {full}").classes("text-xs text-gray-500 font-mono")
                                else:
                                    ui.label(f"→ {base or 'director default Transmission'}").classes(
                                        "text-xs text-gray-500 font-mono"
                                    )

                            # right: actions
                            with ui.column().classes("gap-1 items-end"):
                                def toggle(eid=e["id"], cur=e["is_active"]):
                                    with Session() as s:
                                        row = s.query(Watchlist).filter_by(id=eid).first()
                                        if row:
                                            row.is_active = not cur
                                            s.commit()
                                    refresh()

                                def delete(eid=e["id"]):
                                    with Session() as s:
                                        row = s.query(Watchlist).filter_by(id=eid).first()
                                        if row:
                                            s.delete(row)
                                            s.commit()
                                    ui.notify("Șters", type="warning")
                                    refresh()

                                ui.button(
                                    icon="pause" if e["is_active"] else "play_arrow",
                                    on_click=toggle,
                                ).props("flat dense round")
                                ui.button(icon="delete", on_click=delete).props(
                                    "flat dense round color=red"
                                )

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
