# CRTC AI + Paid API Cost Control Plan

Status: LOCKED PRODUCT DIRECTION — 2026-09-20

## Core rule

CRTC should always attempt the least-expensive reliable source first before invoking a paid AI/API operation.

Priority order:

1. Existing user-supplied data and local application data
2. Existing cached/computed CRTC data
3. Free/low-cost marketplace or public APIs where permitted
4. Deterministic CRTC calculations and rules
5. Paid AI/API calls only when they add information or reasoning that the cheaper sources cannot provide

The application must never call a paid provider merely because AI is available.

## AI Analyzer input modes

All three are valid:

- Photo only
- Description only
- Photo + description

Multiple photos are supported for one item.

Standard interactive cap:

- 6 photos maximum per item
- 4 photos recommended for normal use

One item with multiple photos should normally be one AI analysis/request, not one request per photo.

## AI Analyzer workflow

Separate expensive operations:

### Standard analysis

Identify item, estimate condition/value, confidence, and reasoning.

### Listing generation

Only run when the user asks for listing drafts. Do not automatically generate eBay/Facebook/Mercari drafts during every valuation.

### Deep analysis

Optional higher-cost operation for uncertain/high-value items.

## Batch / estate workflow

Large collections must not be treated as one giant interactive request.

Example:

500-item estate lot
-> cheap deterministic screening
-> identify 25-100 items worth deeper analysis
-> process selected items in controlled batches
-> show progressive completion
-> never leave the UI appearing frozen

Future optimization: use provider batch processing when latency is acceptable and the discount is advantageous.

## AI credits

CRTC will use an internal AI-credit system rather than exposing raw token economics to customers.

Initial conceptual weights:

- Description-only analysis: 1 credit
- 1 photo: 1 credit
- 2-3 photos: 2 credits
- 4-6 photos: 3 credits
- Listing generation: 1 credit
- Deep analysis: 3-5 credits
- Batch analysis: calculated from actual work

Final credit amounts and subscription allowances remain subject to measured production token usage.

## Mandatory spend controls

Before every paid AI/API call:

1. Verify entitlement
2. Verify remaining credits
3. Enforce per-user daily limit
4. Enforce monthly limit
5. Enforce platform-wide AI/API budget
6. Reserve usage
7. Make provider request
8. Consume reservation on success
9. Release/refund reservation on failure

Also provide a global emergency kill switch for paid AI operations.

The application must never allow a retry loop, malformed request, or abusive user to create an uncontrolled provider bill.

## Cost-source routing

Every paid integration should have a documented cost policy.

Examples:

- eBay: use permitted API data/cached data before AI; respect API limits and licensing.
- Anthropic: use AI only when cheaper/reliable data cannot answer the question.
- Stripe: payment processing costs are treated as transaction/revenue costs, not AI usage. Do not confuse Stripe processing fees with API inference spend.

## Planning forecast

These are budgeting scenarios, not guarantees.

Using current Anthropic Sonnet 5 pricing of $2/M input tokens and $10/M output tokens, plus conservative overhead for image requests/retries, CRTC should budget roughly $0.01-$0.03 per normal AI item analysis until real production telemetry establishes the actual figure.

Illustrative AI-spend ranges:

| Scale | Approx. AI analyses/month | Planning AI spend/month | Planning AI spend/year |
|---|---:|---:|---:|
| Early beta | 2,500-10,000 | $50-$300 | $600-$3,600 |
| 1,000 active users | 25,000-100,000 | $250-$3,000 | $3,000-$36,000 |
| 5,000 active users | 125,000-500,000 | $1,250-$15,000 | $15,000-$180,000 |
| 10,000 active users | 250,000-1,000,000 | $2,500-$30,000 | $30,000-$360,000 |
| 50,000 active users | 1.25M-5M | $12,500-$150,000 | $150,000-$1.8M |

These ranges intentionally include a wide safety margin. Actual cost should be driven down through source-first routing, caching, batching, smaller outputs, selective deep analysis, and measured usage.

## Recommended cash reserve

Do not keep a huge API balance merely because the business might grow.

Start with a controlled provider budget and increase it based on measured paid usage.

Suggested operational reserve:

- Beta: $100-$300
- First 1,000 active users: $1,000-$3,000
- 5,000 active users: $3,000-$10,000
- Larger scale: fund from a fixed percentage of collected subscription revenue and enforce a hard monthly provider budget

These are operating-reserve targets, not expected monthly spend.

## Enterprise

Enterprise should receive generous usage, not unlimited uncontrolled usage.

Potential future options:

- Large included credit pool
- Batch processing
- Higher daily limits
- Priority processing
- Optional BYO API key for very high-volume customers

BYO API key is a future enterprise feature and requires secure credential handling, clear billing semantics, and support boundaries.

## Pricing architecture principle

Do not advertise token counts.

Customers should see:

AI credits remaining
Included usage
Optional credit packs/overage
Clear usage limits

The goal is to make CRTC feel generous while ensuring CRTC's maximum provider liability is always bounded.

## Implementation gate

Do not finalize subscription AI-credit quantities until the production Analyzer is instrumented to record:

- request type
- number of images
- image dimensions/bytes
- input tokens
- output tokens
- provider/model
- latency
- success/failure
- retry count
- estimated provider cost
- credits reserved/consumed/refunded

Once telemetry exists, calculate real P50/P90/P99 cost per analysis and set plan limits from those measurements.

This document is the locked product/architecture direction. Implementation should be done as a controlled engineering task, with tests and verification, rather than by making unrelated changes to the beta.
