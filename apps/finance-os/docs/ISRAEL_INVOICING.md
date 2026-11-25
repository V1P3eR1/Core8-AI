# Israel-compliant fiscal documents — implementation research 2026-11-22

## Core rule
Stripe-issued payment/invoice records are not by themselves proven to satisfy Israeli local bookkeeping rules. Never label a Stripe document as an Israeli tax invoice/receipt without validation against Israel Tax Authority requirements and the business's legal and tax registration.

## Israel Invoices allocation numbers
The Israel Tax Authority states that from June 1, 2026 an allocation number is needed for a taxable invoice whose pre-VAT amount **exceeds NIS 5,000** under the applicable business-to-business input VAT framework. Verify the customer's classification, precise document type, threshold logic, and exceptions with the accountant. No allocation number may be invented or inferred.
Sources:
- https://www.gov.il/he/pages/pa240525-1
- https://www.gov.il/he/service/request-assignment-number-for-tax-invoice
- https://www.gov.il/he/service/verify-vendor-invoice-information

## Candidate integration
Morning (formerly GreenInvoice) advertises API/webhooks and integration with Israel Invoices. Its official product page: https://www.greeninvoice.co.il/pricing/
Validate contractual pricing, API access tier, sandbox credentials, exact tax-document lifecycle and failure recovery before procurement. Compare iCount and alternatives before choosing. No provider contract or subscription authorized.

## Draft workflow (not implemented)
Stripe checkout or billing event -> verified/sandbox event inbox -> map to immutable internal payment record -> reconcile gross/tax/fees/currency -> create *draft document request* -> CPA-approved Israeli provider issues fiscal document (with allocation number when required) -> attach official document reference to the transaction -> client delivery with audit trail.

No invoice should be issued twice on Stripe webhook retries. Introduce a unique provider document idempotency reference and manual exception queue. VAT rates, exemptions, withholding, customer location and foreign sales must not be guessed.

## Unresolved decisions requiring Lev + accountant
- Legal entity receiving payments and its registered head-office address.
- Registration (authorized dealer / company / other), Israeli VAT and invoicing requirements.
- Provider selection and whether a separate accounting system must be the ledger of record.
- Rules for USD sales to US customers vs local Israeli customers.
- Salary employees vs contractors and payroll software selection.
