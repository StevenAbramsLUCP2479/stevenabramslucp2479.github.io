# Steven Abrams — Academic Pages

This repository hosts my personal academic website, built with the
[Academic Pages](https://github.com/academicpages/academicpages.github.io)
template and deployed with GitHub Pages.

## Website

https://stevenabramslucp2479.github.io

## Local development

1. Install Ruby and Bundler (see the Academic Pages README).
2. Run `bundle install`.
3. Run `bundle exec jekyll serve -l -H localhost` and open http://localhost:4000.

## Deployment

GitHub Pages builds the site automatically from the `main` branch (root folder).
The build is also checked on every push by the `.github/workflows/jekyll-build.yml`
workflow.

## Structure

- `_pages/` — top-level pages (Home, About, Projects, Publications, CV)
- `_publications/` — one Markdown file per publication, generated from the
  [ORCID profile](https://orcid.org/0000-0001-7353-9304)
- `_posts/`, `_talks/`, `_teaching/`, `_portfolio/` — optional collections (currently empty)
- `files/` — PDFs and other downloadable assets
- `images/` — images, including the profile photo
- `_config.yml` — site-wide configuration

## Publication maintenance

The **Update publications from ORCID** workflow checks public works on
[my ORCID profile](https://orcid.org/0000-0001-7353-9304) every Monday at
05:17 UTC (06:17 in Belgian winter time / 07:17 in summer). It validates the
updated site and opens or refreshes one pull request on
`automation/orcid-publications`. Review and merge that PR to publish the changes.
It does not merge or publish automatically. No PR is opened when nothing changes.

### Enable and run

1. Merge the maintenance implementation into `main`; scheduled workflows run
   from the default branch.
2. In **Settings → Actions → General → Workflow permissions**, enable
   **Allow GitHub Actions to create and approve pull requests**. The workflow
   requests the required contents and pull-request write permissions itself.
3. Under **Actions → Update publications from ORCID → Run workflow**, run the
   first check immediately. No ORCID secret is needed for the public endpoint
   used here. If the endpoint later rejects public requests, the workflow fails
   visibly without changing publication files.
4. Review later update PRs. If GitHub requests approval for their CI workflows,
   approve the workflow run. The maintenance workflow also builds the proposed
   site before opening the PR.

The Actions run summary contains the import report. A report and patch are also
saved as a 30-day artifact, including when PR creation fails because of repository
permissions. Failed runs appear in Actions; enable GitHub Actions notifications
in your GitHub notification settings if you want failure emails. GitHub may
disable scheduled workflows after 60 days without activity in a public repository;
re-enable the workflow from Actions if this happens. Scheduled runs may be delayed.

### What is maintained

- New journal articles, preprints, book chapters and conference papers are imported
  into `_publications/`. Their category pages read these records automatically;
  new journal articles are also eligible for the homepage research highlights.
- Matching uses the ORCID work ID, self DOI, then normalized title. Preprints and
  published articles remain separate. An unambiguous identical-title journal
  article gets linked from its preprint. Different-title versions need a manual link.
- Existing curated records keep their text, categories, topics, links and URLs.
  For newly imported records, later ORCID metadata changes update only fields that
  still match the previous import. Edited fields, custom content and URLs survive.
  Removing/hiding a work on ORCID never deletes a website record.
- Dates with only a year use January 1 for Jekyll sorting and record
  `date_precision: year`; this does not assert an exact publication day. The lists
  show the year. Missing years and unsupported types are reported for manual review.
  Thesis supervision and jury roles remain manually curated.
- Google Scholar is linked for readers but is not scraped. A work listed only on
  Scholar must be added to public ORCID works, or manually added to `_publications/`.
  This keeps the website current with ORCID, not with Scholar independently.

To correct a legacy citation, edit its `_publications/*.md` file. To omit an ORCID
work from future imports, put its numeric put-code (as a string) in
`scripts/publication_sync_config.json` under `ignored_put_codes`; separately remove
the local record if desired. Closing an update PR alone does not ignore the work.
Avoid manual edits on the automation branch: make corrections on `main` or in the
ORCID profile, since the next run regenerates that branch from `main`.

For a local check (Python 3.12):

```sh
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
python scripts/sync_publications.py
git diff -- _publications
bundle exec jekyll build --strict_front_matter
```

`--fixture path/to/works.json` accepts an offline array of ORCID v3 work details
for reproducible checks. Network requests finish and all records are validated
before any publication files are written; failed/incomplete API responses abort.
