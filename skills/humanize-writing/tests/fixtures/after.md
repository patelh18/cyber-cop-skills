# Quarterly Security Review

## Summary

Vulnerability management kept most of our attention this quarter. We triaged 42 new CVEs, and that volume showed where our process was still slow. So the team automated the first pass of triage. Responses got faster.

The numbers are good. They don't mean we're finished, but they give us a solid base for next quarter.

## Findings

- We patched **CVE-2026-109619** in 3 days, down from 9 days last quarter.
- Dependency scanning now covers npm, PyPI and Composer, which closes the biggest gap we had.
- The [full report](https://example.com/report.pdf) has the details [1].

| Area | Status | Owner |
|---|---|---|
| Scanning | Running, wired into CI | Platform team |
| Patching | Tracked per service | SRE |

```bash
python3 scan.py --days 90
```

## Next steps

1. Extend coverage to Go modules by 2027-01-15.
2. Bring mean time to patch under 48 hours.

If people keep treating security as part of normal work, the platform gets safer without heroics. Run `status.py` weekly.

[1]: https://example.com/methodology
