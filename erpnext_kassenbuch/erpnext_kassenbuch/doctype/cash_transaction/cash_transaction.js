// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cash Transaction", {
	refresh(frm) {
		frm.add_custom_button(__("Cash Book"), function () {
			const filters = {};
			if (frm.doc.cash_account) filters.cash_account = frm.doc.cash_account;
			if (frm.doc.company) filters.company = frm.doc.company;
			frappe.set_route("query-report", "Cash Book", filters);
		});
	},

	onload(frm) {
		frm.set_query("reference_name", function () {
			if (!frm.doc.reference_type) return {};
			const filters = { docstatus: 1, outstanding_amount: ["!=", 0] };
			if (frm.doc.company) {
				filters.company = frm.doc.company;
			}
			return { filters };
		});
		frm.set_query("unallocated_account", function () {
			const filters = { is_group: 0 };
			if (frm.doc.company) {
				filters.company = frm.doc.company;
			}
			return { filters };
		});
	},

	before_submit(frm) {
		return new Promise((resolve) => {
			if (
				!["Pay", "Receive"].includes(frm.doc.type) ||
				!frm.doc.reference_type ||
				!frm.doc.reference_name
			) {
				resolve();
				return;
			}
			frappe
				.call({
					method: "check_unallocated_before_submit",
					doc: frm.doc,
				})
				.then((r) => {
					if (r.exc || !r.message || !r.message.changed) {
						resolve();
						return;
					}
					const data = r.message;
					frappe.confirm(
						data.message + "\n\n" + __("Accept and submit anyway?"),
						() => {
							frm.doc.accept_unallocated_change = 1;
							resolve();
						},
						() => {
							frappe.validated = false;
							frappe
								.call({ method: "update_unallocated_only", doc: frm.doc })
								.then(() => frm.reload_doc());
							resolve();
						}
					);
				});
		});
	},

	type(frm) {
		if (frm.doc.type === "Pay") {
			frm.set_value("reference_type", "Purchase Invoice");
		} else if (frm.doc.type === "Receive") {
			frm.set_value("reference_type", "Sales Invoice");
		}
		frm.set_value("reference_name", "");
		frm.set_value("party_type", "");
		frm.set_value("party", "");
		frm.set_value("party_name", "");
	},

	amount(frm) {
		update_unallocated_amount(frm);
	},

	reference_name(frm) {
		if (!frm.doc.reference_type || !frm.doc.reference_name) {
			frm.set_value("party_type", "");
			frm.set_value("party", "");
			frm.set_value("party_name", "");
			frm.set_value("unallocated_amount", 0);
			return;
		}
		update_unallocated_amount(frm);
		if (frm.doc.reference_type === "Sales Invoice") {
			frappe.db.get_value(
				"Sales Invoice",
				frm.doc.reference_name,
				["customer", "customer_name"],
				(r) => {
					if (r) {
						frm.set_value("party_type", "Customer");
						frm.set_value("party", r.customer);
						frm.set_value("party_name", r.customer_name);
					}
				}
			);
		} else if (frm.doc.reference_type === "Purchase Invoice") {
			frappe.db.get_value(
				"Purchase Invoice",
				frm.doc.reference_name,
				["supplier", "supplier_name"],
				(r) => {
					if (r) {
						frm.set_value("party_type", "Supplier");
						frm.set_value("party", r.supplier);
						frm.set_value("party_name", r.supplier_name);
					}
				}
			);
		}
	},
});

function update_unallocated_amount(frm) {
	if (
		!frm.doc.amount ||
		!frm.doc.reference_type ||
		!frm.doc.reference_name ||
		!["Pay", "Receive"].includes(frm.doc.type)
	) {
		return;
	}
	frappe.call({
		method: "get_unallocated_amount",
		doc: frm.doc,
		callback(r) {
			if (r.message != null) {
				frm.set_value("unallocated_amount", r.message);
				if (flt(r.message) === 0) {
					frm.set_value("unallocated_account", "");
				}
			}
		},
	});
}
