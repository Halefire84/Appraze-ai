# Appraze AI Usage Controls

Appraze uses Cooper River Trading Co.'s server-side Anthropic credential. Customer provider keys are not part of the standard product.

## Beta limits

- Paid customer: 100 successful AI calls per calendar month, 10 per calendar day.
- Owner/admin: 500 successful AI calls per month, 25 per day.
- Reservations are atomic in the Apps Script backend and expire after 15 minutes if abandoned.
- Successful calls record actual input/output tokens and estimated provider cost.
- AI access is denied for accounts that are not marked paid in the Users sheet.
- Image input is capped at 3 MB and text descriptions at 2,000 characters.

## Cost accounting

The current AI Analyzer uses claude-sonnet-5. Cost accounting uses Anthropic's published standard rates of $2 per million input tokens and $10 per million output tokens. The account-level usage sheet stores token totals and estimated USD spend.

These figures are application accounting estimates; Anthropic's actual invoice/console usage remains the billing authority.

## Security behavior

- The Anthropic key is read only by server-side Streamlit code.
- The browser never receives the key.
- Provider error response bodies are not shown to customers.
- A quota denial happens before an Anthropic request.
- Network/API failures release the reservation where no provider response was received.
- Deterministic Appraze functionality continues when AI is unavailable.
- BYO Anthropic keys are explicitly out of scope for the current beta.