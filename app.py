import pandas as pd
import streamlit as st
import json
import re
from datetime import datetime, date, timedelta
import os
from sqlalchemy import Column, Float, ForeignKey, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.pool import NullPool
from transaction_categorizer import TransactionCategorizer

# Database setup
DATABASE_FILE = "mca_business_data.db"
BUSINESS_SEED_FILE = "businesses_seed.json"
_DB_METADATA = MetaData()

BUSINESSES_TABLE = Table(
    "businesses",
    _DB_METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, unique=True, nullable=False),
    Column("processing_percentage", Float, nullable=False, default=0.0),
    Column("created_date", String, nullable=False),
    Column("updated_date", String, nullable=False),
)

PROCESSING_HISTORY_TABLE = Table(
    "processing_history",
    _DB_METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("business_id", Integer, ForeignKey("businesses.id"), nullable=False),
    Column("date", String, nullable=False),
    Column("income_amount", Float, nullable=False),
    Column("processing_amount", Float, nullable=False),
    Column("period_start", String, nullable=False),
    Column("period_end", String, nullable=False),
)

ADVANCES_TABLE = Table(
    "advances",
    _DB_METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("business_id", Integer, ForeignKey("businesses.id"), nullable=False),
    Column("amount_loaned", Float, nullable=False),
    Column("factor_rate", Float, nullable=False),
    Column("split_percentage", Float, nullable=False),
    Column("total_repayable", Float, nullable=False),
    Column("funded_date", String, nullable=False),
    Column("status", String, nullable=False, default="active"),
    Column("notes", String, nullable=False, default=""),
    Column("created_date", String, nullable=False),
    Column("updated_date", String, nullable=False),
)

ADVANCE_PAYMENTS_TABLE = Table(
    "advance_payments",
    _DB_METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("advance_id", Integer, ForeignKey("advances.id"), nullable=False),
    Column("business_id", Integer, ForeignKey("businesses.id"), nullable=False),
    Column("processing_history_id", Integer, ForeignKey("processing_history.id"), nullable=True),
    Column("payment_date", String, nullable=False),
    Column("payment_amount", Float, nullable=False),
    Column("source", String, nullable=False),
    Column("notes", String, nullable=False, default=""),
    Column("created_date", String, nullable=False),
)

APP_SETTINGS_TABLE = Table(
    "app_settings",
    _DB_METADATA,
    Column("key", String, primary_key=True),
    Column("value", String, nullable=False),
)


def get_secret_value(*keys):
    """Safely read a Streamlit secret without breaking local/test runs."""
    for key in keys:
        try:
            value = st.secrets.get(key, None)
            if value:
                return value
        except Exception:
            pass
    return None


def get_database_url():
    """Return a cloud database URL when configured, otherwise local SQLite."""
    database_url = get_secret_value("DATABASE_URL", "database_url") or os.environ.get("DATABASE_URL")
    if database_url:
        return str(database_url)
    return f"sqlite:///{DATABASE_FILE}"


def get_database_engine():
    """Create a database engine for the current runtime."""
    database_url = get_database_url()
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    return create_engine(database_url)


def _normalise_seed_businesses(raw_businesses):
    """Validate business seed rows from secrets or a JSON seed file."""
    if not raw_businesses:
        return []

    if isinstance(raw_businesses, str):
        raw_businesses = json.loads(raw_businesses)

    if isinstance(raw_businesses, dict):
        raw_businesses = raw_businesses.get("businesses", [])

    seed_businesses = []
    for row in raw_businesses:
        if not isinstance(row, dict):
            continue

        name = str(row.get("name", "")).strip()
        rate = row.get("processing_percentage", row.get("processing_rate", row.get("rate")))
        if not name or rate is None:
            continue

        seed_businesses.append({
            "name": name,
            "processing_percentage": float(rate),
        })

    return seed_businesses


def load_seed_businesses():
    """Load optional business seed data from Streamlit secrets or a local JSON file."""
    secrets_businesses = get_secret_value("businesses")
    seed_businesses = _normalise_seed_businesses(secrets_businesses)
    if seed_businesses:
        return seed_businesses

    seed_json = get_secret_value("businesses_json")
    seed_businesses = _normalise_seed_businesses(seed_json)
    if seed_businesses:
        return seed_businesses

    if os.path.exists(BUSINESS_SEED_FILE):
        with open(BUSINESS_SEED_FILE, "r", encoding="utf-8") as seed_file:
            return _normalise_seed_businesses(json.load(seed_file))

    return []


def seed_businesses_from_config():
    """Upsert configured seed businesses into the SQLite database."""
    for business in load_seed_businesses():
        add_or_update_business(business["name"], business["processing_percentage"])

def init_database():
    """Initialize SQLite database with required tables"""
    engine = get_database_engine()
    _DB_METADATA.create_all(engine)
    seed_businesses_from_config()

def clean_account_name(account_name):
    """Clean account name to extract business name"""
    if not account_name:
        return "Unknown Business"
    
    name = str(account_name).strip()
    
    # Remove common bank account suffixes/terms
    remove_terms = [
        r'\bcurrent\s+account\b',
        r'\bbusiness\s+account\b', 
        r'\bsavings\s+account\b',
        r'\bchecking\s+account\b',
        r'\bcompany\s+account\b',
        r'\baccount\b',
        r'\bcurrent\b',
        r'\bsavings\b',
        r'\bchecking\b',
        r'\bbusiness\b',
        r'\bcompany\b',
        r'\bbus\b',
        r'\bcurr\b',
        r'\bacc\b',
        r'\bltd\s+current\b',
        r'\bltd\s+business\b',
        r'\blimited\s+current\b',
        r'\blimited\s+business\b',
        r'\b-\s*\d+\b',  # Remove trailing numbers like "- 1234"
        r'\(\d+\)',      # Remove numbers in parentheses
        r'\[\d+\]',      # Remove numbers in square brackets
        r'\b\d{8,}\b',   # Remove long number sequences (account numbers)
        r'\bsort\s*code\b',
        r'\biban\b',
        r'\bswift\b',
    ]
    
    for term in remove_terms:
        name = re.sub(term, '', name, flags=re.IGNORECASE)
    
    # Remove extra punctuation and clean up
    name = re.sub(r'[_\-]+', ' ', name)  # Replace underscores and dashes with spaces
    name = re.sub(r'\s+', ' ', name)     # Replace multiple spaces with single space
    name = name.strip(' .,;:()[]{}')     # Remove trailing punctuation
    
    # Capitalize properly
    name = ' '.join(word.capitalize() for word in name.split())
    
    # If name is too short or empty after cleaning, return original cleaned version
    if len(name) < 2:
        original = str(account_name).strip()
        return ' '.join(word.capitalize() for word in original.split())
    
    return name

def extract_business_name_from_filename(filename: str) -> str:
    """Extract business name from filename using various patterns (fallback method)"""
    # Remove file extension
    name = os.path.splitext(filename)[0]
    
    # Replace common separators with spaces
    name = re.sub(r'[-_]+', ' ', name)
    
    # Remove common transaction-related words
    name = re.sub(r'\b(transactions?|data|export|statement|bank|account)\b', '', name, flags=re.IGNORECASE)
    
    # Remove dates (YYYY, YYYY-MM, YYYY-MM-DD patterns)
    name = re.sub(r'\b\d{4}(-\d{1,2})?(-\d{1,2})?\b', '', name)
    
    # Remove month names
    name = re.sub(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)\b', '', name, flags=re.IGNORECASE)
    
    # Clean up extra spaces and capitalize properly
    name = ' '.join(name.split()).strip()
    name = ' '.join(word.capitalize() for word in name.split())
    
    return name if name else "Unknown Business"

def get_all_businesses() -> pd.DataFrame:
    """Get all businesses from database"""
    engine = get_database_engine()
    with engine.connect() as conn:
        df = pd.read_sql_query(text('''
        SELECT id, name, processing_percentage, created_date, updated_date 
        FROM businesses 
        ORDER BY name
    '''), conn)
    return df

def add_or_update_business(name: str, processing_percentage: float) -> int:
    """Add new business or update existing one"""
    current_time = datetime.now().isoformat()

    engine = get_database_engine()
    with engine.begin() as conn:
        result = conn.execute(text('''
            UPDATE businesses 
            SET processing_percentage = :processing_percentage, updated_date = :updated_date
            WHERE name = :name
        '''), {
            "processing_percentage": processing_percentage,
            "updated_date": current_time,
            "name": name,
        })

        if result.rowcount == 0:
            conn.execute(text('''
                INSERT INTO businesses (name, processing_percentage, created_date, updated_date)
                VALUES (:name, :processing_percentage, :created_date, :updated_date)
            '''), {
                "name": name,
                "processing_percentage": processing_percentage,
                "created_date": current_time,
                "updated_date": current_time,
            })

        business_id = conn.execute(
            text('SELECT id FROM businesses WHERE name = :name'),
            {"name": name},
        ).fetchone()[0]

    return business_id

def update_business_by_id(business_id: int, name: str, processing_percentage: float) -> int:
    """Update an existing business by ID, preserving identity across renames."""
    name = name.strip()
    if not name:
        raise ValueError("Business name cannot be blank.")

    current_time = datetime.now().isoformat()
    engine = get_database_engine()
    with engine.begin() as conn:
        duplicate = conn.execute(text('''
            SELECT id FROM businesses
            WHERE name = :name AND id != :business_id
        '''), {"name": name, "business_id": business_id}).fetchone()
        if duplicate:
            raise ValueError(f"Business name '{name}' already exists.")

        result = conn.execute(text('''
            UPDATE businesses
            SET name = :name, processing_percentage = :processing_percentage, updated_date = :updated_date
            WHERE id = :business_id
        '''), {
            "name": name,
            "processing_percentage": processing_percentage,
            "updated_date": current_time,
            "business_id": business_id,
        })
        if result.rowcount == 0:
            raise ValueError("Business no longer exists.")

    return business_id

def save_processing_history(business_id: int, date: str, income_amount: float, 
                          processing_amount: float, period_start: str, period_end: str):
    """Save processing history to database"""
    engine = get_database_engine()
    with engine.begin() as conn:
        conn.execute(text('''
            DELETE FROM advance_payments
            WHERE processing_history_id IN (
                SELECT id FROM processing_history
                WHERE business_id = :business_id AND date = :date
                  AND period_start = :period_start AND period_end = :period_end
            )
        '''), {
            "business_id": business_id,
            "date": date,
            "period_start": period_start,
            "period_end": period_end,
        })

        conn.execute(text('''
            DELETE FROM processing_history 
            WHERE business_id = :business_id AND date = :date
              AND period_start = :period_start AND period_end = :period_end
        '''), {
            "business_id": business_id,
            "date": date,
            "period_start": period_start,
            "period_end": period_end,
        })

        conn.execute(text('''
            INSERT INTO processing_history 
            (business_id, date, income_amount, processing_amount, period_start, period_end)
            VALUES (:business_id, :date, :income_amount, :processing_amount, :period_start, :period_end)
        '''), {
            "business_id": business_id,
            "date": date,
            "income_amount": income_amount,
            "processing_amount": processing_amount,
            "period_start": period_start,
            "period_end": period_end,
        })

        history_id = conn.execute(text('''
            SELECT id FROM processing_history
            WHERE business_id = :business_id AND date = :date
              AND period_start = :period_start AND period_end = :period_end
            ORDER BY id DESC
        '''), {
            "business_id": business_id,
            "date": date,
            "period_start": period_start,
            "period_end": period_end,
        }).fetchone()[0]

    return int(history_id)


def get_processing_history() -> pd.DataFrame:
    """Get processing history with business names."""
    engine = get_database_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text('''
            SELECT 
                h.date,
                b.name as business_name,
                h.income_amount,
                h.processing_amount,
                h.period_start,
                h.period_end,
                (h.processing_amount / h.income_amount * 100) as processing_percentage
            FROM processing_history h
            JOIN businesses b ON h.business_id = b.id
            ORDER BY h.date DESC, b.name
        '''), conn)


def get_processing_history_count() -> int:
    """Get the number of saved processing records."""
    engine = get_database_engine()
    with engine.connect() as conn:
        row = conn.execute(text('SELECT COUNT(*) as count FROM processing_history')).fetchone()
    return int(row[0] if row else 0)


def get_active_advance_for_business(business_id: int):
    """Return the active advance row for a business, if one exists."""
    engine = get_database_engine()
    with engine.connect() as conn:
        return conn.execute(text('''
            SELECT id, business_id, amount_loaned, factor_rate, split_percentage,
                   total_repayable, funded_date, status, notes
            FROM advances
            WHERE business_id = :business_id AND status = 'active'
            ORDER BY funded_date DESC, id DESC
        '''), {"business_id": business_id}).fetchone()


def create_advance(
    business_id: int,
    amount_loaned: float,
    factor_rate: float,
    split_percentage: float,
    funded_date: str,
    notes: str = "",
) -> int:
    """Create a new active MCA advance for a configured business."""
    if amount_loaned <= 0:
        raise ValueError("Amount loaned must be greater than zero.")
    if factor_rate <= 0:
        raise ValueError("Factor rate must be greater than zero.")
    if split_percentage < 0 or split_percentage > 100:
        raise ValueError("Split percentage must be between 0 and 100.")

    current_time = datetime.now().isoformat()
    total_repayable = round(float(amount_loaned) * float(factor_rate), 2)
    engine = get_database_engine()
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO advances (
                business_id, amount_loaned, factor_rate, split_percentage,
                total_repayable, funded_date, status, notes, created_date, updated_date
            )
            VALUES (
                :business_id, :amount_loaned, :factor_rate, :split_percentage,
                :total_repayable, :funded_date, 'active', :notes, :created_date, :updated_date
            )
        '''), {
            "business_id": business_id,
            "amount_loaned": float(amount_loaned),
            "factor_rate": float(factor_rate),
            "split_percentage": float(split_percentage),
            "total_repayable": total_repayable,
            "funded_date": funded_date,
            "notes": notes.strip(),
            "created_date": current_time,
            "updated_date": current_time,
        })
        advance_id = conn.execute(text('''
            SELECT id FROM advances
            WHERE business_id = :business_id AND created_date = :created_date
            ORDER BY id DESC
        '''), {
            "business_id": business_id,
            "created_date": current_time,
        }).fetchone()[0]

        conn.execute(text('''
            UPDATE businesses
            SET processing_percentage = :split_percentage, updated_date = :updated_date
            WHERE id = :business_id
        '''), {
            "split_percentage": float(split_percentage),
            "updated_date": current_time,
            "business_id": business_id,
        })

    return int(advance_id)


def get_advance_balances() -> pd.DataFrame:
    """Return advances with paid and remaining balance figures."""
    engine = get_database_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text('''
            SELECT
                a.id,
                a.business_id,
                b.name as business_name,
                a.amount_loaned,
                a.factor_rate,
                a.split_percentage,
                a.total_repayable,
                COALESCE(SUM(p.payment_amount), 0) as total_paid,
                CASE
                    WHEN a.total_repayable - COALESCE(SUM(p.payment_amount), 0) < 0 THEN 0
                    ELSE a.total_repayable - COALESCE(SUM(p.payment_amount), 0)
                END as balance_remaining,
                a.funded_date,
                a.status,
                a.notes
            FROM advances a
            JOIN businesses b ON a.business_id = b.id
            LEFT JOIN advance_payments p ON a.id = p.advance_id
            GROUP BY
                a.id, a.business_id, b.name, a.amount_loaned, a.factor_rate,
                a.split_percentage, a.total_repayable, a.funded_date, a.status, a.notes
            ORDER BY
                CASE WHEN a.status = 'active' THEN 0 ELSE 1 END,
                a.funded_date DESC,
                b.name
        '''), conn)


def get_payment_ledger() -> pd.DataFrame:
    """Return payment ledger entries with business and advance details."""
    engine = get_database_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text('''
            SELECT
                p.id,
                p.payment_date,
                b.name as business_name,
                p.payment_amount,
                p.source,
                p.notes,
                a.id as advance_id,
                a.total_repayable,
                a.status as advance_status,
                h.period_start,
                h.period_end
            FROM advance_payments p
            JOIN advances a ON p.advance_id = a.id
            JOIN businesses b ON p.business_id = b.id
            LEFT JOIN processing_history h ON p.processing_history_id = h.id
            ORDER BY p.payment_date DESC, p.id DESC
        '''), conn)


def refresh_advance_status(advance_id: int) -> None:
    """Mark an advance paid when payments meet or exceed total repayable."""
    current_time = datetime.now().isoformat()
    engine = get_database_engine()
    with engine.begin() as conn:
        row = conn.execute(text('''
            SELECT
                a.total_repayable,
                COALESCE(SUM(p.payment_amount), 0) as total_paid
            FROM advances a
            LEFT JOIN advance_payments p ON a.id = p.advance_id
            WHERE a.id = :advance_id
            GROUP BY a.id, a.total_repayable
        '''), {"advance_id": advance_id}).fetchone()

        if not row:
            return

        new_status = "paid" if float(row[1]) >= float(row[0]) else "active"
        conn.execute(text('''
            UPDATE advances
            SET status = :status, updated_date = :updated_date
            WHERE id = :advance_id
        '''), {
            "status": new_status,
            "updated_date": current_time,
            "advance_id": advance_id,
        })


def record_advance_payment(
    advance_id: int,
    business_id: int,
    payment_date: str,
    payment_amount: float,
    source: str,
    notes: str = "",
    processing_history_id: int | None = None,
) -> int:
    """Record a payment against an advance and refresh its balance status."""
    if payment_amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    current_time = datetime.now().isoformat()
    engine = get_database_engine()
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO advance_payments (
                advance_id, business_id, processing_history_id, payment_date,
                payment_amount, source, notes, created_date
            )
            VALUES (
                :advance_id, :business_id, :processing_history_id, :payment_date,
                :payment_amount, :source, :notes, :created_date
            )
        '''), {
            "advance_id": advance_id,
            "business_id": business_id,
            "processing_history_id": processing_history_id,
            "payment_date": payment_date,
            "payment_amount": float(payment_amount),
            "source": source,
            "notes": notes.strip(),
            "created_date": current_time,
        })
        payment_id = conn.execute(text('''
            SELECT id FROM advance_payments
            WHERE advance_id = :advance_id AND created_date = :created_date
            ORDER BY id DESC
        '''), {
            "advance_id": advance_id,
            "created_date": current_time,
        }).fetchone()[0]

    refresh_advance_status(advance_id)
    return int(payment_id)


def apply_processing_payment_to_active_advance(
    business_id: int,
    processing_history_id: int,
    payment_date: str,
    payment_amount: float,
    period_start: str,
    period_end: str,
) -> bool:
    """Apply a saved processing amount to the business's active advance."""
    active_advance = get_active_advance_for_business(business_id)
    if not active_advance or payment_amount <= 0:
        return False

    record_advance_payment(
        advance_id=int(active_advance._mapping["id"]),
        business_id=business_id,
        processing_history_id=processing_history_id,
        payment_date=payment_date,
        payment_amount=payment_amount,
        source="processing_run",
        notes=f"Auto-applied from processing period {period_start} to {period_end}",
    )
    return True

# MCA Sub-categorization using your business lending scorecard logic
MCA_CATEGORIES = [
    'Income',
    'Special Inflow', 
    'Transfer In',
    'Transfer Out',
    'Funding Inflow',
    'Loans',
    'Debt Repayments',
    'Expenses',
    'Special Outflow',
    'Bank Charge',
    'Failed Payment',
    'Uncategorised'
]

_TRANSACTION_CATEGORIZER = TransactionCategorizer()

def map_transaction_category(transaction):
    """Categorize a transaction using the local copy of MCAV2's engine."""
    category, _confidence = _TRANSACTION_CATEGORIZER.categorize_transaction(transaction)
    return category

def categorize_transaction(transaction_dict):
    """
    Wrapper function to categorize a single transaction using the MCAV2-derived logic.
    """
    category = map_transaction_category(transaction_dict)
    return category

def normalize_category_value(category_value):
    """Normalize category payloads from strings/lists into a readable string."""
    if isinstance(category_value, list):
        return ", ".join(map(str, category_value))
    if category_value is None:
        return ""
    return str(category_value)

def get_uploaded_files_signature(uploaded_files):
    """Create a stable signature for the current upload selection."""
    return tuple(
        (uploaded_file.name, getattr(uploaded_file, "size", None))
        for uploaded_file in uploaded_files
    )

def get_processing_inputs_signature(uploaded_files, business_name_mappings, start_date, end_date):
    """Create a signature for inputs that affect processed results."""
    return (
        get_uploaded_files_signature(uploaded_files),
        tuple(sorted((file_index, name.strip()) for file_index, name in business_name_mappings.items())),
        start_date.isoformat(),
        end_date.isoformat(),
    )

def clear_processing_results():
    """Clear cached processing results when uploads change or are removed."""
    for key in ("df", "business_mappings", "date_range", "upload_signature", "processing_inputs_signature"):
        st.session_state.pop(key, None)

def apply_professional_theme():
    """Apply a polished dark Streamlit theme."""
    st.markdown(
        """
        <style>
        :root {
            --bg: #0b0f17;
            --panel: #111827;
            --panel-soft: #151f2e;
            --line: #263244;
            --line-strong: #334155;
            --text: #e5e7eb;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --accent-strong: #0ea5e9;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
        }

        .stApp {
            background:
                radial-gradient(circle at 20% 0%, rgba(56, 189, 248, 0.12), transparent 28rem),
                linear-gradient(180deg, #0b0f17 0%, #0f172a 100%);
            color: var(--text);
        }

        .block-container {
            max-width: 1400px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        [data-testid="stSidebar"] {
            background: #090d14;
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] * {
            color: var(--text);
        }

        h1, h2, h3 {
            color: #f8fafc;
            letter-spacing: 0;
        }

        h1 {
            font-size: 2.1rem;
            font-weight: 750;
            margin-bottom: 0.2rem;
        }

        h2, h3 {
            font-weight: 680;
        }

        p, li, label, [data-testid="stCaptionContainer"] {
            color: var(--muted);
        }

        .app-kicker {
            color: var(--accent);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .app-subtitle {
            color: var(--muted);
            font-size: 1rem;
            margin-bottom: 1.4rem;
        }

        .section-panel {
            background: rgba(17, 24, 39, 0.72);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1rem 1.1rem;
            margin: 0.6rem 0 1rem 0;
        }

        .section-label {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.2rem;
        }

        .section-title {
            color: #f8fafc;
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }

        [data-testid="stMetric"] {
            background: rgba(17, 24, 39, 0.74);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0.95rem 1rem;
        }

        [data-testid="stMetricLabel"] p {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
        }

        [data-testid="stMetricValue"] {
            color: #f8fafc;
            font-weight: 750;
        }

        div[data-testid="stTabs"] button {
            color: var(--muted);
            border-radius: 8px 8px 0 0;
            font-weight: 650;
        }

        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #f8fafc;
            background: rgba(56, 189, 248, 0.10);
        }

        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            background-color: var(--accent);
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
            border: 1px solid var(--line-strong);
            background: #172033;
            color: #f8fafc;
            font-weight: 700;
            min-height: 2.7rem;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            border-color: var(--accent);
            color: #f8fafc;
            background: #1f2a44;
        }

        .stButton > button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {
            background: linear-gradient(135deg, var(--accent-strong), #2563eb);
            border-color: rgba(125, 211, 252, 0.7);
            box-shadow: 0 12px 28px rgba(14, 165, 233, 0.18);
        }

        [data-testid="stFileUploader"] {
            background: rgba(17, 24, 39, 0.72);
            border: 1px dashed var(--line-strong);
            border-radius: 8px;
            padding: 0.8rem;
        }

        [data-testid="stDataFrame"],
        [data-testid="stDataEditor"] {
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
        }

        div[data-baseweb="input"],
        div[data-baseweb="select"],
        textarea {
            background-color: #0f172a;
            border-color: var(--line-strong);
            border-radius: 8px;
        }

        .stAlert {
            border-radius: 8px;
            border: 1px solid var(--line);
        }

        hr {
            border-color: var(--line);
        }

        #MainMenu,
        footer,
        header[data-testid="stHeader"] {
            visibility: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_section_intro(label: str, title: str, description: str):
    """Render a compact section heading."""
    st.markdown(
        f"""
        <div class="section-panel">
            <div class="section-label">{label}</div>
            <div class="section-title">{title}</div>
            <div class="app-subtitle" style="margin-bottom: 0;">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def calculate_business_summary(df: pd.DataFrame, business_percentages: dict) -> pd.DataFrame:
    """Summarize income and processing totals by business."""
    income_df = df[df['is_revenue'] == True].copy()
    if income_df.empty:
        return pd.DataFrame()

    business_summary = income_df.groupby('business_name').agg({
        'amount': lambda x: abs(pd.to_numeric(x, errors='coerce')).sum(),
        'transaction_id': 'count'
    }).round(2)
    business_summary.columns = ['Total Income', 'Transaction Count']
    business_summary['Processing %'] = business_summary.index.map(
        lambda x: business_percentages.get(x, 0.0)
    )
    business_summary['Amount to Process'] = (
        business_summary['Total Income'] * business_summary['Processing %'] / 100
    ).round(2)

    return business_summary

def render_processing_results(df: pd.DataFrame, start_date: date, end_date: date):
    """Render processing outputs from cached session state results."""
    businesses_df = get_all_businesses()
    business_percentages = dict(zip(businesses_df['name'], businesses_df['processing_percentage']))

    render_section_intro(
        "Results",
        "Income Analysis & Processing Calculations",
        "Review the processing totals, inspect daily movement, then save or export the figures."
    )

    income_df = df[df['is_revenue'] == True].copy()
    business_summary = calculate_business_summary(df, business_percentages)

    if not business_summary.empty:
        st.dataframe(
            business_summary.style.format({
                'Total Income': '£{:,.2f}',
                'Amount to Process': '£{:,.2f}',
                'Processing %': '{:.1f}%'
            }),
            use_container_width=True
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Businesses", len(business_summary))
        with col2:
            total_income = business_summary['Total Income'].sum()
            st.metric("Total Income", f"£{total_income:,.2f}")
        with col3:
            total_processing = business_summary['Amount to Process'].sum()
            st.metric("Total to Process", f"£{total_processing:,.2f}")
        with col4:
            avg_percentage = business_summary['Processing %'].mean()
            st.metric("Avg Processing %", f"{avg_percentage:.1f}%")

        if st.button("💾 Save Processing Calculations", type="secondary", key="save_processing_calculations"):
            period_start = start_date.isoformat()
            period_end = end_date.isoformat()
            applied_payment_count = 0

            for business_name, row in business_summary.iterrows():
                business_id = add_or_update_business(business_name, row['Processing %'])
                history_id = save_processing_history(
                    business_id=business_id,
                    date=date.today().isoformat(),
                    income_amount=row['Total Income'],
                    processing_amount=row['Amount to Process'],
                    period_start=period_start,
                    period_end=period_end
                )

                if apply_processing_payment_to_active_advance(
                    business_id=business_id,
                    processing_history_id=history_id,
                    payment_date=date.today().isoformat(),
                    payment_amount=row['Amount to Process'],
                    period_start=period_start,
                    period_end=period_end,
                ):
                    applied_payment_count += 1

            if applied_payment_count:
                st.success(
                    f"Processing calculations saved. {applied_payment_count} payment(s) were applied to active advance balances."
                )
            else:
                st.success("Processing calculations saved to database.")
                st.info("No active advances were found, so no balances were reduced.")

        if st.checkbox("📊 Show Daily Breakdown", key="show_daily_breakdown"):
            render_section_intro(
                "Breakdown",
                "Daily Income Breakdown",
                "Amounts to process by business and transaction date."
            )

            income_df['date'] = pd.to_datetime(income_df['date']).dt.date
            daily_breakdown = income_df.groupby(['business_name', 'date']).agg({
                'amount': lambda x: abs(pd.to_numeric(x, errors='coerce')).sum()
            }).round(2)
            daily_breakdown.columns = ['Daily Income']

            daily_breakdown = daily_breakdown.reset_index()
            daily_breakdown['Processing %'] = daily_breakdown['business_name'].map(
                lambda x: business_percentages.get(x, 0.0)
            )
            daily_breakdown['Amount to Process'] = (
                daily_breakdown['Daily Income'] * daily_breakdown['Processing %'] / 100
            ).round(2)

            daily_pivot = daily_breakdown.pivot(
                index='date',
                columns='business_name',
                values='Amount to Process'
            ).fillna(0)

            st.dataframe(
                daily_pivot.style.format('£{:,.2f}'),
                use_container_width=True
            )

        st.subheader("📤 Export Options")
        col1, col2 = st.columns(2)

        with col1:
            summary_csv = business_summary.to_csv()
            st.download_button(
                label="📊 Business Summary CSV",
                data=summary_csv,
                file_name=f"business_summary_{start_date}_{end_date}.csv",
                mime="text/csv",
                key="direct_summary_download"
            )

        with col2:
            transactions_export_df = income_df[[
                'business_name', 'date', 'name', 'amount', 'mca_subcategory',
                'account_name', 'transaction_id', 'merchant_name'
            ]].copy()
            transactions_csv = transactions_export_df.to_csv(index=False)
            st.download_button(
                label="📋 Income Transactions CSV",
                data=transactions_csv,
                file_name=f"income_transactions_{start_date}_{end_date}.csv",
                mime="text/csv",
                key="direct_transactions_download"
            )
    else:
        st.warning("No income transactions found in the selected time period.")

    unique_businesses = set(df['business_name'].unique())
    configured_businesses = set(business_percentages.keys())
    unconfigured = unique_businesses - configured_businesses

    if unconfigured:
        st.warning(f"⚠️ The following businesses need processing percentages configured: {', '.join(unconfigured)}")
        st.info("💡 Go to the **Business Management** tab to set processing percentages.")

def process_multiple_json_files(uploaded_files, business_name_mappings, start_date=None, end_date=None):
    """
    Process multiple JSON files with business name mappings from JSON content
    """
    all_business_data = []
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            # Get the business name from the mapping
            business_name = business_name_mappings.get(i, f"Unknown Business {i+1}")
            
            # Load JSON data
            uploaded_file.seek(0)  # Reset file pointer
            json_data = json.load(uploaded_file)
            accounts = json_data.get('accounts', [])
            transactions = json_data.get('transactions', [])

            # Filter by date if specified
            if start_date and end_date:
                filtered_transactions = []
                for txn in transactions:
                    try:
                        txn_date = pd.to_datetime(txn.get('date')).date()
                        if start_date <= txn_date <= end_date:
                            filtered_transactions.append(txn)
                    except Exception as e:
                        st.warning(f"Skipping transaction due to invalid date: {txn.get('date')} ({e})")
                transactions = filtered_transactions

            # Create routing data
            routing_data = {}
            for acct in accounts:
                acct_id = acct.get('account_id')
                if not acct_id:
                    st.warning(f"Skipping malformed account in {uploaded_file.name}: missing account_id")
                    continue
                routing_data[acct_id] = {
                    'sort_code': acct.get('sort_code', 'N/A'),
                    'account_number': acct.get('account', 'N/A'),
                    'account_name': acct.get('name', 'Unnamed Account')
                }

            # Process transactions
            for txn in transactions:
                try:
                    acct_id = txn.get('account_id', 'unknown')
                    route_info = routing_data.get(acct_id, {})
                    amount = pd.to_numeric(txn.get('amount'), errors='coerce')
                    if pd.isna(amount):
                        raise ValueError("missing or invalid amount")
                    normalized_txn = dict(txn)
                    normalized_txn['amount'] = float(amount)
                    
                    # Apply the local copy of MCAV2's MCA categorization logic
                    mca_subcategory = categorize_transaction(normalized_txn)
                    
                    # Determine flags based on subcategory
                    is_revenue = mca_subcategory == 'Income'
                    is_special_inflow = mca_subcategory == 'Special Inflow'
                    is_expense = mca_subcategory in ['Expenses', 'Special Outflow', 'Bank Charge']
                    is_debt_repayment = mca_subcategory in ['Debt Repayments']
                    is_debt = mca_subcategory in ['Loans']
                    is_failed_payment = mca_subcategory == 'Failed Payment'
                    is_transfer_in = mca_subcategory == 'Transfer In'
                    is_transfer_out = mca_subcategory == 'Transfer Out'
                    is_internal_transfer = is_transfer_in or is_transfer_out
                    is_funding_injection = mca_subcategory == 'Funding Inflow'
                    is_bank_charge = mca_subcategory == 'Bank Charge'
                    
                    all_business_data.append({
                        'business_name': business_name,
                        'filename': uploaded_file.name,
                        'transaction_id': txn.get('transaction_id', f"txn_{len(all_business_data)}"),
                        'date': txn.get('date'),
                        'name': txn.get('name', 'Unknown Transaction'),
                        'merchant_name': txn.get('merchant_name', ''),
                        'amount': float(amount),
                        'original_category': normalize_category_value(txn.get('category')),
                        'personal_finance_category.detailed': txn.get('personal_finance_category.detailed', ''),
                        'mca_subcategory': mca_subcategory,
                        'account_id': acct_id,
                        'is_authorised_account': acct_id in routing_data,
                        'sort_code': route_info.get('sort_code', 'N/A'),
                        'account_number': route_info.get('account_number', 'N/A'),
                        'account_name': route_info.get('account_name', 'Unnamed Account'),
                        'is_revenue': is_revenue,
                        'is_special_inflow': is_special_inflow,
                        'is_expense': is_expense,
                        'is_debt_repayment': is_debt_repayment,
                        'is_debt': is_debt,
                        'is_failed_payment': is_failed_payment,
                        'is_transfer_in': is_transfer_in,
                        'is_transfer_out': is_transfer_out,
                        'is_internal_transfer': is_internal_transfer,
                        'is_funding_injection': is_funding_injection,
                        'is_bank_charge': is_bank_charge,
                        'selected': True
                    })
                except Exception as txn_error:
                    st.warning(f"Skipping malformed transaction in {uploaded_file.name}: {txn_error}")

        except Exception as e:
            st.error(f"Failed to process {uploaded_file.name}: {str(e)}")

    return pd.DataFrame(all_business_data)

def business_management_tab():
    """Business management interface"""
    render_section_intro(
        "Configuration",
        "Business Management",
        "Maintain configured businesses and processing percentages."
    )
    
    businesses_df = get_all_businesses()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Configured Businesses")
        if not businesses_df.empty:
            edited_df = st.data_editor(
                businesses_df[['id', 'name', 'processing_percentage']],
                column_config={
                    "id": None,
                    "name": "Business Name",
                    "processing_percentage": st.column_config.NumberColumn(
                        "Processing %",
                        help="Percentage of income to process",
                        min_value=0.0,
                        max_value=100.0,
                        step=0.1,
                        format="%.1f%%"
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="business_editor"
            )
            
            if st.button("Save Changes", type="primary"):
                try:
                    seen_names = set()
                    for _, row in edited_df.iterrows():
                        business_name = str(row['name']).strip()
                        normalized_name = business_name.lower()
                        if not business_name:
                            raise ValueError("Business names cannot be blank.")
                        if normalized_name in seen_names:
                            raise ValueError(f"Duplicate business name in editor: '{business_name}'.")
                        seen_names.add(normalized_name)

                    for _, row in edited_df.iterrows():
                        update_business_by_id(int(row['id']), str(row['name']).strip(), float(row['processing_percentage']))
                    st.success("Business settings updated!")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        else:
            st.info("No businesses configured yet. Add your first business below.")
    
    with col2:
        st.subheader("Add New Business")
        with st.form("add_business"):
            new_business_name = st.text_input("Business Name")
            new_processing_percentage = st.number_input(
                "Processing Percentage", 
                min_value=0.0, 
                max_value=100.0, 
                step=0.1,
                format="%.1f"
            )
            
            if st.form_submit_button("Add Business"):
                if new_business_name.strip():
                    add_or_update_business(new_business_name.strip(), new_processing_percentage)
                    st.success(f"Added {new_business_name} with {new_processing_percentage}% processing rate")
                    st.rerun()
                else:
                    st.error("Please enter a business name")

        st.subheader("Backup / Restore")
        backup_rows = []
        if not businesses_df.empty:
            backup_rows = businesses_df[["name", "processing_percentage"]].to_dict(orient="records")

        st.download_button(
            label="Download Businesses Backup",
            data=json.dumps({"businesses": backup_rows}, indent=2),
            file_name=f"businesses_backup_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            disabled=not backup_rows,
            help="Use this as a quick restore file if Streamlit Cloud ever resets its local database."
        )

        restore_file = st.file_uploader(
            "Restore Businesses Backup",
            type=["json"],
            key="businesses_restore_upload",
            help="Upload a businesses backup JSON exported from this app."
        )

        if restore_file is not None and st.button("Restore Businesses"):
            try:
                restored_businesses = _normalise_seed_businesses(json.load(restore_file))
                if not restored_businesses:
                    raise ValueError("No valid businesses found in the uploaded backup.")

                for business in restored_businesses:
                    add_or_update_business(business["name"], business["processing_percentage"])

                st.success(f"Restored {len(restored_businesses)} businesses.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not restore businesses backup: {error}")

def extract_business_name_from_json(json_data, filename=""):
    """Extract business name from JSON account data with multi-account handling"""
    accounts = json_data.get('accounts', [])
    filename_business_name = extract_business_name_from_filename(filename) if filename else ""
    
    if not accounts:
        fallback_name = filename_business_name or f"Unknown Business ({filename})"
        return fallback_name, [], {}
    
    # Get all unique account names with their details
    account_info = {}
    for account in accounts:
        account_id = account.get('account_id', '')
        account_name = account.get('name', 'Unknown Account')
        account_type = account.get('type', '')
        account_subtype = account.get('subtype', '')
        
        if account_name not in account_info:
            account_info[account_name] = {
                'name': account_name,
                'type': account_type,
                'subtype': account_subtype,
                'count': 1,
                'account_ids': [account_id]
            }
        else:
            account_info[account_name]['count'] += 1
            account_info[account_name]['account_ids'].append(account_id)
    
    account_names = list(account_info.keys())
    
    if len(account_names) == 1:
        # Single account - use it directly after cleaning
        return clean_account_name(account_names[0]), account_names, account_info
    else:
        # Multiple accounts often contain generic labels like "Savings" or
        # "CurrentAccount 1234", so prefer the upload filename as the default.
        extracted_name = filename_business_name or clean_account_name(account_names[0])
        account_options = [extracted_name] + [name for name in account_names if name != extracted_name]
        return extracted_name, account_options, account_info

def create_business_name_mapping_interface(business_extractions):
    """Create enhanced business name mapping interface with existing business dropdown"""
    
    render_section_intro(
        "Step 2",
        "Confirm Business Mapping",
        "Match each upload to the business name used for processing rates and reporting."
    )
    
    # Get existing businesses for dropdown
    existing_businesses_df = get_all_businesses()
    existing_business_names = [""] + list(existing_businesses_df['name'].tolist()) if not existing_businesses_df.empty else [""]
    
    business_name_mappings = {}
    
    for extraction in business_extractions:
        st.divider()
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown(f"**📁 File:** `{extraction['filename']}`")
            
            # Show account information
            if extraction['has_multiple_accounts']:
                st.info(f"🏢 **{len(extraction['account_options'])} accounts found**")
            else:
                st.success("✅ **Single account**")
            
            # Show account details
            account_info = extraction.get('account_info', {})
            if account_info:
                with st.expander("View Account Details"):
                    for acc_name, acc_details in account_info.items():
                        st.text(f"• {acc_name}")
                        if acc_details.get('type'):
                            st.text(f"  Type: {acc_details['type']}")
                        if acc_details.get('subtype'):
                            st.text(f"  Subtype: {acc_details['subtype']}")
        
        with col2:
            st.markdown(f"**🏢 Business Name Configuration**")
            
            # Method selection - updated options
            mapping_method = st.radio(
                "How would you like to set the business name?",
                ["Use extracted name", "Choose from account names", "Select existing business", "Enter manually"],
                key=f"method_{extraction['file_index']}",
                horizontal=False
            )
            
            if mapping_method == "Use extracted name":
                # Use the automatically extracted and cleaned name
                business_name = extraction['extracted_name']
                
                # Show what was extracted and allow editing
                final_business_name = st.text_input(
                    "Extracted Business Name (edit if needed):",
                    value=business_name,
                    key=f"extracted_name_{extraction['file_index']}",
                    help="This name was automatically extracted and cleaned from the account name"
                )
                
            elif mapping_method == "Choose from account names":
                # Let user choose from available account names
                selected_account = st.selectbox(
                    "Choose which account name represents your business:",
                    extraction['account_options'],
                    key=f"account_select_{extraction['file_index']}",
                    help="Select the account name that best represents your business"
                )
                
                # Clean the selected account name
                cleaned_name = clean_account_name(selected_account)
                
                # Allow further editing of the cleaned name
                final_business_name = st.text_input(
                    "Business Name (cleaned, edit if needed):",
                    value=cleaned_name,
                    key=f"cleaned_name_{extraction['file_index']}",
                    help=f"Cleaned version of '{selected_account}' - edit if needed"
                )
            
            elif mapping_method == "Select existing business":
                # Dropdown of existing businesses
                if len(existing_business_names) > 1:
                    selected_existing = st.selectbox(
                        "Choose from existing businesses:",
                        existing_business_names,
                        key=f"existing_select_{extraction['file_index']}",
                        help="Select a business that's already configured in Business Management"
                    )
                    
                    final_business_name = selected_existing if selected_existing else ""
                    
                    if not selected_existing:
                        st.info("Please select a business from the dropdown")
                    else:
                        st.success(f"✅ Selected: {selected_existing}")
                else:
                    st.warning("No existing businesses found. Go to Business Management tab to add businesses first.")
                    final_business_name = ""
                
            else:  # Enter manually
                # Manual entry with suggestions
                final_business_name = st.text_input(
                    "Enter Business Name Manually:",
                    value="",
                    key=f"manual_name_{extraction['file_index']}",
                    help="Enter the exact business name you want to use"
                )
                
                # Show suggestions based on account names
                if extraction['account_options']:
                    st.markdown("**💡 Quick suggestions:**")
                    suggestion_cols = st.columns(min(len(extraction['account_options']), 3))
                    for idx, account_name in enumerate(extraction['account_options'][:3]):  # Limit to 3 suggestions
                        with suggestion_cols[idx % 3]:
                            cleaned_suggestion = clean_account_name(account_name)
                            if st.button(f"Use: {cleaned_suggestion}", key=f"suggest_{extraction['file_index']}_{idx}"):
                                st.session_state[f"manual_name_{extraction['file_index']}"] = cleaned_suggestion
                                st.rerun()
            
            business_name_mappings[extraction['file_index']] = final_business_name
            
            # Show preview of final name
            if final_business_name and final_business_name.strip():
                st.success(f"✅ **Final Business Name:** `{final_business_name}`")
                
                # Show if this business exists in the system
                if final_business_name in existing_business_names[1:]:  # Exclude empty string
                    business_percentage = existing_businesses_df[existing_businesses_df['name'] == final_business_name]['processing_percentage'].iloc[0]
                    st.info(f"📊 **Processing Rate:** {business_percentage}% (configured)")
                else:
                    st.warning("⚠️ **New Business** - configure processing percentage in Business Management tab")
            else:
                st.error("⚠️ Please enter a business name")
    
    return business_name_mappings

def processing_analysis_tab():
    """Main processing and analysis interface with enhanced JSON content extraction"""
    render_section_intro(
        "Step 1",
        "Transaction Upload",
        "Upload one or more JSON transaction files. Business names are extracted from account data."
    )
    
    uploaded_files = st.file_uploader(
        "Upload Business Transaction JSON Files", 
        type=['json'],
        accept_multiple_files=True,
        help="Select multiple JSON files - business names will be extracted from account data within each file."
    )

    if not uploaded_files:
        clear_processing_results()
        st.info("Upload JSON files to begin processing.")

        col1, col2 = st.columns(2)
        with col1:
            render_section_intro(
                "Workflow",
                "Upload, Map, Process",
                "Add files, confirm each business name, choose a period, then calculate processing totals."
            )
        with col2:
            render_section_intro(
                "Extraction",
                "Account Names Are Cleaned",
                "`ABC Ltd Current Account` becomes `ABC Ltd`; manual edits are available before processing."
            )

        with st.expander("📚 MCA Categories Reference"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**💰 Revenue Categories:**")
                st.markdown("• Income")

                st.markdown("**↔️ Transfer/Funding Categories:**")
                st.markdown("• Special Inflow")
                st.markdown("• Transfer In")
                st.markdown("• Transfer Out")
                st.markdown("• Funding Inflow")

                st.markdown("**💳 Debt/Financing Categories:**") 
                st.markdown("• Loans")
                st.markdown("• Debt Repayments")
            
            with col2:
                st.markdown("**💸 Expense Categories:**")
                st.markdown("• Expenses")
                st.markdown("• Special Outflow")
                st.markdown("• Bank Charge")
                
                st.markdown("**❌ Other Categories:**")
                st.markdown("• Failed Payment")
                st.markdown("• Uncategorised")
        return

    current_signature = get_uploaded_files_signature(uploaded_files)
    if st.session_state.get('upload_signature') not in (None, current_signature):
        clear_processing_results()

    business_extractions = []
    for i, file in enumerate(uploaded_files):
        try:
            file.seek(0)
            json_data = json.load(file)
            file.seek(0)

            extracted_name, account_options, account_info = extract_business_name_from_json(json_data, file.name)

            business_extractions.append({
                'file_index': i,
                'filename': file.name,
                'extracted_name': extracted_name,
                'account_options': account_options,
                'account_info': account_info,
                'has_multiple_accounts': len(account_options) > 1
            })
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")
            fallback_name = extract_business_name_from_filename(file.name)
            business_extractions.append({
                'file_index': i,
                'filename': file.name,
                'extracted_name': fallback_name,
                'account_options': [fallback_name],
                'account_info': {},
                'has_multiple_accounts': False
            })

    business_name_mappings = create_business_name_mapping_interface(business_extractions)

    render_section_intro(
        "Step 3",
        "Mapping Summary",
        "Confirm all files are ready before selecting the processing period."
    )
    mapping_data = []
    all_names_valid = True

    for i in range(len(uploaded_files)):
        business_name = business_name_mappings.get(i, "")
        if not business_name.strip():
            all_names_valid = False

        mapping_data.append({
            'File': business_extractions[i]['filename'], 
            'Business Name': business_name,
            'Status': '✅ Ready' if business_name.strip() else '⚠️ Missing Name'
        })

    mapping_df = pd.DataFrame(mapping_data)
    st.dataframe(mapping_df, use_container_width=True)

    if not all_names_valid:
        st.warning("⚠️ Please ensure all business names are filled in before processing.")
        clear_processing_results()
        return

    render_section_intro(
        "Step 4",
        "Processing Period",
        "Choose the transaction window to include in this run."
    )

    period_type = st.selectbox(
        "Period Type",
        ["Today", "This Week", "This Month", "Last 30 Days", "Custom Range"]
    )

    if period_type == "Custom Range":
        st.markdown("**Custom Date Range:**")
        col1, col2 = st.columns(2)

        with col1:
            start_date_str = st.text_input(
                "Start Date (YYYY-MM-DD)",
                value=date.today().replace(month=1, day=1).strftime("%Y-%m-%d"),
                help="Enter date in YYYY-MM-DD format"
            )
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                st.error("Invalid start date format. Use YYYY-MM-DD")
                clear_processing_results()
                return

        with col2:
            end_date_str = st.text_input(
                "End Date (YYYY-MM-DD)",
                value=date.today().strftime("%Y-%m-%d"),
                help="Enter date in YYYY-MM-DD format"
            )
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                st.error("Invalid end date format. Use YYYY-MM-DD")
                clear_processing_results()
                return
    elif period_type == "Today":
        start_date = end_date = date.today()
    elif period_type == "This Week":
        today = date.today()
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period_type == "This Month":
        today = date.today()
        start_date = today.replace(day=1)
        end_date = today
    elif period_type == "Last 30 Days":
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

    if start_date > end_date:
        st.error("Start date must be before end date")
        clear_processing_results()
        return

    processing_inputs_signature = get_processing_inputs_signature(
        uploaded_files,
        business_name_mappings,
        start_date,
        end_date
    )
    if st.session_state.get('processing_inputs_signature') not in (None, processing_inputs_signature):
        clear_processing_results()

    if st.button("🚀 Process All Files", type="primary"):
        with st.spinner("Processing transaction files..."):
            df = process_multiple_json_files(uploaded_files, business_name_mappings, start_date, end_date)

        if not df.empty:
            st.session_state.df = df.copy()
            st.session_state.business_mappings = business_name_mappings
            st.session_state.date_range = (start_date.isoformat(), end_date.isoformat())
            st.session_state.upload_signature = current_signature
            st.session_state.processing_inputs_signature = processing_inputs_signature
        else:
            clear_processing_results()
            st.error("No valid transaction data found in uploaded files.")

    stored_range = st.session_state.get('date_range')
    stored_df = st.session_state.get('df')
    if (
        stored_df is not None
        and stored_range
        and st.session_state.get('processing_inputs_signature') == processing_inputs_signature
    ):
        saved_start = datetime.strptime(stored_range[0], "%Y-%m-%d").date()
        saved_end = datetime.strptime(stored_range[1], "%Y-%m-%d").date()
        render_processing_results(stored_df, saved_start, saved_end)

def processing_history_tab():
    """View processing history and MCA advance repayment balances."""
    render_section_intro(
        "Ledger",
        "Advances, Payments & Processing History",
        "Configure funded advances, apply processed payments, and review saved calculation history."
    )

    advance_tab, ledger_tab, history_tab = st.tabs([
        "Advance Setup",
        "Balances & Payments",
        "Processing History",
    ])

    with advance_tab:
        businesses_df = get_all_businesses()

        if businesses_df.empty:
            st.info("Add configured businesses in Business Management before creating an advance.")
        else:
            st.subheader("Create MCA Advance")
            st.caption("The split percentage is also saved as the company's processing percentage.")

            business_options = dict(zip(businesses_df['name'], businesses_df['id']))
            selected_business = st.selectbox(
                "Configured Company",
                list(business_options.keys()),
                key="advance_business_select",
            )

            current_split = float(
                businesses_df.loc[
                    businesses_df['name'] == selected_business,
                    'processing_percentage'
                ].iloc[0]
            )

            with st.form("advance_setup_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    amount_loaned = st.number_input(
                        "Amount Loaned",
                        min_value=0.0,
                        step=100.0,
                        format="%.2f",
                        key="advance_amount_loaned",
                    )
                with col2:
                    factor_rate = st.number_input(
                        "Factor Rate Charged",
                        min_value=0.0,
                        value=1.30,
                        step=0.01,
                        format="%.2f",
                        key="advance_factor_rate",
                    )
                with col3:
                    split_percentage = st.number_input(
                        "% Split",
                        min_value=0.0,
                        max_value=100.0,
                        value=current_split,
                        step=0.1,
                        format="%.1f",
                        key="advance_split_percentage",
                    )

                funded_date = st.date_input(
                    "Funded Date",
                    value=date.today(),
                    key="advance_funded_date",
                )
                notes = st.text_area(
                    "Notes",
                    placeholder="Optional reference, deal ID, or underwriting note",
                    key="advance_notes",
                )

                total_repayable = amount_loaned * factor_rate
                st.metric("Total Repayable", f"£{total_repayable:,.2f}")

                submitted = st.form_submit_button("Create Advance", type="primary")
                if submitted:
                    try:
                        create_advance(
                            business_id=int(business_options[selected_business]),
                            amount_loaned=amount_loaned,
                            factor_rate=factor_rate,
                            split_percentage=split_percentage,
                            funded_date=funded_date.isoformat(),
                            notes=notes,
                        )
                        st.success(f"Advance created for {selected_business}.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

            balances_df = get_advance_balances()
            if not balances_df.empty:
                st.subheader("Existing Advances")
                display_balances = balances_df.copy()
                for column in ["amount_loaned", "total_repayable", "total_paid", "balance_remaining"]:
                    display_balances[column] = display_balances[column].apply(lambda value: f"£{value:,.2f}")
                display_balances["factor_rate"] = display_balances["factor_rate"].apply(lambda value: f"{value:.2f}x")
                display_balances["split_percentage"] = display_balances["split_percentage"].apply(lambda value: f"{value:.1f}%")

                st.dataframe(
                    display_balances[[
                        "business_name", "amount_loaned", "factor_rate", "split_percentage",
                        "total_repayable", "total_paid", "balance_remaining", "funded_date", "status"
                    ]],
                    column_config={
                        "business_name": "Business",
                        "amount_loaned": "Amount Loaned",
                        "factor_rate": "Factor Rate",
                        "split_percentage": "Split",
                        "total_repayable": "Total Repayable",
                        "total_paid": "Paid",
                        "balance_remaining": "Balance",
                        "funded_date": "Funded Date",
                        "status": "Status",
                    },
                    use_container_width=True,
                )

    with ledger_tab:
        balances_df = get_advance_balances()
        payment_df = get_payment_ledger()

        if balances_df.empty:
            st.info("No advances have been created yet.")
        else:
            active_balances = balances_df[balances_df["status"] == "active"].copy()
            total_repayable = balances_df["total_repayable"].sum()
            total_paid = balances_df["total_paid"].sum()
            total_balance = balances_df["balance_remaining"].sum()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Repayable", f"£{total_repayable:,.2f}")
            with col2:
                st.metric("Total Paid", f"£{total_paid:,.2f}")
            with col3:
                st.metric("Outstanding Balance", f"£{total_balance:,.2f}")

            st.subheader("Running Balances")
            display_balances = balances_df.copy()
            for column in ["amount_loaned", "total_repayable", "total_paid", "balance_remaining"]:
                display_balances[column] = display_balances[column].apply(lambda value: f"£{value:,.2f}")
            display_balances["factor_rate"] = display_balances["factor_rate"].apply(lambda value: f"{value:.2f}x")
            display_balances["split_percentage"] = display_balances["split_percentage"].apply(lambda value: f"{value:.1f}%")

            st.dataframe(
                display_balances[[
                    "business_name", "status", "amount_loaned", "factor_rate", "split_percentage",
                    "total_repayable", "total_paid", "balance_remaining", "funded_date"
                ]],
                column_config={
                    "business_name": "Business",
                    "status": "Status",
                    "amount_loaned": "Amount Loaned",
                    "factor_rate": "Factor Rate",
                    "split_percentage": "Split",
                    "total_repayable": "Total Repayable",
                    "total_paid": "Paid",
                    "balance_remaining": "Balance",
                    "funded_date": "Funded Date",
                },
                use_container_width=True,
            )

            with st.expander("Log Manual Payment"):
                if active_balances.empty:
                    st.info("There are no active advances available for manual payment logging.")
                else:
                    active_options = {
                        f"{row.business_name} - balance £{row.balance_remaining:,.2f}": row
                        for row in active_balances.itertuples(index=False)
                    }
                    with st.form("manual_payment_form"):
                        selected_advance_label = st.selectbox(
                            "Active Advance",
                            list(active_options.keys()),
                            key="manual_payment_advance",
                        )
                        selected_advance = active_options[selected_advance_label]
                        col1, col2 = st.columns(2)
                        with col1:
                            payment_date = st.date_input(
                                "Payment Date",
                                value=date.today(),
                                key="manual_payment_date",
                            )
                        with col2:
                            payment_amount = st.number_input(
                                "Payment Amount",
                                min_value=0.0,
                                step=10.0,
                                format="%.2f",
                                key="manual_payment_amount",
                            )
                        notes = st.text_input(
                            "Notes",
                            placeholder="Optional payment reference",
                            key="manual_payment_notes",
                        )
                        submitted = st.form_submit_button("Log Payment", type="primary")
                        if submitted:
                            try:
                                record_advance_payment(
                                    advance_id=int(selected_advance.id),
                                    business_id=int(selected_advance.business_id),
                                    payment_date=payment_date.isoformat(),
                                    payment_amount=payment_amount,
                                    source="manual",
                                    notes=notes,
                                )
                                st.success("Payment logged and balance updated.")
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))

        if not payment_df.empty:
            st.subheader("Payment Ledger")
            display_payments = payment_df.copy()
            display_payments["payment_amount"] = display_payments["payment_amount"].apply(lambda value: f"£{value:,.2f}")
            display_payments["total_repayable"] = display_payments["total_repayable"].apply(lambda value: f"£{value:,.2f}")
            st.dataframe(
                display_payments[[
                    "payment_date", "business_name", "payment_amount", "source",
                    "period_start", "period_end", "advance_status", "notes"
                ]],
                column_config={
                    "payment_date": "Payment Date",
                    "business_name": "Business",
                    "payment_amount": "Payment Amount",
                    "source": "Source",
                    "period_start": "Period Start",
                    "period_end": "Period End",
                    "advance_status": "Advance Status",
                    "notes": "Notes",
                },
                use_container_width=True,
            )

            st.download_button(
                label="Download Payment Ledger CSV",
                data=payment_df.to_csv(index=False),
                file_name=f"payment_ledger_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info("No payments have been logged yet.")
    
    with history_tab:
        history_df = get_processing_history()
    
        if not history_df.empty:
            # Format for display
            display_df = history_df.copy()
            display_df['income_amount'] = display_df['income_amount'].apply(lambda x: f"£{x:,.2f}")
            display_df['processing_amount'] = display_df['processing_amount'].apply(lambda x: f"£{x:,.2f}")
            display_df['processing_percentage'] = display_df['processing_percentage'].apply(lambda x: f"{x:.1f}%")

            st.dataframe(
                display_df[['date', 'business_name', 'income_amount', 'processing_amount', 'processing_percentage', 'period_start', 'period_end']],
                column_config={
                    'date': 'Processing Date',
                    'business_name': 'Business',
                    'income_amount': 'Income Amount',
                    'processing_amount': 'Processing Amount',
                    'processing_percentage': 'Processing %',
                    'period_start': 'Period Start',
                    'period_end': 'Period End'
                },
                use_container_width=True
            )

            # Summary statistics
            st.subheader("History Summary")
            col1, col2, col3 = st.columns(3)

            with col1:
                total_income = history_df['income_amount'].sum()
                st.metric("Total Income Processed", f"£{total_income:,.2f}")

            with col2:
                total_processing = history_df['processing_amount'].sum()
                st.metric("Total Amount Processed", f"£{total_processing:,.2f}")

            with col3:
                unique_businesses = history_df['business_name'].nunique()
                st.metric("Businesses Tracked", unique_businesses)

            # Export history
            csv_data = history_df.to_csv(index=False)
            st.download_button(
                label="Download History CSV",
                data=csv_data,
                file_name=f"processing_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No processing history found. Process some transactions first!")

def main():
    """
    Main Streamlit application
    """
    st.set_page_config(
        page_title="MCA Multi-Business Processing Tool",
        page_icon="M",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    apply_professional_theme()

    # Initialize database
    init_database()
    
    st.markdown('<div class="app-kicker">Merchant Cash Advance</div>', unsafe_allow_html=True)
    st.title("MCA Processing Console")
    st.markdown(
        '<div class="app-subtitle">Process multi-business transaction files, calculate repayment amounts, and keep a clean audit trail.</div>',
        unsafe_allow_html=True
    )

    try:
        businesses_df = get_all_businesses()
        history_count = get_processing_history_count()

        stat1, stat2, stat3 = st.columns(3)
        with stat1:
            st.metric("Configured Businesses", len(businesses_df))
        with stat2:
            avg_rate = businesses_df['processing_percentage'].mean() if not businesses_df.empty else 0.0
            st.metric("Average Processing Rate", f"{avg_rate:.1f}%")
        with stat3:
            st.metric("Saved Processing Records", int(history_count))
    except Exception:
        pass
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Processing & Analysis", "Business Management", "Processing History"])
    
    with tab1:
        processing_analysis_tab()
    
    with tab2:
        business_management_tab()
    
    with tab3:
        processing_history_tab()
    
    # Sidebar info
    with st.sidebar:
        st.header("MCA Console")
        st.markdown("""
        A focused workspace for transaction uploads, business processing rates, and saved calculation history.
        """)
        
        st.header("System Status")
        
        # Show database stats
        try:
            businesses_df = get_all_businesses()
            st.metric("Configured Businesses", len(businesses_df))
            
            history_count = get_processing_history_count()
            st.metric("Processing Records", history_count)
        except:
            st.metric("Configured Businesses", 0)
            st.metric("Processing Records", 0)

if __name__ == "__main__":
    main()
