# Moat 1 V2 limitations

- This is evidence and arithmetic attribution, not a complete accounting decomposition of core versus non-core earnings. Weighted positive non-core contribution retains its existing definition and calculation.
- Amount extraction intentionally requires narrow source and currency linkage. Uncertain or conflicting amounts are not estimated or assumed zero.
- Existing latest-10-K and cached annual sources are reused. No new historical filing collection or 10-Q fetching architecture was added. Multi-year evidence depends on available disclosures.
- Recurrence is observed history, not a prediction. Family grouping cannot guarantee full transaction/entity resolution or removal of every accounting overlap.
- Core revenue cannot establish a complete segment or revenue-quality decomposition. Missing evidence remains unknown. No new Core Revenue score is created.
- Tax-related working capital is unknown where no suitable source field exists. Tax paid is not a substitute.
- Legacy scoring and legacy narrative classifier behavior remain unchanged. V2 factual evidence revalidation is a separate diagnostic operation.
- Offline fixture outcomes are synthetic regression evidence, not current live conclusions about the seven companies. Six ticker fixtures lack a matching recorded balance-sheet response, so accrual evidence stays unavailable and failed independent requests may retry inherited loaders.
- Manual browser visual verification was not completed. Local server execution required permission that was rejected; opening rendered local HTML was blocked by browser URL security policy. Automated Flask route and HTML rendering checks passed for all seven Earnings Quality pages. No workaround was used.
