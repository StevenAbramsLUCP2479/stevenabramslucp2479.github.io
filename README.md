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
