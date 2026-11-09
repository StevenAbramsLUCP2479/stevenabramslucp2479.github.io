#!/usr/bin/env python3
"""Import public ORCID works, preserving editorial changes and stable URLs."""
import argparse
from datetime import date
import html
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]
ORCID = "0000-0001-7353-9304"
API = f"https://pub.orcid.org/v3.0/{ORCID}"
CATEGORIES = {"journal-article": "manuscripts", "preprint": "preprints",
              "book-chapter": "books", "conference-paper": "conferences"}


def value(obj):
    return (obj or {}).get("value") or ""


def clean(text):
    return " ".join(html.unescape(str(text)).split())


def safe(text):
    # Front matter is rendered as HTML and may also be processed by Liquid.
    return html.escape(clean(text), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def title_key(text):
    return "".join(c for c in unicodedata.normalize("NFKD", clean(text)).casefold()
                   if c.isalnum())


def doi_key(text):
    text = clean(text).lower()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text)
    return text if re.fullmatch(r"10\.\d{4,9}/[^\s<>\"{}]+", text) else ""


def get_json(url):
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "StevenAbramsWebsitePublicationSync/1.0"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except (HTTPError, URLError) as error:
            if isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def fetch_works():
    groups = get_json(f"{API}/works")["group"]
    if not groups:
        raise ValueError("ORCID returned no works; refusing an empty response")
    codes = sorted({int(max(g["work-summary"], key=lambda w: int(w.get("display-index") or 0))
                        ["put-code"]) for g in groups})
    works = []
    for start in range(0, len(codes), 50):
        batch = codes[start:start + 50]
        result = get_json(f"{API}/works/" + ",".join(map(str, batch)))
        fetched = [entry["work"] for entry in result["bulk"] if entry.get("work")]
        if len(fetched) != len(batch) or {w["put-code"] for w in fetched} != set(batch):
            raise ValueError("Incomplete ORCID response; no files were changed")
        works.extend(fetched)
    return works


def metadata(work):
    category = CATEGORIES.get(work.get("type"))
    if not category:
        return None
    title = clean(value((work.get("title") or {}).get("title")))
    published = work.get("publication-date") or {}
    year, month, day = [value(published.get(part)) for part in ("year", "month", "day")]
    if not title or not year:
        return None
    stamp = date(int(year), int(month or 1), int(day or 1)).isoformat()
    precision = "day" if day else "month" if month else "year"
    venue = clean(value(work.get("journal-title"))) or ("Preprint" if category == "preprints" else "")
    identifiers = (work.get("external-ids") or {}).get("external-id") or []
    dois = sorted({doi_key(item["external-id-value"]) for item in identifiers
                   if item.get("external-id-type") == "doi"
                   and item.get("external-id-relationship") == "self"} - {""})
    if len(dois) > 1:
        raise ValueError(f"Conflicting self DOIs for ORCID work {work['put-code']}")
    authors = [safe(value(c.get("credit-name"))) for c in
               ((work.get("contributors") or {}).get("contributor") or [])
               if value(c.get("credit-name")) and
               (c.get("contributor-attributes") or {}).get("contributor-role") in (None, "author")]
    citation = ("; ".join(authors) + ". " if authors else "") + f"({year}). {safe(title)}."
    if venue:
        citation += f" <i>{safe(venue)}</i>."
    result = {"title": safe(title), "category": category, "date": stamp,
              "date_precision": precision, "venue": safe(venue), "citation": citation}
    if dois:
        result["doi"] = dois[0]
    url = value(work.get("url"))
    if urlparse(url).scheme in ("https", "http") and urlparse(url).netloc:
        result["paperurl"] = safe(url)
    return result


def read_record(path):
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError(f"Invalid front matter: {path}")
    return yaml.safe_load(parts[1]), parts[2]


def render(data, body):
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100) + "---" + body


def sync(works, root=ROOT, ignored=()):
    directory = root / "_publications"
    records = {p: read_record(p) for p in sorted(directory.glob("*.md"))}
    pending, notes = {}, []
    ignored = {str(code) for code in ignored}
    # Plan every change before writing, so malformed remote data cannot partly update the site.
    for work in sorted(works, key=lambda w: int(w["put-code"])):
        code = str(work["put-code"])
        if code in ignored:
            continue
        incoming = metadata(work)
        if incoming is None:
            notes.append(f"Skipped ORCID {code}: unsupported type or missing title/year.")
            continue
        doi, title = doi_key(incoming.get("doi", "")), title_key(incoming["title"])
        matches = [p for p, (d, _) in records.items() if str(d.get("orcid_put_code")) == code
                   or (doi and doi_key(d.get("doi", "")) == doi)]
        if not matches:
            matches = [p for p, (d, _) in records.items()
                       if (d.get("category") == "preprints") == (incoming["category"] == "preprints")
                       and title_key(d.get("title", "")) == title
                       and not (doi and doi_key(d.get("doi", "")) and doi_key(d["doi"]) != doi)]
        if len(matches) > 1:
            notes.append(f"Review ORCID {code}: multiple matching local records; left unchanged.")
            continue
        if matches:
            path = matches[0]
            data, body = records[path]
            previous = data.get("orcid_imported", {})
            # Legacy records are curated; only previously imported fields are managed.
            if not previous or str(data.get("orcid_put_code")) != code:
                continue
            data = dict(data)
            updated = dict(previous)
            for key, new in incoming.items():
                if key in previous and str(data.get(key, "")) == str(previous[key]):
                    data[key] = new
                    updated[key] = new
                elif key not in previous and key not in data:
                    data[key] = new
                    updated[key] = new
                elif data.get(key) != new:
                    notes.append(f"Preserved editorial field {path.name}: {key}.")
            # Missing upstream fields never remove local content.
            data["orcid_imported"] = updated
            rendered = render(data, body)
            if rendered != path.read_text(encoding="utf-8"):
                pending[path] = rendered
                notes.append(f"Updated: {clean(incoming['title'])}")
            records[path] = data, body
        else:
            slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", clean(incoming["title"]))
                          .encode("ascii", "ignore").decode().lower()).strip("-")[:80].rstrip("-")
            name = f"{incoming['date']}-{slug}-orcid-{code}"
            path = directory / f"{name}.md"
            if path.exists() or path in pending:
                raise ValueError(f"Publication filename collision: {path}")
            data = {**incoming, "collection": "publications", "permalink": f"/publication/{name}/",
                    "orcid_put_code": code, "orcid_imported": incoming}
            body = f"\n\n_Metadata sourced from [ORCID](https://orcid.org/{ORCID})._\n"
            pending[path] = render(data, body)
            records[path] = data, body
            notes.append(f"Added: {clean(incoming['title'])}")
    # Keep preprints available and connect identical titles to their journal versions.
    for path, (data, body) in list(records.items()):
        if data.get("category") != "preprints" or data.get("published_version"):
            continue
        journals = [d for d, _ in records.values() if d.get("category") == "manuscripts"
                    and title_key(d.get("title", "")) == title_key(data["title"])]
        if len(journals) == 1:
            data = {**data, "published_version": journals[0]["permalink"]}
            pending[path] = render(data, body)
            notes.append(f"Linked published version: {clean(data['title'])}")
    for path, content in pending.items():
        path.write_text(content, encoding="utf-8")
    return len(pending), notes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="Offline JSON array of ORCID work details")
    parser.add_argument("--report", type=Path, default=Path("publication-sync-report.md"))
    args = parser.parse_args()
    config = json.loads((ROOT / "scripts/publication_sync_config.json").read_text())
    works = json.loads(args.fixture.read_text()) if args.fixture else fetch_works()
    count, notes = sync(works, ignored=config["ignored_put_codes"])
    report = (f"# ORCID publication check\n\nSource: https://orcid.org/{ORCID}\n\n"
              f"Checked {len(works)} preferred work records; changed {count} publication files.\n\n"
              + "\n".join("- " + note for note in notes) + "\n\n"
              "Review the publication changes before merging. Existing curated metadata is preserved.\n")
    args.report.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
