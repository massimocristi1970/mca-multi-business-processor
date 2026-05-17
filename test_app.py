import io
import json
import os
import tempfile
import unittest
from datetime import date
from unittest import mock

import pandas as pd

import app


class DummyUpload(io.StringIO):
    def __init__(self, name, payload):
        super().__init__(json.dumps(payload))
        self.name = name
        self.size = len(self.getvalue())


class AppTests(unittest.TestCase):
    def setUp(self):
        self.original_db = app.DATABASE_FILE
        self.temp_dir = tempfile.TemporaryDirectory()
        app.DATABASE_FILE = os.path.join(self.temp_dir.name, 'test.db')
        app.init_database()

    def tearDown(self):
        app.DATABASE_FILE = self.original_db
        self.temp_dir.cleanup()

    def test_update_business_by_id_renames_in_place(self):
        business_id = app.add_or_update_business('Alpha Ltd', 10.0)

        app.update_business_by_id(business_id, 'Beta Ltd', 12.5)

        businesses = app.get_all_businesses()
        self.assertEqual(len(businesses), 1)
        self.assertEqual(businesses.iloc[0]['name'], 'Beta Ltd')
        self.assertEqual(businesses.iloc[0]['processing_percentage'], 12.5)

    def test_update_business_by_id_rejects_duplicate_name_and_keeps_db_usable(self):
        alpha_id = app.add_or_update_business('Alpha Ltd', 10.0)
        beta_id = app.add_or_update_business('Beta Ltd', 20.0)

        with self.assertRaises(ValueError):
            app.update_business_by_id(alpha_id, 'Beta Ltd', 30.0)

        app.update_business_by_id(beta_id, 'Gamma Ltd', 25.0)
        businesses = app.get_all_businesses()
        self.assertEqual(set(businesses['name']), {'Alpha Ltd', 'Gamma Ltd'})

    def test_process_multiple_json_files_skips_bad_accounts_but_keeps_file(self):
        upload = DummyUpload(
            'sample.json',
            {
                'accounts': [
                    {'name': 'Broken account'},
                    {'account_id': 'acct-1', 'name': 'Valid Account', 'sort_code': '00-00-00', 'account': '12345678'},
                ],
                'transactions': [
                    {
                        'transaction_id': 'txn-1',
                        'account_id': 'acct-1',
                        'date': '2026-04-01',
                        'name': 'Stripe payout',
                        'merchant_name': 'Stripe',
                        'amount': -150.0,
                        'category': ['income'],
                        'personal_finance_category.detailed': 'income_other_income',
                    }
                ],
            },
        )

        with mock.patch.object(app.st, 'warning'), mock.patch.object(app.st, 'error'):
            df = app.process_multiple_json_files([upload], {0: 'Valid Business'})

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['business_name'], 'Valid Business')
        self.assertTrue(df.iloc[0]['is_authorised_account'])

    def test_process_multiple_json_files_accepts_numeric_string_amounts(self):
        upload = DummyUpload(
            'sample.json',
            {
                'accounts': [
                    {'account_id': 'acct-1', 'name': 'Valid Account'},
                ],
                'transactions': [
                    {
                        'transaction_id': 'txn-1',
                        'account_id': 'acct-1',
                        'date': '2026-04-01',
                        'name': 'Stripe payout',
                        'merchant_name': 'Stripe',
                        'amount': '-150.25',
                    }
                ],
            },
        )

        with mock.patch.object(app.st, 'warning'), mock.patch.object(app.st, 'error'):
            df = app.process_multiple_json_files([upload], {0: 'Valid Business'})

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['amount'], -150.25)
        self.assertEqual(df.iloc[0]['mca_subcategory'], 'Income')

    def test_processing_inputs_signature_changes_with_mapping_and_dates(self):
        upload = DummyUpload('sample.json', {'accounts': [], 'transactions': []})

        first_signature = app.get_processing_inputs_signature(
            [upload],
            {0: 'Alpha Ltd'},
            date(2026, 4, 1),
            date(2026, 4, 30),
        )
        renamed_signature = app.get_processing_inputs_signature(
            [upload],
            {0: 'Beta Ltd'},
            date(2026, 4, 1),
            date(2026, 4, 30),
        )
        date_signature = app.get_processing_inputs_signature(
            [upload],
            {0: 'Alpha Ltd'},
            date(2026, 4, 2),
            date(2026, 4, 30),
        )

        self.assertNotEqual(first_signature, renamed_signature)
        self.assertNotEqual(first_signature, date_signature)

    def test_multi_account_json_prefers_filename_business_name(self):
        extracted_name, account_options, _ = app.extract_business_name_from_json(
            {
                'accounts': [
                    {'account_id': 'acct-1', 'name': 'Saving Challenge (2026)', 'subtype': 'savings'},
                    {'account_id': 'acct-2', 'name': 'Savings', 'subtype': 'savings'},
                    {'account_id': 'acct-3', 'name': 'CurrentAccount 3267', 'subtype': 'checking'},
                ],
                'transactions': [],
            },
            'Upper6th Consultancy Limited.json',
        )

        self.assertEqual(extracted_name, 'Upper6th Consultancy Limited')
        self.assertIn('Saving Challenge (2026)', account_options)

    def test_credit_expense_keyword_is_not_forced_to_expenses(self):
        category = app.map_transaction_category({
            'name': 'HMRC VAT REFUND',
            'merchant_name': '',
            'amount': -125.0,
            'personal_finance_category.detailed': '',
        })

        self.assertNotEqual(category, 'Expenses')

    def test_categorizer_matches_mcav2_edge_cases(self):
        cases = [
            (
                {
                    'name': 'STRIPE REVERSAL',
                    'merchant_name': '',
                    'amount': -100.0,
                    'personal_finance_category.detailed': 'income_other_income',
                },
                'Failed Payment',
            ),
            (
                {
                    'name': 'Transfer from savings',
                    'merchant_name': '',
                    'amount': -250.0,
                    'personal_finance_category.detailed': 'transfer_in_account_transfer',
                },
                'Transfer In',
            ),
            (
                {
                    'name': 'Director loan capital introduced',
                    'merchant_name': '',
                    'amount': -250.0,
                    'personal_finance_category.detailed': '',
                },
                'Funding Inflow',
            ),
            (
                {
                    'name': 'Monthly account fee',
                    'merchant_name': '',
                    'amount': 25.0,
                    'personal_finance_category.detailed': '',
                },
                'Bank Charge',
            ),
            (
                {
                    'name': 'Amazon refund',
                    'merchant_name': '',
                    'amount': -30.0,
                    'personal_finance_category.detailed': 'general_merchandise_books_and_supplies',
                },
                'Special Inflow',
            ),
        ]

        for transaction, expected_category in cases:
            with self.subTest(transaction=transaction['name']):
                self.assertEqual(app.map_transaction_category(transaction), expected_category)

    def test_process_multiple_json_files_uses_mcav2_revenue_flags(self):
        upload = DummyUpload(
            'sample.json',
            {
                'accounts': [
                    {'account_id': 'acct-1', 'name': 'Valid Account'},
                ],
                'transactions': [
                    {
                        'transaction_id': 'txn-1',
                        'account_id': 'acct-1',
                        'date': '2026-04-01',
                        'name': 'Transfer from savings',
                        'merchant_name': '',
                        'amount': -250.0,
                        'personal_finance_category.detailed': 'transfer_in_account_transfer',
                    },
                ],
            },
        )

        with mock.patch.object(app.st, 'warning'), mock.patch.object(app.st, 'error'):
            df = app.process_multiple_json_files([upload], {0: 'Valid Business'})

        self.assertEqual(df.iloc[0]['mca_subcategory'], 'Transfer In')
        self.assertFalse(bool(df.iloc[0]['is_revenue']))
        self.assertTrue(bool(df.iloc[0]['is_transfer_in']))
        self.assertTrue(bool(df.iloc[0]['is_internal_transfer']))

    def test_calculate_business_summary_uses_absolute_income(self):
        df = pd.DataFrame([
            {'business_name': 'Alpha Ltd', 'amount': -100.0, 'transaction_id': '1', 'is_revenue': True},
            {'business_name': 'Alpha Ltd', 'amount': -50.0, 'transaction_id': '2', 'is_revenue': True},
            {'business_name': 'Beta Ltd', 'amount': -200.0, 'transaction_id': '3', 'is_revenue': True},
        ])

        summary = app.calculate_business_summary(df, {'Alpha Ltd': 10.0, 'Beta Ltd': 20.0})

        self.assertEqual(summary.loc['Alpha Ltd', 'Total Income'], 150.0)
        self.assertEqual(summary.loc['Alpha Ltd', 'Amount to Process'], 15.0)
        self.assertEqual(summary.loc['Beta Ltd', 'Amount to Process'], 40.0)


if __name__ == '__main__':
    unittest.main()
