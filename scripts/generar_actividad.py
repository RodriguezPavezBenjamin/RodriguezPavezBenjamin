"""Genera un calendario SVG animado a partir de contribuciones públicas de GitHub.

Solo biblioteca estándar. No necesita tokens ni consulta repositorios privados.
Los disparos usan los niveles 1–4 del calendario original, no métricas inventadas.
"""

import argparse
import datetime as dt
import json
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


class Calendario(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}
        self.tips = {}
        self.tip_id = None
        self.tip_text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("data-date") and a.get("data-level") is not None:
            self.days[a["id"]] = {"date": a["data-date"], "level": int(a["data-level"])}
        if tag == "tool-tip" and a.get("for"):
            self.tip_id, self.tip_text = a["for"], []

    def handle_data(self, data):
        if self.tip_id is not None:
            self.tip_text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tip_id is not None:
            self.tips[self.tip_id] = " ".join(self.tip_text).strip()
            self.tip_id = None

    def result(self):
        result = []
        for cell_id, day in self.days.items():
            label = self.tips.get(cell_id, "")
            match = re.search(r"([\d,]+)\s+contributions?", label)
            if not label or (day["level"] and not match):
                raise ValueError(f"No se puede determinar la actividad de {day['date']}")
            result.append({**day, "count": int(match[1].replace(",", "")) if match else 0})
        if len(result) < 350:
            raise ValueError("Calendario incompleto; se conserva la imagen publicada")
        return result


def fetch_days(user):
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", user):
        raise ValueError("Nombre de usuario inválido")
    request = Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "github-profile-space-activity", "Accept-Language": "en-US"},
    )
    with urlopen(request, timeout=45) as response:
        parser = Calendario()
        parser.feed(response.read().decode("utf-8"))
    return parser.result()


def render(days):
    days = sorted(days, key=lambda d: d["date"])
    if not days:
        raise ValueError("Calendario vacío")
    for day in days:
        dt.date.fromisoformat(day["date"])
        if day["level"] not in range(5) or day["count"] < 0:
            raise ValueError("Actividad inválida")
    first = dt.date.fromisoformat(days[0]["date"])
    sunday = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    last = dt.date.fromisoformat(days[-1]["date"])
    columns = (last - sunday).days // 7 + 1
    pitch = min(20, 1060 / columns)
    tile = pitch - 4
    colors = ["#23151f", "#64243a", "#a5304e", "#e44b6a", "#ff8ca3"]
    active = []
    parts = []
    total = sum(d["count"] for d in days)
    end = last.strftime("%d/%m/%Y")
    parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="430" viewBox="0 0 1200 430" role="img" aria-labelledby="title desc">
<title id="title">Actividad en GitHub: {total} contribuciones</title>
<desc id="desc">Calendario público hasta {end}. La nave visita todos los días activos. Nivel 1: disparo simple; nivel 2: doble; nivel 3: triple; nivel 4: ráfaga de plasma. Los días sin actividad no reciben disparos.</desc>
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#24111e"/><stop offset="1" stop-color="#0d1117"/></linearGradient><radialGradient id="halo"><stop stop-color="#f04462" stop-opacity=".16"/><stop offset="1" stop-color="#f04462" stop-opacity="0"/></radialGradient><filter id="glow" x="-150%" y="-100%" width="400%" height="300%"><feGaussianBlur stdDeviation="2"/></filter></defs>
<rect x="1" y="1" width="1198" height="428" rx="22" fill="url(#bg)" stroke="#73313d"/>
<ellipse cx="1040" cy="85" rx="210" ry="130" fill="url(#halo)"/>
<g font-family="Segoe UI,Arial,sans-serif"><text x="35" y="45" fill="#fff3f6" font-size="25" font-weight="700">Actividad en GitHub</text><text x="36" y="73" fill="#d09aaa" font-size="15">{total} contribuciones · últimos 12 meses · {len([d for d in days if d['count']])} días activos</text><text x="1164" y="44" fill="#b77f91" font-size="12" text-anchor="end">ACTIVITY / SPACE</text></g>''')
    months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    prior_month = None
    for day in days:
        date = dt.date.fromisoformat(day["date"])
        column, row = divmod((date - sunday).days, 7)
        x, y = 70 + column * pitch, 126 + row * pitch
        if date.month != prior_month:
            if date.day < 8:
                parts.append(f'<text x="{x:.2f}" y="112" fill="#b48c9b" font-family="Segoe UI,Arial,sans-serif" font-size="12">{months[date.month-1]}</text>')
            prior_month = date.month
        noun = "contribución" if day["count"] == 1 else "contribuciones"
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{tile:.2f}" height="{tile:.2f}" rx="3" fill="{colors[day["level"]]}" data-date="{day["date"]}" data-level="{day["level"]}" data-count="{day["count"]}"><title>{day["date"]}: {day["count"]} {noun}</title></rect>')
        if day["count"]:
            active.append({**day, "x": x + tile / 2, "y": y + tile / 2})
    for row, label in [(1, "Lun"), (3, "Mié"), (5, "Vie")]:
        parts.append(f'<text x="34" y="{139 + row*pitch:.2f}" fill="#a67a8b" font-family="Segoe UI,Arial,sans-serif" font-size="11">{label}</text>')
    # Star field stays below the real calendar, where shots and the ship are visible.
    for i in range(32):
        x, y = 45 + (i * 139) % 1110, 284 + (i * 17) % 76
        parts.append(f'<circle cx="{x}" cy="{y}" r=".8" fill="#c56c85" opacity=".3"/>')
    slot = 1.75
    cycle = max(5, len(active) * slot + .65)
    keys, positions = [0], []
    first_x = active[0]["x"] if active else 600
    positions.append(f"{first_x:.2f} 332")
    for index, day in enumerate(active):
        start = index * slot
        keys.extend([(start + .30) / cycle, (start + slot) / cycle])
        positions.extend([f'{day["x"]:.2f} 332'] * 2)
        # All shots share one clock. Each burst is aligned with the held ship position.
        for shot in range(day["level"]):
            launch = start + .38 + shot * .20
            hit = launch + .32
            times = [0, launch / cycle, hit / cycle, (hit + .10) / cycle, 1]
            kt = ";".join(f"{v:.7f}" for v in times)
            wide = day["level"] == 4
            width = 4 if wide else 2
            color = "#ffd0dc" if wide else "#ff6989"
            parts.append(f'''<g class="shot" data-target="{day['date']}" data-level="{day['level']}" opacity="0"><animate attributeName="opacity" values="0;1;1;0;0" keyTimes="{kt}" calcMode="discrete" dur="{cycle}s" repeatCount="indefinite"/>
<rect x="{day['x']-width/2:.2f}" y="313" width="{width}" height="{16 if wide else 10}" rx="1.5" fill="{color}"><animate attributeName="y" values="313;313;{day['y']-5:.2f};{day['y']-5:.2f};313" keyTimes="{kt}" dur="{cycle}s" repeatCount="indefinite"/></rect></g>''')
            flash_times = ";".join(f"{v:.7f}" for v in [0, hit/cycle, (hit+.10)/cycle, 1])
            parts.append(f'''<g class="impact" opacity="0"><animate attributeName="opacity" values="0;1;0;0" keyTimes="{flash_times}" calcMode="discrete" dur="{cycle}s" repeatCount="indefinite"/><rect x="{day['x']-tile/2-2:.2f}" y="{day['y']-tile/2-2:.2f}" width="{tile+4:.2f}" height="{tile+4:.2f}" rx="4" fill="none" stroke="{color}" stroke-width="2"/><path d="M{day['x']-12:.2f} {day['y']:.2f}h-4m32 0h4M{day['x']:.2f} {day['y']-12:.2f}v-4m0 32v4" stroke="{color}" stroke-width="1.5"/></g>''')
        info_times = ";".join(f"{v:.7f}" for v in [0, (start+.30)/cycle, (start+slot)/cycle, 1])
        shot_names = ["", "simple", "doble", "triple", "plasma"]
        noun = "contribución" if day["count"] == 1 else "contribuciones"
        parts.append(f'<text x="600" y="383" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="13" fill="#dba2b3" opacity="0"><animate attributeName="opacity" values="0;1;0;0" keyTimes="{info_times}" calcMode="discrete" dur="{cycle}s" repeatCount="indefinite"/>{day["date"]} · {day["count"]} {noun} · disparo {shot_names[day["level"]]}</text>')
    keys.append(1)
    positions.append(f"{first_x:.2f} 332")
    parts.append(f'''<g id="ship" transform="translate({first_x:.2f} 332)"><animateTransform attributeName="transform" type="translate" values="{';'.join(positions)}" keyTimes="{';'.join(f'{k:.7f}' for k in keys)}" dur="{cycle}s" repeatCount="indefinite"/>
<ellipse cx="0" cy="17" rx="10" ry="16" fill="#ff3a6b" opacity=".28" filter="url(#glow)"/>
<path d="M-5 10 0 29 5 10" fill="#ff5a7d"><animate attributeName="d" values="M-5 10 0 29 5 10;M-5 10 0 21 5 10;M-5 10 0 29 5 10" dur=".3s" repeatCount="indefinite"/></path>
<path d="M0-22 8-4 21 14 6 9 0 14-6 9-21 14-8-4Z" fill="#f9dbe4" stroke="#ff728f" stroke-width="1.4" stroke-linejoin="round"/><path d="M0-13 4 1 0 5-4 1Z" fill="#b52b54"/><path d="M-15 10-7 6M15 10 7 6" stroke="#a72e50" stroke-width="2"/></g>
<g font-family="Segoe UI,Arial,sans-serif" font-size="11" fill="#b48295"><text x="35" y="408">Intensidad real de GitHub: simple · doble · triple · plasma</text><text x="1164" y="408" text-anchor="end">Actualizado: {end}</text></g></svg>''')
    result = "\n".join(parts)
    ET.fromstring(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default="RodriguezPavezBenjamin")
    parser.add_argument("--input", type=Path, help="JSON local, solo para previsualización")
    parser.add_argument("--output", type=Path, default=Path("assets/actividad-nave.svg"))
    args = parser.parse_args()
    days = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch_days(args.user)
    result = render(days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    print(f"Generado {args.output}: {len(days)} días, {sum(d['count'] for d in days)} contribuciones")


if __name__ == "__main__":
    main()
