import pandas as pd
import streamlit as st
import json
import re
import sqlite3
from datetime import datetime, date, timedelta
import os

# Database setup
DATABASE_FILE = "mca_business_data.db"

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Create businesses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            processing_percentage REAL NOT NULL DEFAULT 0.0,
            created_date TEXT NOT NULL,
            updated_date TEXT NOT NULL
        )
    ''')
    
    # Create processing history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processing_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            income_amount REAL NOT NULL,
            processing_amount REAL NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses (id)
        )
    ''')
    
    # Create app settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

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
    conn = sqlite3.connect(DATABASE_FILE)
    df = pd.read_sql_query('''
        SELECT id, name, processing_percentage, created_date, updated_date 
        FROM businesses 
        ORDER BY name
    ''', conn)
    conn.close()
    return df

def add_or_update_business(name: str, processing_percentage: float) -> int:
    """Add new business or update existing one"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    current_time = datetime.now().isoformat()
    
    # Try to update existing business
    cursor.execute('''
        UPDATE businesses 
        SET processing_percentage = ?, updated_date = ?
        WHERE name = ?
    ''', (processing_percentage, current_time, name))
    
    if cursor.rowcount == 0:
        # Insert new business
        cursor.execute('''
            INSERT INTO businesses (name, processing_percentage, created_date, updated_date)
            VALUES (?, ?, ?, ?)
        ''', (name, processing_percentage, current_time, current_time))
    
    # Get the business ID
    cursor.execute('SELECT id FROM businesses WHERE name = ?', (name,))
    business_id = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    return business_id

def update_business_by_id(business_id: int, name: str, processing_percentage: float) -> int:
    """Update an existing business by ID, preserving identity across renames."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    current_time = datetime.now().isoformat()
    cursor.execute('''
        UPDATE businesses
        SET name = ?, processing_percentage = ?, updated_date = ?
        WHERE id = ?
    ''', (name, processing_percentage, current_time, business_id))

    conn.commit()
    conn.close()
    return business_id

def save_processing_history(business_id: int, date: str, income_amount: float, 
                          processing_amount: float, period_start: str, period_end: str):
    """Save processing history to database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Delete existing record for same business and date to avoid duplicates
    cursor.execute('''
        DELETE FROM processing_history 
        WHERE business_id = ? AND date = ? AND period_start = ? AND period_end = ?
    ''', (business_id, date, period_start, period_end))
    
    # Insert new record
    cursor.execute('''
        INSERT INTO processing_history 
        (business_id, date, income_amount, processing_amount, period_start, period_end)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (business_id, date, income_amount, processing_amount, period_start, period_end))
    
    conn.commit()
    conn.close()

# MCA Sub-categorization using your business lending scorecard logic
MCA_CATEGORIES = [
    'Income',
    'Special Inflow', 
    'Loans',
    'Debt Repayments',
    'Expenses',
    'Special Outflow',
    'Failed Payment',
    'Uncategorised'
]

def map_transaction_category(transaction):
    """Enhanced transaction categorization matching your business lending scorecard version"""
    name = transaction.get("name", "")
    if isinstance(name, list):
        name = " ".join(map(str, name))
    else:
        name = str(name)
    name = name.lower()

    description = transaction.get("merchant_name", "")
    if isinstance(description, list):
        description = " ".join(map(str, description))
    else:
        description = str(description)
    description = description.lower()

    category = transaction.get("personal_finance_category.detailed", "")
    if isinstance(category, list):
        category = " ".join(map(str, category))
    else:
        category = str(category)
    category = category.lower().strip().replace(" ", "_")

    amount = transaction.get("amount", 0)
    combined_text = f"{name} {description}"

    is_credit = amount < 0
    is_debit = amount > 0

    # Step 1: Custom keyword overrides
    if is_credit and re.search(
        r"(?i)\b("
        r"stripe|sumup|zettle|square|take\s*payments|shopify|card\s+settlement|daily\s+takings|payout"
        r"|paypal|go\s*cardless|klarna|worldpay|izettle|ubereats|just\s*eat|deliveroo|uber|bolt"
        r"|fresha|treatwell|taskrabbit|terminal|pos\s+deposit|revolut"
        r"|capital\s+one|evo\s*payments?|tink|teya(\s+solutions)?|talech"
        r"|barclaycard|elavon|adyen|payzone|verifone|ingenico"
        r"|nmi|trust\s+payments?|global\s+payments?|checkout\.com|epdq|santander|handepay"
        r"|dojo|valitor|paypoint|mypos|moneris|paymentsense"
        r"|merchant\s+services|payment\s+sense"
        r"|bcard\d*\s*bcard|bcard\d+|bcard\s+\d+"
        r")\b", 
        combined_text
    ):
        return "Income"
    if is_credit and re.search(r"(you\s?lend|yl\s?ii|yl\s?ltd|yl\s?limited|yl\s?a\s?limited)", combined_text):
        # Check if it contains funding indicators (including within reference numbers)
        if re.search(r"(fnd|fund|funding)", combined_text):
            return "Loans"
        else:
            return "Income"
    if is_credit and re.search(
        r"\biwoca\b|\bcapify\b|\bfundbox\b|\bgot[\s\-]?capital\b|\bfunding[\s\-]?circle\b|"
        r"\bfleximize\b|\bmarketfinance\b|\bliberis\b|\besme[\s\-]?loans\b|\bthincats\b|"
        r"\bwhite[\s\-]?oak\b|\bgrowth[\s\-]?street\b|\bnucleus[\s\-]?commercial[\s\-]?finance\b|"
        r"\bultimate[\s\-]?finance\b|\bjust[\s\-]?cash[\s\-]?flow\b|\bboost[\s\-]?capital\b|"
        r"\bmerchant[\s\-]?money\b|\bcapital[\s\-]?on[\s\-]?tap\b|\bkriya\b|\buncapped\b|"
        r"\blendingcrowd\b|\bfolk2folk\b|\bfunding[\s\-]?tree\b|\bstart[\s\-]?up[\s\-]?loans\b|"
        r"\bbcrs[\s\-]?business[\s\-]?loans\b|\bbusiness[\s\-]?enterprise[\s\-]?fund\b|"
        r"\bswig[\s\-]?finance\b|\benterprise[\s\-]?answers\b|\blet's[\s\-]?do[\s\-]?business[\s\-]?finance\b|"
        r"\bfinance[\s\-]?for[\s\-]?enterprise\b|\bdsl[\s\-]?business[\s\-]?finance\b|"
        r"\bbizcap[\s\-]?uk\b|\bsigma[\s\-]?lending\b|\bbizlend[\s\-]?ltd\b|\bcubefunder\b|\bloans?\b",
        combined_text
    ):
        return "Loans"

    if is_debit and re.search(
        r"\biwoca\b|\bcapify\b|\bfundbox\b|\bgot[\s\-]?capital\b|\bfunding[\s\-]?circle\b|\bfleximize\b|\bmarketfinance\b|\bliberis\b|"
        r"\besme[\s\-]?loans\b|\bthincats\b|\bwhite[\s\-]?oak\b|\bgrowth[\s\-]?street\b|\bnucleus[\s\-]?commercial[\s\-]?finance\b|"
        r"\bultimate[\s\-]?finance\b|\bjust[\s\-]?cash[\s\-]?flow\b|\bboost[\s\-]?capital\b|\bmerchant[\s\-]?money\b|"
        r"\bcapital[\s\-]?on[\s\-]?tap\b|\bkriya\b|\buncapped\b|\blendingcrowd\b|\bfolk2folk\b|\bfunding[\s\-]?tree\b|"
        r"\bstart[\s\-]?up[\s\-]?loans\b|\bbcrs[\s\-]?business[\s\-]?loans\b|\bbusiness[\s\-]?enterprise[\s\-]?fund\b|"
        r"\bswig[\s\-]?finance\b|\benterprise[\s\-]?answers\b|\blet's[\s\-]?do[\s\-]?business[\s\-]?finance\b|"
        r"\bfinance[\s\-]?for[\s\-]?enterprise\b|\bdsl[\s\-]?business[\s\-]?finance\b|\bbizcap[\s\-]?uk\b|"
        r"\bsigma[\s\-]?lending\b|\bbizlend[\s\-]?ltd\b|"
        r"\bloan[\s\-]?repayment\b|\bdebt[\s\-]?repayment\b|\binstal?ments?\b|\bpay[\s\-]+back\b|\brepay(?:ing|ment|ed)?\b",
        combined_text
    ):
        return "Debt Repayments"
        
    # Step 1.5: Business expense override (before Plaid fallback)
    if is_debit and re.search(r"(facebook|facebk|fb\.me|outlook|office365|microsoft|google\s+ads|linkedin|twitter|adobe|zoom|slack|shopify|wix|squarespace|mailchimp|hubspot|hmrc\s*vat|hmrc|hm\s*revenue|hm\s*customs)", combined_text, re.IGNORECASE):
        return "Expenses"

    # Step 2: Plaid category fallback with validation
    plaid_map = {
        "income_wages": "Income",
        "income_other_income": "Income",
        "income_dividends": "Special Inflow",
        "income_interest_earned": "Special Inflow",
        "income_retirement_pension": "Special Inflow",
        "income_unemployment": "Special Inflow",
        "transfer_in_cash_advances_and_loans": "Loans",
        "transfer_in_investment_and_retirement_funds": "Special Inflow",
        "transfer_in_savings": "Special Inflow",
        "transfer_in_account_transfer": "Special Inflow",
        "transfer_in_other_transfer_in": "Special Inflow",
        "transfer_in_deposit": "Special Inflow",
        "transfer_out_investment_and_retirement_funds": "Special Outflow",
        "transfer_out_savings": "Special Outflow",
        "transfer_out_other_transfer_out": "Special Outflow",
        "transfer_out_withdrawal": "Special Outflow",
        "transfer_out_account_transfer": "Special Outflow",
        "bank_fees_insufficient_funds": "Failed Payment",
        "bank_fees_late_payment": "Failed Payment",
    }

    # Handle loan payment categories with validation
    if category.startswith("loan_payments_"):
        # Only trust Plaid if transaction contains actual loan/debt keywords
        if re.search(r"(loan|debt|repay|finance|lending|credit|iwoca|capify|fundbox)", combined_text, re.IGNORECASE):
            return "Debt Repayments"
        # Otherwise, don't trust Plaid and continue to other checks

    # Match exact key
    if category in plaid_map:
        return plaid_map[category]

    # Step 3: Fallback for Plaid broad categories
    broad_matchers = [
        ("Expenses", [
            "bank_fees_", "entertainment_", "food_and_drink_", "general_merchandise_",
            "general_services_", "government_and_non_profit_", "home_improvement_",
            "medical_", "personal_care_", "rent_and_utilities_", "transportation_", "travel_"
        ])
    ]

    for label, patterns in broad_matchers:
        if any(category.startswith(p) for p in patterns):
            return label

   # Default fallback: debit transactions become Expenses, credit transactions stay Uncategorised
    if is_debit:
        return "Expenses"
    else:
        return "Uncategorised"

def categorize_transaction(transaction_dict):
    """
    Wrapper function to categorize a single transaction using your MCA logic
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

def clear_processing_results():
    """Clear cached processing results when uploads change or are removed."""
    for key in ("df", "business_mappings", "date_range", "upload_signature"):
        st.session_state.pop(key, None)

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

    st.subheader("💰 Income Analysis & Processing Calculations")

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

            for business_name, row in business_summary.iterrows():
                business_id = add_or_update_business(business_name, row['Processing %'])
                save_processing_history(
                    business_id=business_id,
                    date=date.today().isoformat(),
                    income_amount=row['Total Income'],
                    processing_amount=row['Amount to Process'],
                    period_start=period_start,
                    period_end=period_end
                )

            st.success("Processing calculations saved to database!")

        if st.checkbox("📊 Show Daily Breakdown", key="show_daily_breakdown"):
            st.subheader("Daily Income Breakdown")

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
                    
                    # Apply your MCA categorization logic
                    mca_subcategory = categorize_transaction(txn)
                    
                    # Determine flags based on subcategory
                    is_revenue = mca_subcategory in ['Income', 'Special Inflow']
                    is_expense = mca_subcategory in ['Expenses', 'Special Outflow']
                    is_debt_repayment = mca_subcategory in ['Debt Repayments']
                    is_debt = mca_subcategory in ['Loans']
                    
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
                        'is_expense': is_expense,
                        'is_debt_repayment': is_debt_repayment,
                        'is_debt': is_debt,
                        'selected': True
                    })
                except Exception as txn_error:
                    st.warning(f"Skipping malformed transaction in {uploaded_file.name}: {txn_error}")

        except Exception as e:
            st.error(f"Failed to process {uploaded_file.name}: {str(e)}")

    return pd.DataFrame(all_business_data)

def business_management_tab():
    """Business management interface"""
    st.header("Business Management")
    
    businesses_df = get_all_businesses()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Current Businesses")
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
                for _, row in edited_df.iterrows():
                    update_business_by_id(int(row['id']), str(row['name']).strip(), float(row['processing_percentage']))
                st.success("Business settings updated!")
                st.rerun()
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

def extract_business_name_from_json(json_data, filename=""):
    """Extract business name from JSON account data with multi-account handling"""
    accounts = json_data.get('accounts', [])
    
    if not accounts:
        return f"Unknown Business ({filename})", [], {}
    
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
        # Multiple accounts - return first one as default, but provide options
        return clean_account_name(account_names[0]), account_names, account_info

def create_business_name_mapping_interface(business_extractions):
    """Create enhanced business name mapping interface with existing business dropdown"""
    
    st.markdown("**Review and confirm business names extracted from account data:**")
    st.info("💡 **Tip**: You can use extracted names, choose from account options, select from existing businesses, or enter manually.")
    
    # Get existing businesses for dropdown
    existing_businesses_df = get_all_businesses()
    existing_business_names = [""] + list(existing_businesses_df['name'].tolist()) if not existing_businesses_df.empty else [""]
    
    business_name_mappings = {}
    
    for extraction in business_extractions:
        st.markdown("---")
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
    st.header("Multi-Business Transaction Processing")
    
    uploaded_files = st.file_uploader(
        "Upload Business Transaction JSON Files", 
        type=['json'],
        accept_multiple_files=True,
        help="Select multiple JSON files - business names will be extracted from account data within each file."
    )

    if not uploaded_files:
        clear_processing_results()
        st.info("📁 Upload JSON files to begin processing.")
        st.markdown("""
        **🎯 How it works:**
        1. **📁 Upload Files**: Upload multiple JSON files (can have same generic filename)
        2. **🏢 Extract Names**: Business names automatically extracted from account data
        3. **✏️ Review & Edit**: Choose extraction method and edit names as needed
        4. **📊 Process**: Calculate income and processing amounts based on configured percentages
        """)

        st.subheader("🧽 Business Name Extraction Examples")
        st.markdown("""
        **The tool will automatically clean account names like:**
        - `ABC Ltd Current Account` → `ABC Ltd`
        - `XYZ COMPANY BUSINESS ACCOUNT` → `Xyz Company` 
        - `My Restaurant Ltd - 12345` → `My Restaurant Ltd`
        - `COFFEE SHOP LIMITED CURRENT` → `Coffee Shop Limited`
        - `Bound Expenses` → `Bound Expenses` *(you can manually change to "Bound Studios Ltd")*
        """)

        with st.expander("📚 MCA Categories Reference"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**💰 Revenue Categories:**")
                st.markdown("• Income")
                st.markdown("• Special Inflow")

                st.markdown("**💳 Debt/Financing Categories:**") 
                st.markdown("• Loans")
                st.markdown("• Debt Repayments")
            
            with col2:
                st.markdown("**💸 Expense Categories:**")
                st.markdown("• Expenses")
                st.markdown("• Special Outflow")
                
                st.markdown("**❌ Other Categories:**")
                st.markdown("• Failed Payment")
                st.markdown("• Uncategorised")
        return

    current_signature = get_uploaded_files_signature(uploaded_files)
    if st.session_state.get('upload_signature') not in (None, current_signature):
        clear_processing_results()

    st.subheader("Business Name Extraction & Configuration")

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

    st.subheader("📋 Final Business Mapping Summary")
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

    st.subheader("⏰ Time Period Selection")

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

    if st.button("🚀 Process All Files", type="primary"):
        with st.spinner("Processing transaction files..."):
            df = process_multiple_json_files(uploaded_files, business_name_mappings, start_date, end_date)

        if not df.empty:
            st.session_state.df = df.copy()
            st.session_state.business_mappings = business_name_mappings
            st.session_state.date_range = (start_date.isoformat(), end_date.isoformat())
            st.session_state.upload_signature = current_signature
        else:
            clear_processing_results()
            st.error("No valid transaction data found in uploaded files.")

    stored_range = st.session_state.get('date_range')
    stored_df = st.session_state.get('df')
    if stored_df is not None and stored_range and st.session_state.get('upload_signature') == current_signature:
        saved_start = datetime.strptime(stored_range[0], "%Y-%m-%d").date()
        saved_end = datetime.strptime(stored_range[1], "%Y-%m-%d").date()
        render_processing_results(stored_df, saved_start, saved_end)

def processing_history_tab():
    """View processing history"""
    st.header("Processing History")
    
    conn = sqlite3.connect(DATABASE_FILE)
    
    # Get processing history with business names
    history_df = pd.read_sql_query('''
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
    ''', conn)
    
    conn.close()
    
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
        if st.button("Export Processing History"):
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
    # Initialize database
    init_database()
    
    st.set_page_config(
        page_title="MCA Multi-Business Processing Tool",
        page_icon="💼",
        layout="wide"
    )
    
    st.title("💼 MCA Multi-Business Processing Tool")
    st.markdown("Process multiple business transaction files and calculate processing amounts based on pre-configured percentages.")
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📊 Processing & Analysis", "⚙️ Business Management", "📈 Processing History"])
    
    with tab1:
        processing_analysis_tab()
    
    with tab2:
        business_management_tab()
    
    with tab3:
        processing_history_tab()
    
    # Sidebar info
    with st.sidebar:
        st.header("About")
        st.markdown("""
        **MCA Processing Tool Features:**
        
        📁 **Multi-File Upload**
        - Upload multiple JSON files
        - Auto-extract business names from account data
        
        ⚙️ **Business Configuration**
        - Set processing percentages per business
        - Persistent storage in SQLite database
        
        📊 **Income Analysis**
        - Calculate processing amounts automatically
        - Daily/period breakdowns
        - Export summaries and transaction details
        
        📈 **Processing History**
        - Track historical processing calculations
        - View trends and summaries
        """)
        
        st.header("Quick Stats")
        
        # Show database stats
        try:
            businesses_df = get_all_businesses()
            st.metric("Configured Businesses", len(businesses_df))
            
            conn = sqlite3.connect(DATABASE_FILE)
            history_count = pd.read_sql_query('SELECT COUNT(*) as count FROM processing_history', conn).iloc[0]['count']
            conn.close()
            st.metric("Processing Records", history_count)
        except:
            st.metric("Configured Businesses", 0)
            st.metric("Processing Records", 0)

if __name__ == "__main__":
    main()
