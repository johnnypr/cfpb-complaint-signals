"""Universe, paths, and analysis windows."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"              # CFPB archive zips (git-ignored, ~1.3 GB)
INTERIM = DATA / "interim"      # filtered complaints in DuckDB (git-ignored)
PROCESSED = DATA / "processed"  # small derived tables (committed)
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
SQL_DIR = ROOT / "sql"
DB_PATH = INTERIM / "cfpb.duckdb"

# The live CFPB API stopped serving narratives on 2026-08-14; the full records (with the
# previously published narratives) now live in the CFPB FOIA reading room as zipped CSVs.
ARCHIVE_PAGE = ("https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/"
                "cfpb-consumer-complaint-database-narratives-archive/")
# Exports from May 2018 onward (export #1, Dec 2011 - Apr 2018, is skipped to keep it light)
FIRST_EXPORT = 2
API_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"

# CFPB company name -> listed ticker.  Large US card issuers / banks plus two fintechs.
COMPANIES = {
    "JPMORGAN CHASE & CO.": "JPM",
    "BANK OF AMERICA, NATIONAL ASSOCIATION": "BAC",
    "WELLS FARGO & COMPANY": "WFC",
    "CITIBANK, N.A.": "C",
    "CAPITAL ONE FINANCIAL CORPORATION": "COF",
    "SYNCHRONY FINANCIAL": "SYF",
    "AMERICAN EXPRESS COMPANY": "AXP",
    "ALLY FINANCIAL INC.": "ALLY",
    "Paypal Holdings, Inc": "PYPL",
    "Block, Inc.": "XYZ",   # Block (Cash App / Square); ticker changed from SQ to XYZ in 2025
}
BENCHMARK = "XLF"  # Financial Select Sector SPDR, for excess returns

# Quarterly analysis windows (complete quarters only)
VOLUME_START, VOLUME_END = "2018-07-01", "2026-06-30"      # complaint counts (all complaints)
TOPIC_START, TOPIC_END = "2018-07-01", "2025-12-31"        # narratives (coverage collapses in 2026)

N_TOPICS = 12
FIT_SAMPLE = 120_000   # narratives used to fit TF-IDF + NMF (all narratives are then scored)
SEED = 72

# Human-readable topic labels, assigned by reading each topic's top terms and its most
# representative narratives (data/processed/topics_top_terms.json, topic_examples.csv).
# NMF with a fixed seed on the same data reproduces the same topic order; if you change the
# data window, N_TOPICS or the vectorizer, re-check these labels.
TOPIC_LABELS = [
    "Credit-report accuracy / debt (FCRA)",
    "FCRA legal template ('15 USC 1681')",
    "Unauthorized hard inquiries",
    "Fraud-platform template",
    "Late payments & fees",
    "Card account, limits & closures",
    "Deposits, transfers & frozen funds",
    "Identity theft",
    "Transaction disputes & refunds",
    "Account-closure template",
    "Auto & mortgage loans",
    "Customer service & promotions",
]
TEMPLATE_MIN_COPIES = 10  # a narrative opening shared by >= this many complaints = template / copy-paste
