"""Download legal open-access copies of the manuscript reference list.

The list is read from scripts/write_manuscript_docx.py. Each DOI is sent to
the Unpaywall API, which returns publisher and repository files that the
publisher or the author has released. Closed papers are recorded with their
DOI and are not fetched from other sites. This step does not change any
soil-loss, connectivity, or model result.
"""

import ast
import csv
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "write_manuscript_docx.py"
OUT_DIR = ROOT / "literature" / "cited"
TABLE = ROOT / "output" / "tables" / "cited_literature_downloads.csv"
EMAIL = "Mukesh.tiwari1@icar.org.in"
BLOCKED = ("sci-hub", "libgen", "annas-archive", "z-lib", "zlibrary", "bookfi")

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": f"TilaiyaLiteratureBot/1.0 (mailto:{EMAIL})",
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.5",
    }
)


def reference_list():
    text = SOURCE.read_text(encoding="utf-8")
    match = re.search(r"\n    refs = (\[.*?\])\n    for item in refs:", text, re.S)
    if not match:
        raise SystemExit("The reference list was not found in the manuscript script.")
    return ast.literal_eval(match.group(1))


def doi_of(citation):
    match = re.search(r"10\.\d{4,9}/\S+", citation)
    if not match:
        return ""
    return match.group(0).rstrip(").,;")


def slug(citation, index):
    year = re.search(r"(19|20)\d{2}", citation)
    author = re.split(r",|\.", citation, maxsplit=1)[0]
    author = re.sub(r"[^A-Za-z0-9]+", "", author) or "ref"
    year_text = year.group(0) if year else "nd"
    return f"{index:02d}_{author}_{year_text}"


def unpaywall(doi):
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='/')}?email={EMAIL}"
    response = SESSION.get(url, timeout=40)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def pdf_candidates(record):
    if not record:
        return []
    found = []
    best = record.get("best_oa_location") or {}
    locations = [best] + list(record.get("oa_locations") or [])
    for location in locations:
        if not location:
            continue
        for key in ("url_for_pdf", "url"):
            link = location.get(key) or ""
            if link and link not in found:
                found.append(link)
    return found


def allowed(link):
    host = link.lower()
    return not any(name in host for name in BLOCKED)


def save_pdf(link, path):
    response = SESSION.get(link, timeout=90, allow_redirects=True, stream=True)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    content_type = (response.headers.get("Content-Type") or "").lower()
    data = response.content
    if not data.startswith(b"%PDF") and "pdf" not in content_type:
        return False, content_type.split(";")[0] or "not a pdf"
    if not data.startswith(b"%PDF"):
        return False, "response was not a pdf"
    path.write_bytes(data)
    return True, str(len(data))


BROWSER = requests.Session()
BROWSER.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.5",
    }
)

# Publisher or author copies for gold open-access papers whose Unpaywall
# link was the article page rather than the file.
# Author or repository copies used when the publisher page did not return a file.
AUTHOR_PDF = {
    "04_Ballabio_2017": [
        "https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC5206222&blobtype=pdf"
    ],
    "10_Breiman_2001": ["https://www.stat.berkeley.edu/~breiman/randomforest2001.pdf"],
    "28_Lundberg_2017": ["https://arxiv.org/pdf/1705.07874"],
    "36_Prokhorenkova_2018": ["https://arxiv.org/pdf/1706.09516"],
}

DIRECT_PDF = {
    "10.3390/su7043528": ["https://www.mdpi.com/2071-1050/7/4/3528/pdf"],
    "10.1007/s44288-025-00191-w": [
        "https://link.springer.com/content/pdf/10.1007/s44288-025-00191-w.pdf"
    ],
    "10.1186/s12302-025-01079-9": [
        "https://enveurope.springeropen.com/counter/pdf/10.1186/s12302-025-01079-9.pdf",
        "https://link.springer.com/content/pdf/10.1186/s12302-025-01079-9.pdf",
    ],
    "10.5194/hess-22-6059-2018": [
        "https://hess.copernicus.org/articles/22/6059/2018/hess-22-6059-2018.pdf"
    ],
    "10.5194/soil-7-217-2021": [
        "https://soil.copernicus.org/articles/7/217/2021/soil-7-217-2021.pdf"
    ],
    "10.1038/s41467-020-18321-y": [
        "https://www.nature.com/articles/s41467-020-18321-y.pdf"
    ],
}


def pdf_page_count(path):
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return 0


def save_response(response, path):
    data = response.content
    if response.status_code != 200 or not data.startswith(b"%PDF"):
        return False
    path.write_bytes(data)
    return pdf_page_count(path) >= 2


def fetch_pdf(link, path):
    if not allowed(link):
        return False
    try:
        response = BROWSER.get(link, timeout=90, allow_redirects=True)
    except requests.RequestException:
        return False
    return save_response(response, path)


def pdf_links_from_html(page_url, html):
    found = []
    for match in re.findall(r'citation_pdf_url"\s+content="([^"]+)"', html, flags=re.I):
        found.append(match)
    for match in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, flags=re.I):
        if match.startswith("http"):
            found.append(match)
        elif match.startswith("/"):
            root = re.match(r"https?://[^/]+", page_url)
            if root:
                found.append(root.group(0) + match)
    unique = []
    for link in found:
        if link not in unique and allowed(link):
            unique.append(link)
    return unique


def try_links(links, path):
    for link in links:
        if fetch_pdf(link, path):
            return link
        try:
            response = BROWSER.get(link, timeout=60, allow_redirects=True)
        except requests.RequestException:
            continue
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "html" not in content_type and not response.text[:200].lstrip().startswith("<"):
            continue
        for nested in pdf_links_from_html(response.url, response.text):
            if fetch_pdf(nested, path):
                return nested
    return ""


def crossref_doi(citation):
    author = re.split(r",|\.", citation, maxsplit=1)[0].strip()
    year_match = re.search(r"(19|20)\d{2}", citation)
    year = year_match.group(0) if year_match else ""
    try:
        response = SESSION.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": citation[:240], "rows": 3},
            timeout=40,
        )
        response.raise_for_status()
        items = response.json()["message"]["items"]
    except (requests.RequestException, KeyError, ValueError):
        return ""
    for item in items:
        issued = item.get("issued", {}).get("date-parts", [[None]])[0][0]
        names = " ".join(
            person.get("family", "") for person in item.get("author", [])[:3]
        )
        if year and str(issued) != year:
            continue
        if author.lower() not in names.lower():
            continue
        return item.get("DOI", "")
    return ""


def retry_missing():
    """Second pass for open-access pages that did not return a file."""
    recovered = []
    citations = reference_list()
    for index, citation in enumerate(citations, start=1):
        name = slug(citation, index)
        path = OUT_DIR / f"{name}.pdf"
        if path.exists() and pdf_page_count(path) >= 2:
            continue
        doi = doi_of(citation) or crossref_doi(citation)
        links = list(AUTHOR_PDF.get(name, [])) + list(DIRECT_PDF.get(doi, []))
        record = None
        if doi:
            try:
                record = unpaywall(doi)
            except requests.RequestException:
                record = None
            links.extend(link for link in pdf_candidates(record) if allowed(link))
        if not links and not doi:
            recovered.append((name, "no open-access file", doi, citation))
            print(f"{index:02d} still missing {name}", flush=True)
            continue
        used = try_links(links, path)
        if used:
            pages = pdf_page_count(path)
            recovered.append((name, f"saved {pages} pages", doi, used))
            print(f"{index:02d} retry saved {name} {pages} pages", flush=True)
        else:
            status = "closed" if record and not record.get("is_oa") else "no open-access pdf"
            recovered.append((name, status, doi, citation))
            print(f"{index:02d} retry {status} {doi or name}", flush=True)
        time.sleep(0.4)
    return recovered


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    citations = reference_list()
    for index, citation in enumerate(citations, start=1):
        doi = doi_of(citation)
        name = slug(citation, index)
        status = "no doi"
        link_used = ""
        oa_status = ""
        note = "No DOI in the reference. Not fetched."
        if doi:
            try:
                record = unpaywall(doi)
            except requests.RequestException as error:
                record = None
                status = "lookup failed"
                note = str(error)
            else:
                oa_status = (record or {}).get("oa_status") or "closed"
                candidates = [link for link in pdf_candidates(record) if allowed(link)]
                if not record:
                    status = "doi not in unpaywall"
                    note = doi
                elif not record.get("is_oa") or not candidates:
                    status = "closed"
                    note = doi
                else:
                    saved = False
                    for link in candidates:
                        path = OUT_DIR / f"{name}.pdf"
                        try:
                            ok, detail = save_pdf(link, path)
                        except requests.RequestException as error:
                            ok, detail = False, str(error)
                        if ok:
                            status = "saved"
                            link_used = link
                            note = detail
                            saved = True
                            break
                    if not saved:
                        status = "oa link was not a pdf"
                        link_used = candidates[0]
                        note = doi
            time.sleep(0.4)
        rows.append(
            {
                "file": f"{name}.pdf" if status == "saved" else "",
                "status": status,
                "oa_status": oa_status,
                "doi": doi,
                "url": link_used,
                "bytes": note if status == "saved" else "",
                "citation": citation,
            }
        )
        print(f"{index:02d} {status} {doi or name}", flush=True)
    with TABLE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file", "status", "oa_status", "doi", "url", "bytes", "citation"],
        )
        writer.writeheader()
        writer.writerows(rows)
    saved = sum(row["status"] == "saved" for row in rows)
    print(f"saved {saved} of {len(rows)}")
    print(TABLE)
    print(OUT_DIR)
    recovered = retry_missing()
    retry_table = TABLE.with_name("cited_literature_retry.csv")
    with retry_table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file", "status", "doi", "detail"])
        writer.writerows(recovered)
    print(retry_table)


if __name__ == "__main__":
    main()
