# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from erpnext import get_default_cost_center
from erpnext.accounts.utils import get_balance_on
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, fmt_money


class CashTransaction(Document):
	def before_save(self):
		self.unallocated_amount = self.get_unallocated_amount()
		self.unallocated_account = self.unallocated_account if self.unallocated_amount > 0 else None

	def before_validate(self):
		self.set_party_from_reference()

	def validate(self):
		self.set_title()
		self.validate_mandatory_fields()
		self.validate_unallocated_amount()

	def before_submit(self):
		self.unallocated_amount = self.get_unallocated_amount()
		self.unallocated_account = self.unallocated_account if self.unallocated_amount > 0 else None

	def on_submit(self):
		if self.unallocated_amount > 0 and not self.unallocated_account:
			frappe.throw(
				frappe._("Unallocated account is mandatory when unallocated amount is greater than zero")
			)
		self.create_journal_entry()
		self.show_success_message()

	def set_party_from_reference(self):
		"""
		Set party_type, party, party_name from reference (Sales/Purchase Invoice).
		Ensures they are set on save even when client-side async fetch hasn't completed.
		"""
		if self.type not in ("Pay", "Receive") or not self.reference_type or not self.reference_name:
			return
		if self.reference_type == "Sales Invoice":
			self.party_type = "Customer"
			self.party, self.party_name = frappe.db.get_value(
				"Sales Invoice", self.reference_name, ["customer", "customer_name"]
			)
		elif self.reference_type == "Purchase Invoice":
			self.party_type = "Supplier"
			self.party, self.party_name = frappe.db.get_value(
				"Purchase Invoice", self.reference_name, ["supplier", "supplier_name"]
			)

	def set_title(self):
		self.title = (self.party_name or self.type or "").strip()

	def validate_mandatory_fields(self):
		self._validate_reference_for_pay_receive()
		self._validate_bank_account_for_bank_types()
		if not self.amount or self.amount <= 0:
			frappe.throw(frappe._("Amount must be greater than zero"))

	def validate_unallocated_amount(self):
		"""
		Avoid that 100% is unallocated (for example, if there is no outstanding amount on the reference).
		"""
		if round(self.unallocated_amount, 2) == round(self.amount, 2):
			frappe.throw(frappe._("Unallocated amount cannot be 100% of the payment amount."))

	@frappe.whitelist()
	def get_unallocated_amount(self):
		"""
		Get the unallocated amount from the reference. Fallback: 0
		"""
		frappe.has_permission("Cash Transaction", ptype="write", throw=True)
		if not self.reference_type or not self.reference_name:
			return 0
		outstanding = frappe.db.get_value(self.reference_type, self.reference_name, "outstanding_amount")
		return flt(max(flt(self.amount) - abs(flt(outstanding)), 0))

	@frappe.whitelist()
	def check_unallocated_before_submit(self):
		"""Return whether unallocated amount has changed (for client confirm dialog)."""
		frappe.has_permission("Cash Transaction", ptype="write", throw=True)
		new_amount = self.get_unallocated_amount()
		if round(new_amount, 2) == round(flt(self.unallocated_amount), 2):
			return {"changed": False}
		currency, outstanding = frappe.db.get_value(
			self.reference_type, self.reference_name, ["currency", "outstanding_amount"]
		)
		msg = _("Unallocated amount has changed. Old: {0}, New: {1}. Outstanding: {2}.").format(
			fmt_money(self.unallocated_amount, currency=currency),
			fmt_money(new_amount, currency=currency),
			fmt_money(outstanding, currency=currency),
		)
		return {"changed": True, "message": msg}

	@frappe.whitelist()
	def update_unallocated_only(self):
		"""Update only unallocated_amount and unallocated_account (no submit)."""
		self.save()

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

		Amounts: paid (full amount), allocated (against invoice), unallocated (to unallocated account).
		For Pay/Receive with unallocated amount, the JE has three rows; otherwise two.
		"""
		je = frappe.new_doc("Journal Entry")

		# Journal Entry (parent level)
		remark = _(self.type)  # Default remark
		if self.reference_name and self.party_name:
			remark = f"{self.reference_name} ({self.party_name})"
			if self.reference_type == "Purchase Invoice" and (
				supplier_bill_no := frappe.db.get_value("Purchase Invoice", self.reference_name, "bill_no")
			):
				remark = f"{supplier_bill_no}, {remark}"

		je.update(
			{
				"voucher_type": "Cash Entry",
				"company": self.company,
				"posting_date": self.date,
				"is_system_generated": 1,
				"custom_cash_transaction": self.name,
				"remark": remark,
			}
		)

		# Journal Entry Accounts: paid (full amount), allocated (against invoice), unallocated (suspense)
		cost_center = self._get_cost_center()
		paid_amount = flt(self.amount)
		unallocated = flt(self.unallocated_amount, 2)
		allocated_amount = paid_amount - unallocated

		debit_account, credit_account = self._get_debit_credit_accounts()
		is_pay_receive_with_reference = (
			self.type in ("Pay", "Receive") and self.reference_type and self.reference_name
		)
		has_unallocated = is_pay_receive_with_reference and unallocated > 0 and self.unallocated_account

		if has_unallocated:
			# Against account gets allocated amount; cash/bank gets full paid amount; third row = unallocated
			if self.type == "Receive":
				debit_row = {
					"account": debit_account,
					"debit_in_account_currency": paid_amount,
					"cost_center": cost_center,
				}
				credit_row = {
					"account": credit_account,
					"credit_in_account_currency": allocated_amount,
					"cost_center": cost_center,
				}
				unallocated_row = {
					"account": self.unallocated_account,
					"credit_in_account_currency": unallocated,
					"cost_center": cost_center,
				}
			else:  # Pay
				debit_row = {
					"account": debit_account,
					"debit_in_account_currency": allocated_amount,
					"cost_center": cost_center,
				}
				credit_row = {
					"account": credit_account,
					"credit_in_account_currency": paid_amount,
					"cost_center": cost_center,
				}
				unallocated_row = {
					"account": self.unallocated_account,
					"debit_in_account_currency": unallocated,
					"cost_center": cost_center,
				}
			rows = [*self._add_reference_to_rows(debit_row, credit_row), unallocated_row]
		else:
			# Two rows: full amount on both sides
			debit_row = {
				"account": debit_account,
				"debit_in_account_currency": paid_amount,
				"cost_center": cost_center,
			}
			credit_row = {
				"account": credit_account,
				"credit_in_account_currency": paid_amount,
				"cost_center": cost_center,
			}
			rows = self._add_reference_to_rows(debit_row, credit_row)

		je.set("accounts", rows)

		# Insert and submit Journal Entry
		je.flags.skip_remarks_creation = True
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

	def show_success_message(self):
		"""
		Show an alert that shows:
		- Bank Withdrawal/Bank Deposit: Success message incl. new balance of the cash account.
		- Pay/Receive: Success message incl. what was allocated, what was unallocated, and what is the balance.
		"""
		balance = flt(
			get_balance_on(
				account=self.cash_account,
				date=self.date,
				company=self.company,
			),
			2,
		)
		currency = frappe.db.get_value("Account", self.cash_account, "account_currency")
		balance_fmt = fmt_money(balance, currency=currency)

		if self.type in ("Bank Withdrawal", "Bank Deposit"):
			title = _("{0} submitted").format(
				_(self.type),
			)
			msg = _("Cash account balance: {0}").format(
				balance_fmt,
			)
		else:
			allocated = flt(self.amount, 2) - flt(self.unallocated_amount, 2)
			allocated_fmt = fmt_money(allocated, currency=currency)
			unallocated_fmt = fmt_money(self.unallocated_amount, currency=currency)
			title = _("Cash Transaction submitted")
			msg = _(
				"Allocated: {0} on {1} ({2}).<br>Unallocated: {3} ({4}).<br>Cash account balance: {5}."
			).format(
				allocated_fmt,
				_(self.reference_type),
				self.reference_name,
				unallocated_fmt,
				self.unallocated_account,
				balance_fmt,
			)
		frappe.msgprint(msg, title=title, indicator="green")
