# Finance OS — Owner inputs required for compliant launch

These are **decisions, not credentials**. Do not paste secrets, banking numbers,
ID numbers, employee salary data or tax returns into GitHub.

## Needed from Lev (no paid services or real financial actions without approval)

- **Legal entity:** confirm whether Core8-AI collects funds as Israeli sole proprietorship/company or an overseas entity, and the country of registration. Share only entity type and country in the public issue; provide sensitive fields through a secured provider onboarding channel.
- **Tax adviser and invoicing:** select an Israeli accountant and decide between approved fiscal document issuer providers after comparing pricing, API and official invoice allocation support.
- **Currencies / sale types:** confirm which of ILS/USD/EUR to offer for (a) SaaS monthly subscriptions, (b) project setup fees, (c) enterprise invoices. Prices remain blank until approved.
- **Salary:** confirm whether first phase includes salaried employees, independent contractors, or neither; choose a local payroll provider if needed.
- **Cloud:** approve a separate encrypted, private sandbox deployment destination, secrets management and budget. Public Core8-AI GitHub must hold no live financial information.
- **Approval policy:** assign at least one human reviewer for billing, refunds, payroll, tax filings and deployment; use dual control for high-value refunds or bank detail changes.

## System-prepared work — no user action needed yet

1. Sandbox-only webhook intake/signature/dedup/worker in PR #64.
2. Sandbox CI policy tests + real disposable PostgreSQL integration test.
3. Draft journal validation and draft Checkout intent validation.
4. Implement protected backend integrations after tenant auth is finalized.
5. Determine Israel document API, invoice allocation and payroll system integration details with chosen providers.

## Explicit gate
A pass in CI is **not** evidence that actual Stripe payments were collected.
The system cannot be called completed until real sandbox end-to-end tests,
audit trail, accounting reconciliation and professional fiscal checks succeed.
