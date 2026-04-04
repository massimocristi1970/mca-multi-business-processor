import io
import json
import os
import tempfile
import unittest
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

    def test_credit_expense_keyword_is_not_forced_to_expenses(self):
        category = app.map_transaction_category({
            'name': 'HMRC VAT REFUND',
            'merchant_name': '',
            'amount': -125.0,
            'personal_finance_category.detailed': '',
        })

        self.assertNotEqual(category, 'Expenses')

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
