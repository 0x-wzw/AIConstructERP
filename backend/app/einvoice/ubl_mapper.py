"""Map a domain EInvoice (+ lines + issuer config) to a MyInvois UBL 2.1 JSON
document.

This is a STRUCTURAL scaffold: it emits the required top-level UBL blocks in the
shape MyInvois expects so submission can be exercised end-to-end. Full field
coverage (address sub-fields, tax exemption details, shipment, prepaid amounts,
allowance/charge, etc.) and the strict Aug-2026 validation rules are marked with
TODO and should be completed against the current SDK JSON schema before
production use:
    https://sdk.myinvois.hasil.gov.my/documents/invoice-v1-1/
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:  # avoid import cycle at runtime
    from .. import models


def _t(value: Any) -> List[Dict[str, Any]]:
    """MyInvois JSON wraps scalars as a single-element list of {"_": value}."""
    return [{"_": value}]


def _money(value: Any, currency: str = "MYR") -> List[Dict[str, Any]]:
    return [{"_": float(value or 0), "currencyID": currency}]


def _party(*, name: str, tin: str, reg_no: str, sst: str = "", msic: str = "",
           activity: str = "", email: str = "", city: str = "", state: str = "",
           country: str = "MYS") -> Dict[str, Any]:
    """A UBL Party block (used for both supplier and customer)."""
    party: Dict[str, Any] = {
        "PartyLegalEntity": [{"RegistrationName": _t(name)}],
        "PartyIdentification": [
            {"ID": [{"_": tin, "schemeID": "TIN"}]},
            {"ID": [{"_": reg_no, "schemeID": "BRN"}]},
        ],
        "PostalAddress": [{
            "CityName": _t(city),
            "PostalZone": _t(""),
            "CountrySubentityCode": _t(state),
            "Country": [{"IdentificationCode": [{"_": country, "listID": "ISO3166-1"}]}],
        }],
    }
    if sst:
        party["PartyIdentification"].append({"ID": [{"_": sst, "schemeID": "SST"}]})
    if msic:
        party["IndustryClassificationCode"] = [{"_": msic, "name": activity}]
    if email:
        party["Contact"] = [{"ElectronicMail": _t(email)}]
    return party


def build_document(
    invoice: "models.EInvoice",
    config: "models.MyInvoisConfig",
) -> Dict[str, Any]:
    """Return a MyInvois UBL 2.1 Invoice JSON document (single-invoice envelope)."""
    currency = invoice.currency or "MYR"
    issue_dt = invoice.invoice_date or invoice.created_at

    lines: List[Dict[str, Any]] = []
    for ln in sorted(invoice.lines, key=lambda x: x.line_no):
        lines.append({
            "ID": _t(str(ln.line_no)),
            "InvoicedQuantity": [{"_": float(ln.quantity or 0), "unitCode": ln.measurement or "C62"}],
            "LineExtensionAmount": _money(ln.subtotal, currency),
            "Item": [{
                "Description": _t(ln.description),
                "CommodityClassification": [
                    {"ItemClassificationCode": [{"_": ln.classification_code, "listID": "CLASS"}]}
                ],
            }],
            "Price": [{"PriceAmount": _money(ln.unit_price, currency)}],
            "TaxTotal": [{
                "TaxAmount": _money(ln.tax_amount, currency),
                "TaxSubtotal": [{
                    "TaxableAmount": _money(ln.subtotal, currency),
                    "TaxAmount": _money(ln.tax_amount, currency),
                    "TaxCategory": [{
                        "ID": _t(ln.tax_type or "E"),
                        "TaxScheme": [{"ID": [{"_": "OTH", "schemeID": "UN/ECE 5153"}]}],
                    }],
                }],
            }],
        })

    supplier = _party(
        name=invoice.vendor_name or config.business_activity or "Supplier",
        tin=invoice.supplier_tin or config.tin,
        reg_no=invoice.supplier_reg_no or config.registration_no,
        sst=invoice.supplier_sst or config.sst_no,
        msic=invoice.supplier_msic or config.msic_code,
        activity=config.business_activity,
        email=config.email, city=config.city, state=config.state_code,
        country=config.country_code or "MYS",
    )
    customer = _party(
        name=invoice.buyer_name or "Buyer",
        tin=invoice.buyer_tin,
        reg_no=invoice.buyer_reg_no,
    )

    document: Dict[str, Any] = {
        "_D": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "_A": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "_B": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "Invoice": [{
            "ID": _t(invoice.invoice_no),
            "IssueDate": _t(issue_dt.strftime("%Y-%m-%d") if issue_dt else ""),
            "IssueTime": _t(issue_dt.strftime("%H:%M:%SZ") if issue_dt else ""),
            "InvoiceTypeCode": [{"_": invoice.document_type or "01",
                                 "listVersionID": invoice.document_version or "1.1"}],
            "DocumentCurrencyCode": _t(currency),
            "AccountingSupplierParty": [{"Party": [supplier]}],
            "AccountingCustomerParty": [{"Party": [customer]}],
            "InvoiceLine": lines,
            "TaxTotal": [{"TaxAmount": _money(invoice.tax_amount, currency)}],
            "LegalMonetaryTotal": [{
                "LineExtensionAmount": _money(invoice.subtotal, currency),
                "TaxExclusiveAmount": _money(invoice.subtotal, currency),
                "TaxInclusiveAmount": _money(invoice.total_amount, currency),
                "PayableAmount": _money(invoice.total_amount, currency),
            }],
            # TODO: exchange rate block (mandatory when currency != MYR),
            # BillingReference for credit/debit/refund notes, and the
            # cryptographic Signature block (added by signer.py).
        }],
    }
    return document
