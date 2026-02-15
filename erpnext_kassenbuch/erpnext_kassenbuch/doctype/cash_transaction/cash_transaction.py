# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.utils import get_default_cost_center
from frappe.model.document import Document
from frappe.utils import flt


class CashTransaction(Document):
	def validate(self):
		self.set_title()
		self.validate_mandatory_fields()

	def on_submit(self):
		self.create_journal_entry()

	def set_title(self):
		self.title = (self.party_name or self.type or "").strip()

	def validate_mandatory_fields(self):
		self._validate_reference_for_pay_receive()
		self._validate_bank_account_for_bank_types()
		if not self.cash_account:
			frappe.throw(frappe._("Cash Account is mandatory"))
		if not self.amount or self.amount <= 0:
			frappe.throw(frappe._("Amount must be greater than zero"))

	def _validate_reference_for_pay_receive(self):
		if self.type in ("Pay", "Receive"):
			if not self.reference_type or not self.reference_name:
				frappe.throw(frappe._("Reference Type and Name are mandatory for type {0}").format(self.type))

	def _validate_bank_account_for_bank_types(self):
		if self.type in ("Bank Withdrawal", "Bank Deposit"):
			if not self.bank_account:
				frappe.throw(frappe._("Bank Account is mandatory for type {0}").format(self.type))

	def create_journal_entry(self):
		"""
		Create a Journal Entry for the Cash Transaction.
		"""
		je = frappe.new_doc("Journal Entry")

		# Journal Entry (parent level)
		je.update(
			{
				"voucher_type": "Cash Entry",
				"company": self.company,
				"posting_date": self.date,
				"is_system_generated": 1,
				"custom_cash_transaction": self.name,
				"remark": f"Cash Transaction: {self.name} ({self.type})",
			}
		)

		# Journal Entry Accounts (child level, account rows)
		cost_center = self._get_cost_center()
		amount = flt(self.amount)
		debit_account, credit_account = self._get_debit_credit_accounts()
		debit_row = {
			"account": debit_account,
			"debit_in_account_currency": amount,
			"cost_center": cost_center,
		}
		credit_row = {
			"account": credit_account,
			"credit_in_account_currency": amount,
			"cost_center": cost_center,
		}
		rows = self._add_reference_to_rows(debit_row, credit_row)
		je.set("accounts", rows)

		# Insert and submit Journal Entry
		je.insert(ignore_permissions=True)
		je.submit()

	def _get_cost_center(self):
		cost_center = None
		if self.reference_type and self.reference_name:
			cost_center = frappe.db.get_value(self.reference_type, self.reference_name, "cost_center")
		if not cost_center:
			cost_center = self.get("cost_center") or get_default_cost_center(self.company)
		return cost_center

	def _get_against_account(self):
		"""Account to post against (invoice receivable/payable or bank)."""
		if self.reference_type == "Purchase Invoice" and self.reference_name:
			return frappe.db.get_value("Purchase Invoice", self.reference_name, "credit_to")
		if self.reference_type == "Sales Invoice" and self.reference_name:
			return frappe.db.get_value("Sales Invoice", self.reference_name, "debit_to")
		if self.type in ("Bank Withdrawal", "Bank Deposit"):
			return self.bank_account
		return None

	def _get_debit_credit_accounts(self):
		"""Return (debit_account, credit_account) for the two JE rows."""
		against = self._get_against_account()
		cash = self.cash_account
		bank = self.bank_account
		if self.type == "Pay":
			return (against, cash)  # debit payable, credit cash
		if self.type == "Receive":
			return (cash, against)  # debit cash, credit receivable
		if self.type == "Bank Withdrawal":
			return (cash, bank)
		if self.type == "Bank Deposit":
			return (bank, cash)
		return (None, None)

	def _add_reference_to_rows(self, debit_row, credit_row):
		if not self.reference_type or not self.reference_name:
			return [debit_row, credit_row]
		if self.reference_type == "Purchase Invoice":
			debit_row["reference_type"] = "Purchase Invoice"
			debit_row["reference_name"] = self.reference_name
			debit_row["party_type"] = self.party_type
			debit_row["party"] = self.party
		if self.reference_type == "Sales Invoice":
			credit_row["reference_type"] = "Sales Invoice"
			credit_row["reference_name"] = self.reference_name
			credit_row["party_type"] = self.party_type
			credit_row["party"] = self.party
		return [debit_row, credit_row]
