# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def before_submit(doc, method=None):
	if doc.custom_cash_transaction or frappe.db.get_single_value(
		"Cash Transaction Settings", "allow_manual_journal_entries"
	):
		return
	if any(frappe.db.get_value("Account", row.account, "account_type") == "Cash" for row in doc.accounts):
		frappe.throw(
			_(
				"Journal Entries that include a Cash Account have to be created via the <b>Cash Transaction</b> doctype. Alternatively you can activate the <i>Allow manual Journal Entries</i> setting in the <b>Cash Transaction Settings</b>."
			)
		)


def on_cancel(doc, method=None):
	if doc.custom_cash_transaction:
		cancel_cash_transaction(doc.custom_cash_transaction)


def cancel_cash_transaction(cash_transaction_id):
	"""When a Journal Entry is cancelled, cancel the linked Cash Transaction if any."""
	if not frappe.db.exists("Cash Transaction", {"name": cash_transaction_id, "docstatus": 1}):
		return
	ct = frappe.get_doc("Cash Transaction", cash_transaction_id)
	frappe.msgprint(
		_("Linked Cash Transaction {0} was automatically cancelled as well.").format(ct.name), alert=True
	)
	ct.cancel()
