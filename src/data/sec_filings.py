from src.data.reuse import memoized
import re
import requests

from bs4 import BeautifulSoup

from src.config import SEC_USER_AGENT
from src.data.sec_data import get_company_cik


# =========================================================
# SEC Configuration
# =========================================================

SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate"
}

SEC_SUBMISSIONS_BASE_URL = (
    "https://data.sec.gov/submissions"
)

SEC_ARCHIVES_BASE_URL = (
    "https://www.sec.gov/Archives/edgar/data"
)


# =========================================================
# Company Submissions
# =========================================================

@memoized
def get_company_submissions(ticker):
    """
    Return SEC submissions metadata
    for a company.

    Includes recent 10-K, 10-Q, 8-K, etc.
    """

    cik = get_company_cik(ticker)

    if cik is None:
        return None

    url = (
        f"{SEC_SUBMISSIONS_BASE_URL}/"
        f"CIK{cik}.json"
    )

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# Recent Filings
# =========================================================

def get_recent_filings(ticker):
    """
    Return recent SEC filing metadata.
    """

    submissions = get_company_submissions(
        ticker
    )

    if submissions is None:
        return None

    return (
        submissions
        .get("filings", {})
        .get("recent", {})
    )


# =========================================================
# Find Latest Filing
# =========================================================

def get_latest_filing(
    ticker,
    form_type="10-K"
):
    """
    Return the latest filing matching
    the requested form type.
    """

    filings = get_recent_filings(
        ticker
    )

    if filings is None:
        return None

    forms = filings.get(
        "form",
        []
    )

    accession_numbers = filings.get(
        "accessionNumber",
        []
    )

    filing_dates = filings.get(
        "filingDate",
        []
    )

    report_dates = filings.get(
        "reportDate",
        []
    )

    primary_documents = filings.get(
        "primaryDocument",
        []
    )

    for index, form in enumerate(forms):

        if form == form_type:

            return {
                "ticker":
                    ticker.upper(),

                "form":
                    form,

                "accession_number":
                    accession_numbers[index],

                "filing_date":
                    filing_dates[index],

                "report_date":
                    report_dates[index],

                "primary_document":
                    primary_documents[index]
            }

    return None


# =========================================================
# Filing URL
# =========================================================

def build_filing_url(
    ticker,
    filing
):
    """
    Build SEC filing document URL.
    """

    if filing is None:
        return None

    cik = get_company_cik(
        ticker
    )

    if cik is None:
        return None

    cik_without_leading_zeros = (
        str(
            int(cik)
        )
    )

    accession_number = (
        filing[
            "accession_number"
        ]
    )

    accession_no_dashes = (
        accession_number.replace(
            "-",
            ""
        )
    )

    primary_document = (
        filing[
            "primary_document"
        ]
    )

    return (
        f"{SEC_ARCHIVES_BASE_URL}/"
        f"{cik_without_leading_zeros}/"
        f"{accession_no_dashes}/"
        f"{primary_document}"
    )


# =========================================================
# Latest 10-K
# =========================================================

def get_latest_10k(ticker):
    """
    Return latest 10-K metadata
    including filing URL.
    """

    filing = get_latest_filing(
        ticker,
        form_type="10-K"
    )

    if filing is None:
        return None

    filing["url"] = (
        build_filing_url(
            ticker,
            filing
        )
    )

    return filing


# =========================================================
# Latest 10-Q
# =========================================================

def get_latest_10q(ticker):
    """
    Return latest 10-Q metadata
    including filing URL.
    """

    filing = get_latest_filing(
        ticker,
        form_type="10-Q"
    )

    if filing is None:
        return None

    filing["url"] = (
        build_filing_url(
            ticker,
            filing
        )
    )

    return filing


# =========================================================
# Filing Selector
# =========================================================

def get_filing_by_form(
    ticker,
    form_type="10-K"
):
    """
    Return latest filing metadata
    for supported form type.
    """

    if form_type == "10-K":

        return get_latest_10k(
            ticker
        )

    elif form_type == "10-Q":

        return get_latest_10q(
            ticker
        )

    else:

        filing = get_latest_filing(
            ticker,
            form_type=form_type
        )

        if filing is None:
            return None

        filing["url"] = (
            build_filing_url(
                ticker,
                filing
            )
        )

        return filing


# =========================================================
# Download Filing HTML
# =========================================================

@memoized
def get_filing_html(
    ticker,
    form_type="10-K"
):
    """
    Download the raw HTML
    of the latest filing.
    """

    filing = get_filing_by_form(
        ticker,
        form_type=form_type
    )

    if filing is None:
        return None

    url = filing.get(
        "url"
    )

    if url is None:
        return None

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=60
    )

    response.raise_for_status()

    return response.text


# =========================================================
# Clean Filing Text
# =========================================================

def clean_filing_text(text):
    """
    Clean extracted filing text.

    Removes excessive spaces and line breaks
    while preserving readable structure.
    """

    if text is None:
        return None

    text = text.replace(
        "\xa0",
        " "
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n\s*\n+",
        "\n",
        text
    )

    text = text.strip()

    return text


# =========================================================
# Extract Filing Text
# =========================================================

@memoized
def get_filing_text(
    ticker,
    form_type="10-K"
):
    """
    Download filing HTML and convert it
    into searchable plain text.
    """

    html = get_filing_html(
        ticker,
        form_type=form_type
    )

    if html is None:
        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Remove elements that are usually
    # not useful for textual analysis.
    for tag in soup(
        [
            "script",
            "style"
        ]
    ):
        tag.decompose()

    text = soup.get_text(
        separator="\n"
    )

    return clean_filing_text(
        text
    )


# =========================================================
# Search Filing Text
# =========================================================

def search_filing_text(
    ticker,
    keyword,
    form_type="10-K",
    context_chars=500,
    max_results=5
):
    """
    Search the filing for a keyword.

    Returns text around each match.

    Search is case-insensitive.
    """

    text = get_filing_text(
        ticker,
        form_type=form_type
    )

    if text is None:
        return []

    if not keyword:
        return []

    text_lower = text.lower()
    keyword_lower = keyword.lower()

    results = []

    start_position = 0

    while True:

        index = text_lower.find(
            keyword_lower,
            start_position
        )

        if index == -1:
            break

        context_start = max(
            0,
            index - context_chars
        )

        context_end = min(
            len(text),
            index
            + len(keyword)
            + context_chars
        )

        context = text[
            context_start:
            context_end
        ]

        results.append(
            {
                "keyword":
                    keyword,

                "match_position":
                    index,

                "context":
                    context.strip()
            }
        )

        if len(results) >= max_results:
            break

        start_position = (
            index
            + len(keyword_lower)
        )

    return results


# =========================================================
# Search Multiple Keywords
# =========================================================

def search_filing_keywords(
    ticker,
    keywords,
    form_type="10-K",
    context_chars=500,
    max_results_per_keyword=3
):
    """
    Search multiple research keywords
    in the same filing.
    """

    results = {}

    for keyword in keywords:

        results[keyword] = (
            search_filing_text(
                ticker=ticker,
                keyword=keyword,
                form_type=form_type,
                context_chars=context_chars,
                max_results=max_results_per_keyword
            )
        )

    return results


# =========================================================
# Company Filing Summary
# =========================================================

def get_filing_summary(ticker):
    """
    Return latest 10-K and 10-Q.
    """

    return {
        "ticker":
            ticker.upper(),

        "latest_10k":
            get_latest_10k(
                ticker
            ),

        "latest_10q":
            get_latest_10q(
                ticker
            )
    }


# =========================================================
# Display Filing Metadata
# =========================================================

def print_filing(
    title,
    filing
):
    """
    Pretty-print filing metadata.
    """

    print("\n==============================")
    print(title)
    print("==============================")

    if filing is None:

        print("N/A")

        return

    print(
        f"Ticker: "
        f"{filing.get('ticker')}"
    )

    print(
        f"Form: "
        f"{filing.get('form')}"
    )

    print(
        f"Report Date: "
        f"{filing.get('report_date')}"
    )

    print(
        f"Filing Date: "
        f"{filing.get('filing_date')}"
    )

    print(
        f"Accession Number: "
        f"{filing.get('accession_number')}"
    )

    print(
        f"Primary Document: "
        f"{filing.get('primary_document')}"
    )

    print(
        f"URL: "
        f"{filing.get('url')}"
    )


# =========================================================
# Display Search Results
# =========================================================

def print_search_results(
    keyword,
    results
):
    """
    Pretty-print filing search results.
    """

    print("\n==============================")
    print(f"SEARCH: {keyword}")
    print("==============================")

    if not results:

        print("No results found.")

        return

    for index, result in enumerate(
        results,
        start=1
    ):

        print(
            f"\n--- Result {index} ---"
        )

        print(
            result[
                "context"
            ]
        )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    print("\n==============================")
    print(f"SEC FILINGS TEST: {ticker}")
    print("==============================")

    print(
        f"\nCIK: "
        f"{get_company_cik(ticker)}"
    )

    # -----------------------------------------------------
    # Latest Filings
    # -----------------------------------------------------

    latest_10k = (
        get_latest_10k(
            ticker
        )
    )

    latest_10q = (
        get_latest_10q(
            ticker
        )
    )

    print_filing(
        "LATEST 10-K",
        latest_10k
    )

    print_filing(
        "LATEST 10-Q",
        latest_10q
    )

    # -----------------------------------------------------
    # Filing Text Test
    # -----------------------------------------------------

    print("\n==============================")
    print("10-K TEXT TEST")
    print("==============================")

    filing_text = (
        get_filing_text(
            ticker,
            form_type="10-K"
        )
    )

    if filing_text is None:

        print(
            "Unable to retrieve filing text."
        )

    else:

        print(
            f"Extracted Characters: "
            f"{len(filing_text):,}"
        )

        print(
            "\nFirst 1,000 characters:\n"
        )

        print(
            filing_text[:1000]
        )

    # -----------------------------------------------------
    # Research Keyword Test
    # -----------------------------------------------------

    research_keywords = [
        "marketable securities",
        "interest income",
        "other income",
        "segment"
    ]

    print("\n==============================")
    print("10-K KEYWORD SEARCH")
    print("==============================")

    keyword_results = (
        search_filing_keywords(
            ticker=ticker,
            keywords=research_keywords,
            form_type="10-K",
            context_chars=350,
            max_results_per_keyword=2
        )
    )

    for keyword, results in (
        keyword_results.items()
    ):

        print_search_results(
            keyword,
            results
        )