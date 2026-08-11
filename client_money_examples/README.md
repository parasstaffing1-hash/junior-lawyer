# Client-money examples

These examples exercise the Batch 13 finance API without assuming any jurisdiction-specific trust-account rule.

Recommended sequence:

1. Create a client-money account.
2. Post a client receipt.
3. Create a transfer-to-fees request.
4. Have a different authorized user approve it when `require_separate_approver=true`.
5. Execute the transfer.
6. Create and independently review a reconciliation.

The application ledger is a control foundation, not a certification that a firm's professional-account rules have been satisfied.
