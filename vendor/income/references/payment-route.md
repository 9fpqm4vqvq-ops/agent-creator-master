# Iraq payout-route verification — six mandatory stages

Before labeling a pathway VERIFIED, document evidence **for the user's actual eligible residence and account type** at every step:

1. `customer_payment`: Can the real buyer pay for this offer using a legal supported method?
2. `platform_receipt`: Does the marketplace/merchant system accept these payments for this merchant/resident?
3. `withdrawable_balance`: Do legitimate earnings settle, clear reserves, and become withdrawable?
4. `payout_provider`: Can an allowed provider receive payouts for this person's eligible location/currency?
5. `iraqi_account`: Can the individual legitimately maintain and receive funds in an accessible account/bank in Iraq?
6. `usable_funds`: Can the person convert, spend, or withdraw actual funds legally after exchange and fees?

For each stage: `VERIFIED | UNVERIFIED | BLOCKED`, provider name, checked date, current primary source URL (not merely homepage), relevant geographic/personal conditions, actual fee/minimum, uncertainty. The CLI requires an evidence URL to enter VERIFIED, but **a URL alone does NOT prove the claim**; independent QA must read and verify its contents. Verify end-to-end rather than assuming platform signup implies cash-out. The exact local bank and KYC facts may require the user's voluntary confirmation; don't collect account numbers or ID documents in reports.

If stage is UNVERIFIED or BLOCKED → HOLD, no READY or user-facing income recommendation. Do not recommend using third-country residence, borrowed accounts, fake addresses, or evasive VPNs. Rules can change at any time. No country eligibility table in this template is asserted as current fact.
