# Risk Analysis – edgar-crawler Integration

- Portfolio state import lacks ES metric; advise sourcing full state before production go-live to enforce 2.5% ES constraint.
- External dependency introduces supply chain risk; mitigate via checksum pinning and internal mirror.
- Temporary file workflow must ensure filings containing MNPI are deleted immediately; consider in-memory patch for future hardening.
- Regression surface: inline XBRL permutations, broken headers (e.g., "I T E M 1 A"), legacy TXT filings. Require automated tests before replacing existing parser.
