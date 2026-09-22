# CRTC Financial Intelligence Roadmap

## Objective
Connect CRTC to the owner's financial picture without putting banking or payment secrets in the client.

## Architecture

CRTC Android UI → secure backend → bank/payment provider → normalized financial events → Financial Brain → acquisition decision.

## Bank layer
- Plaid Link for user-authorized account connection.
- Start read-only: balances and transactions.
- Keep Plaid client secret server-side.
- Normalize transactions before feeding the Financial Brain.

## Payment layer
- Venmo/PayPal as a payment channel where supported by the merchant integration.
- Normalize completed payments and fees into `PaymentEvent` records.
- Never treat a payment as completed from client-side UI alone; verify server-side/provider status.

## CRTC decision loop
FIND → IDENTIFY → VALUE → MAX BID → CHECK CASH → BUY/PASS → TRACK → LIST → SELL → RECEIVE PAYMENT → MEASURE PROFIT → LEARN

## Safety rules
- Do not store banking credentials.
- Do not expose provider secrets in Streamlit/client JavaScript.
- Do not move money until a separate, explicitly authorized transfer workflow is implemented.
- Unknown cash obligations reduce the safe buying budget rather than being ignored.

## Current implementation
`financial_intelligence.py` provides the provider-neutral cash and transaction logic.
`payments_adapter.py` provides the normalized payment-event contract.
Provider credentials and production API wiring remain deployment configuration, not source code.
