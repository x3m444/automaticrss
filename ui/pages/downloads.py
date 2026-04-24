from nicegui import ui, run
from ui.layout import navbar
from core.db import Session, Setting


def _get_setting(key, default=""):
    with Session() as s:
        row = s.query(Setting).filter_by(key=key).first()
        return row.value if row else default


def _connect_transmission():
    from transmission_rpc import Client
    return Client(
        host=_get_setting("transmission_host", "localhost"),
        port=int(_get_setting("transmission_port", "9091")),
        username=_get_setting("transmission_user", ""),
        password=_get_setting("transmission_pass", ""),
    )


def _status_color(status: str) -> str:
    return {
        "downloading": "blue",
        "seeding":     "green",
        "stopped":     "grey",
        "checking":    "orange",
        "queued":      "purple",
    }.get(status.lower(), "grey")


def _fmt_size(n: int) -> str:
    if not n:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_speed(n: int) -> str:
    if not n:
        return ""
    return f"{n/1024:.0f} KB/s" if n < 1024*1024 else f"{n/1024/1024:.1f} MB/s"


@ui.page("/downloads")
def downloads_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-4 max-w-6xl"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Downloads").classes("text-2xl font-bold")
            status_label = ui.label("").classes("text-xs text-gray-400")

        err_label = ui.label("").classes("text-sm text-red-400 hidden")
        table_container = ui.element("div").classes("w-full")

        def _fetch_data():
            client = _connect_transmission()
            return client.get_torrents(), client.get_session()

        async def refresh():
            try:
                torrents, session = await run.io_bound(_fetch_data)

                total_down = sum(t.rateDownload for t in torrents if t.rateDownload)
                total_up   = sum(t.rateUpload   for t in torrents if t.rateUpload)

                status_label.set_text(
                    f"{len(torrents)} torrente · "
                    f"↓ {_fmt_speed(total_down)}  ↑ {_fmt_speed(total_up)}"
                )
                err_label.classes(add="hidden")

                rows = []
                for t in sorted(torrents, key=lambda x: x.addedDate or 0, reverse=True):
                    pct = round(t.percentDone * 100, 1) if t.percentDone else 0
                    rows.append({
                        "id":       t.id,
                        "name":     t.name or "?",
                        "status":   t.status or "unknown",
                        "pct":      pct,
                        "size":     _fmt_size(t.totalSize),
                        "down":     _fmt_speed(t.rateDownload or 0),
                        "up":       _fmt_speed(t.rateUpload or 0),
                        "ratio":    f"{t.uploadRatio:.2f}" if t.uploadRatio and t.uploadRatio >= 0 else "—",
                        "hash":     t.hashString or "",
                    })

                table_container.clear()
                if not rows:
                    with table_container:
                        ui.label("Niciun torrent activ.").classes("text-gray-400 text-sm")
                    return

                with table_container:
                    columns = [
                        {"name": "name",   "label": "Nume",     "field": "name",   "align": "left"},
                        {"name": "status", "label": "Status",   "field": "status"},
                        {"name": "pct",    "label": "%",        "field": "pct"},
                        {"name": "size",   "label": "Mărime",   "field": "size"},
                        {"name": "down",   "label": "↓",        "field": "down"},
                        {"name": "up",     "label": "↑",        "field": "up"},
                        {"name": "ratio",  "label": "Ratio",    "field": "ratio"},
                        {"name": "actions","label": "",         "field": "id"},
                    ]
                    tbl = ui.table(columns=columns, rows=rows, row_key="hash").classes("w-full")

                    tbl.add_slot("body-cell-status", """
                        <q-td :props="props">
                            <q-badge :color="
                                props.value === 'downloading' ? 'blue'  :
                                props.value === 'seeding'     ? 'green' :
                                props.value === 'stopped'     ? 'grey'  :
                                props.value === 'checking'    ? 'orange': 'purple'">
                                {{ props.value }}
                            </q-badge>
                        </q-td>
                    """)
                    tbl.add_slot("body-cell-pct", """
                        <q-td :props="props">
                            <div class="flex items-center gap-2">
                                <q-linear-progress
                                    :value="props.value / 100"
                                    :color="props.value === 100 ? 'green' : 'blue'"
                                    class="w-16" rounded />
                                <span class="text-xs">{{ props.value }}%</span>
                            </div>
                        </q-td>
                    """)
                    tbl.add_slot("body-cell-actions", """
                        <q-td :props="props">
                            <q-btn flat dense
                                :icon="props.row.status === 'stopped' ? 'play_arrow' : 'pause'"
                                :color="props.row.status === 'stopped' ? 'green' : 'orange'"
                                @click="$parent.$emit('toggle', props.row)" />
                            <q-btn flat dense icon="delete" color="red"
                                @click="$parent.$emit('remove', props.row)" />
                        </q-td>
                    """)

                    async def handle_toggle(e):
                        tid = e.args["id"]
                        status = e.args["status"]
                        def _do():
                            c = _connect_transmission()
                            if status == "stopped":
                                c.start_torrent(tid)
                            else:
                                c.stop_torrent(tid)
                        await run.io_bound(_do)
                        await refresh()

                    async def handle_remove(e):
                        tid = e.args["id"]
                        await run.io_bound(lambda: _connect_transmission().remove_torrent(tid, delete_data=False))
                        ui.notify("Torrent eliminat (fișierele rămân)", type="warning")
                        await refresh()

                    tbl.on("toggle", handle_toggle)
                    tbl.on("remove", handle_remove)

            except Exception as ex:
                err_label.set_text(f"Transmission offline: {ex}")
                err_label.classes(remove="hidden")

        ui.timer(0.1, refresh, once=True)
        ui.timer(15, refresh)
