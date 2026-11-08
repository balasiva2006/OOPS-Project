"""Configuration checks that do not require a database server."""
import os
import unittest
from unittest.mock import patch

from hmc_system import create_app
from hmc_system.transactions import Bill
from hmc_system.utilities.validation import money


class ConfigurationTests(unittest.TestCase):
    def test_missing_database_url_has_clear_error(self):
        with patch.dict(os.environ, {}, clear=True), patch('hmc_system.web.application.load_dotenv'):
            with self.assertRaisesRegex(RuntimeError, 'DATABASE_URL'):
                create_app()

    def test_missing_session_key_has_clear_error(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://unused'}, clear=True), patch('hmc_system.web.application.load_dotenv'):
            with self.assertRaisesRegex(RuntimeError, 'HMC_SECRET_KEY'):
                create_app()

    def test_factory_and_static_assets_need_no_database_connection(self):
        with patch('psycopg.connect') as connect:
            app = create_app({'DATABASE_URL': 'postgresql://unused', 'SECRET_KEY': 'test-only', 'TESTING': True})
            client = app.test_client()
            self.assertEqual(client.get('/').status_code, 200)
            with client.get('/static/css/style.css') as response:
                self.assertEqual(response.status_code, 200)
            for name in app.jinja_env.list_templates():
                app.jinja_env.get_template(name)
            connect.assert_not_called()

    def test_hosted_sessions_use_secure_cookie(self):
        with patch.dict(os.environ, {'VERCEL': '1'}):
            app = create_app({'DATABASE_URL': 'postgresql://unused', 'SECRET_KEY': 'test-only'})
            self.assertTrue(app.config['SESSION_COOKIE_SECURE'])
            self.assertEqual(app.config['MAX_CONTENT_LENGTH'], 4 * 1024 * 1024)

    def test_money_and_bill_properties(self):
        bill = Bill(1, money('1500'), money('2500'), money('300'), money('3000'))
        self.assertEqual(bill.total, 430000)
        self.assertEqual(bill.balance, 130000)
        for invalid in ('-1', 'NaN', 'Infinity', '0.001'):
            with self.assertRaises(ValueError):
                money(invalid)
