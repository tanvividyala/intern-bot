# intern-bot

Polls target companies' ATS job boards and pings Discord when a new internship listing appears.

## How it works

- `config.yaml` lists companies, each pointing at an ATS and slug (plus a few ATS-specific fields — see below)
- `adapters/` fetches and normalizes job listings per ATS, including a best-effort US-location detection
  (`adapters/us_location.py`) used when `us_only: true` is set in config
- `main.py` filters titles against `keywords`, filters by location if `us_only` is set, diffs against
  `state/seen_jobs.json`, and sends a Discord notification for anything new
- `.github/workflows/check-listings.yml` runs this on a schedule via GitHub Actions and commits the
  updated state file back to the repo

### US-location filtering

Each ATS exposes location/country data differently, so `adapters/us_location.py` uses the most reliable
signal available: a structured country field when the ATS provides one (Ashby, Lever, Oracle,
SmartRecruiters), otherwise a heuristic over the location text (matches "United States" / US state names
and abbreviations, and flags an explicit non-US country if found). Workday doesn't expose country on its
list endpoint, so country is looked up per-job (`fetch_country`) only for listings that already matched
the title keywords, to avoid extra requests. If a job's country can't be determined at all, it's kept
rather than dropped, since a missed real listing is worse than an occasional ambiguous one.

## Local setup

```bash
pip install -r requirements.txt

# Preview matches without sending Discord notifications
python main.py --dry-run

# Send real notifications (requires DISCORD_WEBHOOK_URL)
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python main.py
```

## GitHub Actions setup

1. Create a Discord webhook: Server Settings -> Integrations -> Webhooks -> New Webhook -> Copy URL
2. In the repo: Settings -> Secrets and variables -> Actions -> New repository secret
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: the webhook URL from step 1
3. The workflow runs on a schedule, or trigger it manually from the Actions tab (`workflow_dispatch`)

## Adding a company

Add an entry to `config.yaml`:

```yaml
- name: SomeCompany
  ats: greenhouse   # greenhouse | ashby | lever | workday | oracle_fusion | smartrecruiters | eightfold
  slug: somecompany
```

- **Greenhouse**: slug is the value in `boards.greenhouse.io/<slug>`
- **Ashby**: slug is the value in `jobs.ashbyhq.com/<slug>`
- **Lever**: slug is the value in `jobs.lever.co/<slug>`
- **SmartRecruiters**: slug is the company identifier in `jobs.smartrecruiters.com/<slug>` (case-sensitive)
- **Workday**: also requires `tenant` (e.g. `wd12`) and `site` (e.g. `External_Career_Site`), found in the
  careers page URL: `https://<slug>.<tenant>.myworkdayjobs.com/<site>`. Some companies run a separate
  early-careers/campus site (e.g. Visa's `Visa_Early_Careers`) worth using instead of the general one.
- **Oracle Fusion Recruiting Cloud**: needs `host` (the Fusion instance), `site_number` (internal id), and
  `site_alias` (public URL slug) — found by inspecting the careers page's network requests.
- **Eightfold**: needs `domain` (the company's domain, e.g. `netapp.com`); slug is the Eightfold tenant
  subdomain (`<slug>.eightfold.ai`). Some Eightfold tenants block the public API (see Qualcomm above) —
  test with a plain `curl` before adding.

If a company isn't on one of these ATSes, it needs a new adapter in `adapters/` implementing
`fetch_jobs(slug, company_name, **extra) -> list[Job]`, registered in `main.py`'s `ADAPTERS` (and
`ADAPTER_EXTRA_ARGS` if it needs config fields beyond `slug`/`name`).
