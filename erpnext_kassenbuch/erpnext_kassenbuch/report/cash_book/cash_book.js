// Copyright (c) 2026, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.query_reports["Cash Book"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			on_change: function () {
				const company = frappe.query_report.get_filter_value("company");
				if (company) {
					frappe.db.get_value("Company", company, "default_cash_account", (r) => {
						if (r && r.default_cash_account) {
							frappe.query_report.set_filter_value(
								"cash_account",
								r.default_cash_account
							);
						} else {
							frappe.query_report.set_filter_value("cash_account", "");
						}
					});
				}
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "cash_account",
			label: __("Cash Account"),
			fieldtype: "Link",
			options: "Account",
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				if (!company) return {};
				return {
					filters: {
						company: company,
						account_type: "Cash",
						is_group: 0,
					},
				};
			},
			reqd: 1,
		},
		{
			fieldname: "title",
			label: __("Title"),
			fieldtype: "Data",
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher No"),
			fieldtype: "Data",
		},
		{
			fieldname: "amount",
			label: __("Amount"),
			fieldtype: "Currency",
		},
		{
			fieldname: "submitted_only",
			label: __("Submitted Only"),
			fieldtype: "Check",
			default: 1,
		},
	],
	onload: function (report) {
		// Set default cash account from company when report loads
		const company = report.get_filter_value("company");
		if (company) {
			frappe.db.get_value("Company", company, "default_cash_account", (r) => {
				if (r && r.default_cash_account) {
					report.set_filter_value("cash_account", r.default_cash_account);
				}
			});
		}
	},
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (
			column.fieldname === "amount" &&
			data &&
			!data.is_total_row &&
			!data.is_opening &&
			!data.is_closing
		) {
			const num = parseFloat(data.amount);
			if (num > 0) {
				return '<span style="color: green;">' + value + "</span>";
			}
			if (num < 0) {
				return '<span style="color: red;">' + value + "</span>";
			}
		}
		return value;
	},
};
