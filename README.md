# intern-bot

Polls target companies' ATS job boards and pings Discord when a new internship listing appears.

## How it works

- `config.yaml` lists companies, each pointing at an ATS (`greenhouse`, `ashby`, or `workday`) and slug
- `adapters/` fetches and normalizes job listings per ATS
- `main.py` filters titles against `keywords`, diffs against `state/seen_jobs.json`, and sends a Discord
  notification for anything new
- `.github/workflows/check-listings.yml` runs this on a schedule (every 30 min) via GitHub Actions and
  commits the updated state file back to the repo

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
3. The workflow runs automatically every 30 minutes, or trigger it manually from the Actions tab
   (`workflow_dispatch`)

## Adding a company

Add an entry to `config.yaml`:

```yaml
- name: SomeCompany
  ats: greenhouse   # or ashby, or workday
  slug: somecompany
```

- **Greenhouse**: slug is the value in `boards.greenhouse.io/<slug>`
- **Ashby**: slug is the value in `jobs.ashbyhq.com/<slug>`
- **Workday**: also requires `tenant` (e.g. `wd12`) and `site` (e.g. `External_Career_Site`), found in the
  careers page URL: `https://<slug>.<tenant>.myworkdayjobs.com/<site>`

If a company isn't on one of these three ATSes, it needs a new adapter in `adapters/` implementing
`fetch_jobs(slug, company_name) -> list[Job]`.
