# MCA Multi-Business Processing Tool

A Streamlit application for processing multiple business transaction files and calculating processing amounts based on pre-configured percentages using MCA (Merchant Cash Advance) business lending scorecard logic.

## 🎯 Features

### 📁 Multi-File Processing
- Upload multiple JSON transaction files simultaneously
- Automatically extract business names from filenames
- Process all businesses in one session

### ⚙️ Business Management
- Configure processing percentages per business
- Persistent SQLite database storage
- Easy add/edit/update business settings

### 📊 Income Analysis & Calculations
- Automatic categorization using MCA business lending logic
- Calculate processing amounts: `Income × Processing % = Amount to Process`
- Flexible time period selection (today, week, month, custom range)
- Daily breakdown views

### 📈 Processing History
- Track all processing calculations over time
- View historical trends and summaries
- Export historical data

## 🚀 Installation

1. **Clone/Download this repository:**
```bash
git clone <your-repo-url>
cd mca-multi-business-processor
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Run the application:**
```bash
streamlit run app.py
```

4. **Open in browser:** Usually `http://localhost:8501`

## 📖 Usage Guide

### 1. **First Time Setup - Configure Businesses**
- Go to **"Business Management"** tab
- Add your businesses with their processing percentages
- Example: "ABC Ltd" with 15.5% processing rate

### 2. **Process Transactions**
- Go to **"Processing & Analysis"** tab
- Upload multiple JSON files (one per business)
- Select your desired time period
- Review income calculations and processing amounts

### 3. **View Results**
- See total income per business
- View calculated processing amounts
- Export summaries and detailed transaction data
- Save calculations to processing history

### 4. **Review History**
- Go to **"Processing History"** tab
- View past processing calculations
- Export historical data for reporting

## 📁 JSON File Format

Your transaction JSON files should follow this structure:

```json
{
  "accounts": [
    {
      "account_id": "string",
      "name": "string",
      "type": "string",
      "sort_code": "string",
      "account": "string",
      "balances": {
        "available": number,
        "current": number
      }
    }
  ],
  "transactions": [
    {
      "transaction_id": "string",
      "account_id": "string",
      "date": "YYYY-MM-DD",
      "name": "string",
      "merchant_name": "string",
      "amount": number,
      "category": ["array", "of", "strings"],
      "personal_finance_category.detailed": "string"
    }
  ]
}
```

## 🏷️ MCA Categories

The tool automatically categorizes transactions using your business lending scorecard logic:

### Revenue Categories
- **Income**: Payment processors (Stripe, Square, PayPal, etc.), business revenue
- **Special Inflow**: Dividends, interest, transfers in, deposits

### Debt/Financing Categories  
- **Loans**: Business loans, cash advances from recognized lenders
- **Debt Repayments**: Loan payments, debt service

### Expense Categories
- **Expenses**: General business expenses (categorized by Plaid broad categories)
- **Special Outflow**: Transfers out, withdrawals

### Other Categories
- **Failed Payment**: Insufficient funds, late payment fees
- **Uncategorised**: Transactions that don't match any pattern

## 📊 Business Name Extraction

Business names are automatically extracted from filenames using these patterns:

- `ABC_Ltd_transactions.json` → "ABC Ltd"
- `company-name-2024-data.json` → "Company Name"  
- `XYZ Corp - Jan 2024.json` → "XYZ Corp"
- `business_name_export.json` → "Business Name"

The tool removes common words like "transactions", "data", "export" and date patterns.

## 💾 Data Storage

- **Database**: SQLite (`mca_business_data.db`) auto-created on first run
- **Business Configuration**: Persistent storage of processing percentages
- **Processing History**: All calculations saved with timestamps
- **No External Dependencies**: Self-contained database solution

## 🔧 Workflow Example

1. **Setup**: Add "ABC Ltd" with 15% processing rate
2. **Upload**: Upload `ABC_Ltd_transactions_Jan2024.json`
3. **Period**: Select "This Month" 
4. **Results**: See £10,000 income → £1,500 to process
5. **Save**: Store calculation in processing history
6. **Export**: Download summary CSV for reporting

## 📈 Export Formats

### Business Summary CSV
- Business name, total income, processing percentage, amount to process
- Aggregated totals and transaction counts

### Income Transactions CSV  
- Individual transaction details with MCA categorization
- Business assignment and processing flags

### Processing History CSV
- Historical processing calculations
- Period tracking and trend analysis

## ⚙️ Technical Details

- **Framework**: Streamlit
- **Database**: SQLite3 
- **Data Processing**: Pandas
- **Categorization**: Custom regex patterns matching business lending scorecard
- **File Processing**: JSON parsing with error handling

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes  
4. Test thoroughly
5. Submit a pull request

## 📄 License

[Add your license here]

## 🆘 Support

For questions or issues:
1. Check the processing history for data verification
2. Ensure JSON files follow the expected format
3. Verify business names are correctly extracted from filenames
4. Configure processing percentages in Business Management tab

## 🔄 Version History

- **v1.0**: Initial release with multi-business processing
- Features: Business management, income analysis, processing history