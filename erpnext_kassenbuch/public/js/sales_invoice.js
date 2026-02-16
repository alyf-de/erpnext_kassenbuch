// Copyright (c) 2025, ALYF GmbH and contributors
// Add "Create > Cash Transaction" on Sales Invoice (submitted, with outstanding).

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || flt(frm.doc.outstanding_amount) <= 0) {
			return;
		}
		if (!frappe.model.can_create("Cash Transaction")) {
			return;
		}
		frm.add_custom_button(
			__("Cash Transaction"),
			() => {
				frappe.new_doc("Cash Transaction", {
					type: "Receive",
					reference_type: "Sales Invoice",
					reference_name: frm.doc.name,
					company: frm.doc.company,
					party_type: "Customer",
					party: frm.doc.customer,
					party_name: frm.doc.customer_name,
					amount: frm.doc.outstanding_amount,
					date: frappe.datetime.get_today(),
				});
			},
			__("Create")
		);
	},
});
