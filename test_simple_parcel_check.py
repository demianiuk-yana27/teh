import unittest
from datetime import date
from simple_parcel_check import request_date, order_id

class SimpleParcelTests(unittest.TestCase):
    def test_dates(self):
        for value in ("27.11", "27.11.2026", "2026-11-27", "2026-11-26T23:16:57.321Z"):
            self.assertEqual(request_date(value), date(2026,11,27))
        self.assertEqual(request_date("2026-11-26T20:16:57.321Z"), date(2026,11,26))
        self.assertIsNone(request_date("31.11"))
        self.assertIsNone(request_date(""))
    def test_ids(self):
        self.assertEqual(order_id(339924103.0), "339924103")
        self.assertEqual(order_id(" 339924103 "), "339924103")
        self.assertEqual(order_id("abc339924103"), "")

    def test_inclusive_range(self):
        since, until = date(2026,11,18), date(2026,11,27)
        for value in ("18.11", "22.11.2026", "2026-11-26T23:16:57.321Z"):
            self.assertTrue(since <= request_date(value) <= until)
        self.assertFalse(since <= request_date("28.11") <= until)
