# Copyright (c) 2026, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.utils import get_balance_on
from frappe import _
from frappe.utils import add_days, flt, getdate


def execute(filters=None):
	if not filters:
		return [], []

	validate_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def validate_filters(filters):
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date must be before To Date"))
	acc_type = frappe.get_cached_value("Account", filters.cash_account, "account_type")
	if acc_type != "Cash":
		frappe.throw(_("Account {0} is not a Cash account").format(filters.cash_account))


def get_columns():
	return [
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("ID"), "fieldname": "id", "fieldtype": "Data", "width": 140},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
		{"label": _("Title"), "fieldname": "title", "fieldtype": "Data", "width": 220},
		{"label": _("Type"), "fieldname": "type", "fieldtype": "Data", "width": 120},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"options": "account_currency",
			"width": 130,
		},
		{
			"label": _("Balance"),
			"fieldname": "balance",
			"fieldtype": "Currency",
			"options": "account_currency",
			"width": 130,
		},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 400},
	]


def get_data(filters):
	currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	opening = get_opening_balance(filters)
	gl_entries = get_gl_entries(filters)
	enrich_gl_entries_with_cash_transaction(gl_entries)

	data = []
	data.append(
		_make_row(
			title=_("Opening"),
			balance=opening,
			currency=currency,
			is_opening=True,
		)
	)

	running_balance = opening
	total_amount = 0

	for gle in gl_entries:
		amt = flt(gle.debit_in_account_currency or 0, 2) - flt(gle.credit_in_account_currency or 0, 2)
		running_balance += amt
		total_amount += amt
		status = _("Cancelled") if gle.is_cancelled else _("Submitted")
		# ID: Cash Transaction name if linked, else voucher_no (fallback)
		row_id = gle.ct_name or gle.voucher_no
		data.append(
			_make_row(
				id=row_id,
				date=gle.posting_date,
				title=gle.ct_title or "",
				type=gle.ct_type or "",
				amount=amt,
				balance=running_balance,
				remarks=gle.remarks or "",
				status=status,
				currency=currency,
			)
		)

	data.append(
		_make_row(
			title=_("Total"),
			amount=total_amount,
			currency=currency,
			is_total=True,
		)
	)
	data.append(
		_make_row(
			title=_("Closing (Opening + Total)"),
			balance=opening + total_amount,
			currency=currency,
			is_closing=True,
		)
	)

	for row in data:
		row["account_currency"] = currency

	return data


def get_opening_balance(filters):
	"""Opening balance of the cash account from GL (ERPNext standard)."""
	return flt(
		get_balance_on(
			account=filters.cash_account,
			date=add_days(filters.from_date, -1),
			company=filters.company,
		),
		2,
	)


def get_gl_entries(filters):
	"""GL entries for the cash account in date range (base = GL Entry)."""
	gle = frappe.qb.DocType("GL Entry")
	q = (
		frappe.qb.from_(gle)
		.select(
			gle.name.as_("gl_entry"),
			gle.posting_date,
			gle.account,
			gle.voucher_type,
			gle.voucher_no,
			gle.debit_in_account_currency,
			gle.credit_in_account_currency,
			gle.remarks,
			gle.is_cancelled,
		)
		.where(gle.company == filters.company)
		.where(gle.account == filters.cash_account)
		.where(gle.posting_date >= filters.from_date)
		.where(gle.posting_date <= filters.to_date)
		.orderby(gle.posting_date, order=frappe.qb.asc)
		.orderby(gle.creation, order=frappe.qb.asc)
	)
	if filters.get("submitted_only"):
		q = q.where(gle.is_cancelled == 0)
	if filters.get("title"):
		q = q.where(gle.remarks.like("%" + (filters.title or "").strip() + "%"))
	if filters.get("voucher_no"):
		q = q.where(gle.voucher_no == filters.voucher_no)
	if filters.get("amount") is not None and filters.get("amount") != "":
		try:
			amt = flt(filters.amount)
			# GL row is either debit or credit to cash account
			q = q.where((gle.debit_in_account_currency == amt) | (gle.credit_in_account_currency == amt))
		except (TypeError, ValueError):
			pass
	return q.run(as_dict=True)


def enrich_gl_entries_with_cash_transaction(gl_entries):
	"""When GL is from a Journal Entry linked to Cash Transaction, set ct_name, title, type."""
	je_voucher_nos = [e.voucher_no for e in gl_entries if e.voucher_type == "Journal Entry"]
	if not je_voucher_nos:
		for e in gl_entries:
			e["ct_name"] = None
			e["ct_title"] = ""
			e["ct_type"] = e.voucher_type or _("Other")
		return

	# Journal Entry -> custom_cash_transaction
	je_ct = frappe.db.sql(
		"""
		SELECT name AS voucher_no, custom_cash_transaction AS ct_name
		FROM `tabJournal Entry`
		WHERE name IN %(voucher_nos)s
		""",
		{"voucher_nos": je_voucher_nos},
		as_dict=1,
	)
	voucher_to_ct = {r.voucher_no: r.ct_name for r in je_ct if r.ct_name}
	ct_names = [v for v in voucher_to_ct.values() if v]
	ct_map = {}
	if ct_names:
		ct_rows = frappe.db.sql(
			"""
			SELECT name, title, type
			FROM `tabCash Transaction`
			WHERE name IN %(ct_names)s
			""",
			{"ct_names": ct_names},
			as_dict=1,
		)
		ct_map = {r.name: r for r in ct_rows}

	for e in gl_entries:
		ct_name = voucher_to_ct.get(e.voucher_no) if e.voucher_type == "Journal Entry" else None
		e["ct_name"] = ct_name
		if ct_name and ct_name in ct_map:
			e["ct_title"] = ct_map[ct_name].get("title") or ""
			e["ct_type"] = ct_map[ct_name].get("type") or ""
		else:
			e["ct_title"] = ""
			e["ct_type"] = e.voucher_type or _("Other")


def _make_row(
	id=None,
	date=None,
	title=None,
	type=None,
	amount=None,
	balance=None,
	remarks=None,
	status=None,
	currency=None,
	is_opening=False,
	is_total=False,
	is_closing=False,
):
	return {
		"status": status,
		"id": id,
		"date": date,
		"title": title or "",
		"type": type or "",
		"amount": amount,
		"balance": balance,
		"remarks": remarks or "",
		"is_total_row": is_total,
		"is_opening": is_opening,
		"is_closing": is_closing,
	}
