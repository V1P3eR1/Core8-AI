import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ledger import DraftJournal, JournalLine, draft_journal, validate_draft

class DraftJournalTests(unittest.TestCase):
    def test_balanced(self):
        v=draft_journal("sandbox-demo","ILS",(JournalLine("100",debit_minor=12000),JournalLine("400",credit_minor=12000)))
        self.assertEqual(v.currency,"ILS")
    def test_imbalanced(self):
        with self.assertRaises(ValueError):
            draft_journal("id","ILS",(JournalLine("100",debit_minor=12000),JournalLine("400",credit_minor=12001)))
    def test_float_rejected(self):
        with self.assertRaises(ValueError):
            draft_journal("id","ILS",(JournalLine("100",debit_minor=100.10),JournalLine("400",credit_minor=100)))
    def test_bool_rejected(self):
        with self.assertRaises(ValueError):
            draft_journal("id","USD",(JournalLine("100",debit_minor=True),JournalLine("400",credit_minor=1)))
    def test_cross_currency_not_implicit(self):
        with self.assertRaises(ValueError):
            draft_journal("id","XYZ",(JournalLine("100",debit_minor=100),JournalLine("400",credit_minor=100)))
    def test_one_sided_entry_denied(self):
        with self.assertRaises(ValueError):
            draft_journal("id","ILS",(JournalLine("100",debit_minor=10,credit_minor=10),JournalLine("400",credit_minor=10)))
    def test_zero_entry_denied(self):
        with self.assertRaises(ValueError):
            draft_journal("id","USD",(JournalLine("100"),JournalLine("400")))
    def test_empty_reference_denied(self):
        with self.assertRaises(ValueError):
            draft_journal("","ILS",(JournalLine("100",debit_minor=1),JournalLine("400",credit_minor=1)))
if __name__=="__main__":unittest.main()
