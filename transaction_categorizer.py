"""Local copy of the MCAV2 transaction categorisation engine.

Copied from MCAV2's ``app.services.data_processor.TransactionCategorizer`` so
this app can stay independent while matching MCAV2 transaction categories.
"""

import re
from typing import Any, Dict, Tuple


class TransactionCategorizer:
    """Business-focused transaction categorisation with confidence scores."""

    def __init__(self):
        self.categorization_rules = self._load_categorization_rules()
        self.confidence_threshold = 0.8

    def _load_categorization_rules(self) -> Dict[str, Any]:
        """Load categorisation rules and patterns."""
        return {
            "income_patterns": {
                "payment_processors": [
                    r"stripe", r"sumup", r"zettle", r"square", r"take\s*payments",
                    r"shopify", r"card\s+settlement", r"daily\s+takings", r"payout",
                    r"paypal", r"go\s*cardless", r"klarna", r"worldpay", r"izettle",
                    r"ubereats", r"just\s*eat", r"deliveroo", r"uber", r"bolt",
                    r"fresha", r"treatwell", r"taskrabbit", r"terminal", r"pos\s+deposit",
                    r"revolut", r"capital\s+on\s+tap", r"evo\s*payments?", r"tink",
                    r"teya(\s+solutions)?", r"talech", r"barclaycard", r"elavon", r"adyen",
                ],
                "direct_revenue": [
                    r"sales", r"revenue", r"income", r"payment\s+received",
                    r"customer\s+payment", r"invoice\s+payment", r"service\s+fee",
                ],
                "special_cases": [
                    (
                        r"you\s?lend|yl\s?ii|yl\s?ltd|yl\s?limited|yl\s?a\s?limited|\byl\b",
                        lambda text: "Loans" if re.search(r"\b(fnd|fund|funding)\b", text) else "Income",
                    )
                ],
            },
            "loan_patterns": [
                r"iwoca", r"capify", r"fundbox", r"got[\s\-]?capital", r"funding[\s\-]?circle",
                r"fleximize", r"marketfinance", r"liberis", r"esme[\s\-]?loans", r"thincats",
                r"white[\s\-]?oak", r"growth[\s\-]?street", r"nucleus[\s\-]?commercial[\s\-]?finance",
                r"ultimate[\s\-]?finance", r"just[\s\-]?cash[\s\-]?flow", r"boost[\s\-]?capital",
                r"merchant[\s\-]?money", r"capital[\s\-]?on[\s\-]?tap", r"kriya", r"uncapped",
                r"lendingcrowd", r"folk2folk", r"funding[\s\-]?tree", r"start[\s\-]?up[\s\-]?loans",
                r"loan", r"advance", r"financing", r"disbursement",
                r"you\s?lend", r"\byl\b", r"everyday[\s\-]?people[\s\-]?finance",
                r"barclays", r"natwest", r"hsbc", r"lloyds", r"santander",
                r"metro[\s\-]?bank", r"royal[\s\-]?bank[\s\-]?of[\s\-]?scotland", r"\brbs\b",
                r"starling", r"zempler", r"oak[\s\-]?north", r"allica", r"monzo", r"revolut",
                r"funding[\s\-]?agent", r"nationwide[\s\-]?finance", r"cubefunder",
                r"spotcap", r"time[\s\-]?finance", r"together",
                r"corporate[\s\-]?asset[\s\-]?solutions", r"creative[\s\-]?capital",
                r"credit4", r"crowd2fund", r"fgi[\s\-]?finance",
                r"hampshire[\s\-]?trust[\s\-]?bank", r"hodge[\s\-]?bank",
                r"igf[\s\-]?invoice[\s\-]?finance", r"investec", r"lendinvest",
                r"maslow[\s\-]?capital", r"mycashline", r"octane[\s\-]?capital",
                r"secure[\s\-]?trust[\s\-]?bank", r"sme[\s\-]?capital", r"swishfund",
                r"growth[\s\-]?guarantee[\s\-]?scheme", r"british[\s\-]?business[\s\-]?bank",
                r"community[\s\-]?development[\s\-]?finance", r"cdfi",
            ],
            "debt_repayment_patterns": [
                r"repayment", r"loan\s+payment", r"debt\s+service", r"installment",
                r"instalment", r"payback", r"repay", r"amortization",
                r"iwoca", r"capify", r"fundbox", r"got[\s\-]?capital", r"funding[\s\-]?circle",
                r"fleximize", r"market[\s\-]?finance", r"liberis", r"esme[\s\-]?loans",
                r"thincats", r"white[\s\-]?oak", r"growth[\s\-]?street",
                r"nucleus[\s\-]?commercial[\s\-]?finance", r"ultimate[\s\-]?finance",
                r"just[\s\-]?cash[\s\-]?flow", r"boost[\s\-]?capital", r"merchant[\s\-]?money",
                r"capital[\s\-]?on[\s\-]?tap", r"kriya", r"uncapped", r"lendingcrowd",
                r"folk2folk", r"funding[\s\-]?tree", r"start[\s\-]?up[\s\-]?loans",
                r"you\s?lend", r"\byl\b", r"everyday[\s\-]?people[\s\-]?finance",
                r"barclays", r"natwest", r"hsbc", r"lloyds", r"santander",
                r"metro[\s\-]?bank", r"royal[\s\-]?bank[\s\-]?of[\s\-]?scotland", r"\brbs\b",
                r"starling", r"zempler", r"oak[\s\-]?north", r"allica", r"monzo", r"revolut",
                r"funding[\s\-]?agent", r"nationwide[\s\-]?finance", r"cubefunder",
                r"spotcap", r"time[\s\-]?finance", r"together",
                r"corporate[\s\-]?asset[\s\-]?solutions", r"creative[\s\-]?capital",
                r"credit4", r"crowd2fund", r"fgi[\s\-]?finance",
                r"hampshire[\s\-]?trust[\s\-]?bank", r"hodge[\s\-]?bank",
                r"igf[\s\-]?invoice[\s\-]?finance", r"investec", r"lendinvest",
                r"maslow[\s\-]?capital", r"mycashline", r"octane[\s\-]?capital",
                r"secure[\s\-]?trust[\s\-]?bank", r"sme[\s\-]?capital", r"swishfund",
                r"growth[\s\-]?guarantee[\s\-]?scheme", r"british[\s\-]?business[\s\-]?bank",
                r"community[\s\-]?development[\s\-]?finance", r"cdfi",
            ],
            "transfer_patterns": [
                r"\btransfer\s+(from|to)\b", r"\btrf\b", r"\bfaster\s+payment\b",
                r"\bown\s+account\b", r"\bbetween\s+accounts\b", r"\bmove\s+money\b",
                r"\baccount\s+transfer\b", r"\bsweep\b", r"\bsavings\s+transfer\b",
                r"\bcurrent\s+account\s+transfer\b",
            ],
            "funding_injection_patterns": [
                r"director[\' ]?s?\s+loan", r"shareholder\s+loan", r"capital\s+introduced",
                r"capital\s+injection", r"capital\s+contribution", r"owner\s+funds?",
                r"owner\s+investment", r"founder\s+loan", r"member\s+loan",
                r"partners?\s+capital", r"shareholder\s+funding",
            ],
            "bank_charge_patterns": [
                r"account\s+fee", r"monthly\s+fee", r"service\s+charge", r"bank\s+charge",
                r"overdraft\s+fee", r"arranged\s+overdraft", r"unarranged\s+overdraft",
                r"paid\s+item\s+fee", r"card\s+terminal\s+fee", r"merchant\s+service\s+charge",
            ],
            "failed_payment_patterns": [
                r"\bunpaid\b", r"\breturned\b", r"\bbounced\b",
                r"\binsufficient\s+funds\b", r"\bnsf\b", r"\bdeclined\b",
                r"\bfailed\b", r"\breversed\b", r"\bchargeback\b",
            ],
        }

    def categorize_transaction(self, transaction: Dict[str, Any]) -> Tuple[str, float]:
        """Categorise a single transaction and return ``(category, confidence)``."""
        name = str(transaction.get("name_y", transaction.get("name", ""))).lower()
        transaction_name = str(transaction.get("transaction_name", "")).lower()
        merchant_name = str(transaction.get("merchant_name", "")).lower()
        category = str(transaction.get("personal_finance_category.detailed", "")).lower()
        amount = transaction.get("amount_original", transaction.get("amount_1", transaction.get("amount", 0)))

        combined_text = f"{name} {transaction_name} {merchant_name}"
        normalized_text = combined_text.replace("_", " ")
        is_credit = amount < 0
        is_debit = amount > 0

        failed_category, confidence = self._check_failed_payment_patterns(combined_text, category)
        if confidence > self.confidence_threshold:
            return failed_category, confidence

        if is_credit:
            refund_category, confidence = self._check_refund_patterns(combined_text)
            if confidence > self.confidence_threshold:
                return refund_category, confidence

        transfer_category, confidence = self._check_transfer_patterns(combined_text, category, is_credit, is_debit)
        if confidence > self.confidence_threshold:
            return transfer_category, confidence

        if is_credit:
            funding_category, confidence = self._check_funding_patterns(combined_text)
            if confidence > self.confidence_threshold:
                return funding_category, confidence

        if is_debit:
            bank_charge_category, confidence = self._check_bank_charge_patterns(combined_text, category)
            if confidence > self.confidence_threshold:
                return bank_charge_category, confidence

        if is_credit:
            income_category, confidence = self._check_income_patterns(combined_text)
            if confidence > self.confidence_threshold:
                return income_category, confidence

        if re.search(r"disbursement", normalized_text, re.IGNORECASE):
            if is_credit or category.startswith("transfer_in_"):
                return "Loans", 0.9

        loan_category, confidence = self._check_loan_patterns(combined_text, is_credit)
        if confidence > self.confidence_threshold:
            return loan_category, confidence

        if is_debit:
            debt_category, confidence = self._check_debt_patterns(combined_text)
            if confidence > self.confidence_threshold:
                return debt_category, confidence

        plaid_category, confidence = self._map_plaid_category(category, is_credit, is_debit)
        if confidence > 0.5:
            return plaid_category, confidence

        if is_credit:
            return "Uncategorised", 0.3
        return "Expenses", 0.3

    def _check_income_patterns(self, text: str) -> Tuple[str, float]:
        for pattern in self.categorization_rules["income_patterns"]["payment_processors"]:
            if re.search(pattern, text, re.IGNORECASE):
                return "Income", 0.95

        for pattern in self.categorization_rules["income_patterns"]["direct_revenue"]:
            if re.search(pattern, text, re.IGNORECASE):
                return "Income", 0.85

        for pattern, condition_func in self.categorization_rules["income_patterns"]["special_cases"]:
            if re.search(pattern, text, re.IGNORECASE):
                return condition_func(text), 0.9

        return "Unknown", 0.0

    def _check_loan_patterns(self, text: str, is_credit: bool) -> Tuple[str, float]:
        for pattern in self.categorization_rules["loan_patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                if is_credit:
                    return "Loans", 0.9
                return "Debt Repayments", 0.9

        return "Unknown", 0.0

    def _check_transfer_patterns(self, text: str, category: str, is_credit: bool, is_debit: bool) -> Tuple[str, float]:
        for pattern in self.categorization_rules["transfer_patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                if is_credit:
                    return "Transfer In", 0.9
                if is_debit:
                    return "Transfer Out", 0.9

        if category.startswith("transfer_in_") and category != "transfer_in_cash_advances_and_loans":
            return "Transfer In", 0.9
        if category.startswith("transfer_out_"):
            return "Transfer Out", 0.9

        return "Unknown", 0.0

    def _check_funding_patterns(self, text: str) -> Tuple[str, float]:
        for pattern in self.categorization_rules["funding_injection_patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                return "Funding Inflow", 0.9

        return "Unknown", 0.0

    def _check_bank_charge_patterns(self, text: str, category: str = "") -> Tuple[str, float]:
        for pattern in self.categorization_rules["bank_charge_patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                return "Bank Charge", 0.9

        if category.startswith("bank_fees_") and category not in {
            "bank_fees_insufficient_funds",
            "bank_fees_late_payment",
            "bank_fees_overdraft",
            "bank_fees_returned_payment",
        }:
            return "Bank Charge", 0.85

        return "Unknown", 0.0

    def _check_debt_patterns(self, text: str) -> Tuple[str, float]:
        for pattern in self.categorization_rules["debt_repayment_patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                return "Debt Repayments", 0.85

        return "Unknown", 0.0

    def _check_failed_payment_patterns(self, text: str, category: str = "") -> Tuple[str, float]:
        extended_patterns = [
            r"reversal", r"reversed", r"chargeback", r"dispute",
            r"refund\s+fee", r"rejected", r"cancelled\s+payment", r"payment\s+returned",
        ]

        for pattern in self.categorization_rules["failed_payment_patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                return "Failed Payment", 0.95

        for pattern in extended_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return "Failed Payment", 0.95

        failed_plaid_categories = [
            "bank_fees_insufficient_funds",
            "bank_fees_late_payment",
            "bank_fees_overdraft",
            "bank_fees_returned_payment",
        ]
        if category.lower() in failed_plaid_categories:
            return "Failed Payment", 0.95

        return "Unknown", 0.0

    def _check_refund_patterns(self, text: str) -> Tuple[str, float]:
        refund_patterns = [
            r"refund", r"rebate", r"credit\s+adj", r"adjustment",
            r"cashback", r"reimburs", r"money\s+back", r"return\s+credit",
        ]

        for pattern in refund_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return "Special Inflow", 0.9

        return "Unknown", 0.0

    def _map_plaid_category(self, category: str, is_credit: bool = False, is_debit: bool = True) -> Tuple[str, float]:
        plaid_mapping = {
            "income_wages": ("Income", 0.8),
            "income_other_income": ("Income", 0.7),
            "income_dividends": ("Special Inflow", 0.8),
            "income_interest_earned": ("Special Inflow", 0.8),
            "transfer_in_cash_advances_and_loans": ("Loans", 0.9),
            "loan_payments_credit_card_payment": ("Debt Repayments", 0.9),
            "loan_payments_personal_loan_payment": ("Debt Repayments", 0.9),
            "loan_payments_other_payment": ("Debt Repayments", 0.8),
            "bank_fees_insufficient_funds": ("Failed Payment", 0.95),
            "bank_fees_late_payment": ("Failed Payment", 0.95),
            "bank_fees_overdraft": ("Failed Payment", 0.95),
            "bank_fees_returned_payment": ("Failed Payment", 0.95),
        }

        if category in plaid_mapping:
            return plaid_mapping[category]

        if category.startswith("income_"):
            return "Income", 0.6
        if category.startswith("loan_payments_"):
            return "Debt Repayments", 0.7
        if category.startswith("bank_fees_"):
            return "Bank Charge", 0.8
        if category.startswith("transfer_in_"):
            return "Transfer In", 0.7
        if category.startswith("transfer_out_"):
            return "Transfer Out", 0.7

        expense_prefixes = [
            "entertainment_", "food_and_drink_", "general_merchandise_",
            "general_services_", "rent_and_utilities_", "transportation_",
            "travel_", "home_improvement_", "medical_", "personal_care_",
            "government_and_non_profit_",
        ]

        if any(category.startswith(prefix) for prefix in expense_prefixes):
            if is_debit:
                return "Expenses", 0.7
            return "Special Inflow", 0.6

        return "Uncategorised", 0.1
