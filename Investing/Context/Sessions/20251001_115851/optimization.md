# Optimization Notes – Section Parser

- Wrapper should reuse existing OpenBB caching to avoid redundant downloads.
- Consider async `to_thread` execution to keep MCP event loop responsive.
- Batch requested section filtering post-extraction to minimize repeated parsing cost.
- Monitor memory footprint when processing large 10-K filings; stream chunking after JSON extraction to respect MCP token caps.
