# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CashTransaction(Document):
	def validate(self):
		self.set_title()
		self.validate_mandatory_fields()

	def set_title(self):
		self.title = (self.party_name or self.type or "").strip()

	def validate_mandatory_fields(self):
		self._validate_reference_for_pay_receive()
		self._validate_bank_account_for_bank_types()

	def _validate_reference_for_pay_receive(self):
		if self.type in ("Pay", "Receive"):
			if not self.reference_type or not self.reference_name:
				frappe.throw(frappe._("Reference Type and Name are mandatory for type {0}").format(self.type))

	def _validate_bank_account_for_bank_types(self):
		if self.type in ("Bank Withdrawal", "Bank Deposit"):
			if not self.bank_account:
				frappe.throw(frappe._("Bank Account is mandatory for type {0}").format(self.type))
