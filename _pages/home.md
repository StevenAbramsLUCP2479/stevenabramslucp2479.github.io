---
permalink: /
title: "Understanding infectious diseases through data and models"
author_profile: true
excerpt: "Steven Abrams — biostatistics, infectious disease modelling, immunity and vaccination."
---

I am **Steven Abrams**, a biostatistician and medical statistician at **Hasselt University** and the **University of Antwerp**. I develop statistical and mathematical methods to understand infection, immunity and vaccination, and to inform public health decisions.

<div class="site-actions">
  <a href="{{ '/projects/' | relative_url }}" class="btn">Explore my research</a>
  <a href="{{ '/contact/' | relative_url }}" class="btn">Contact me</a>
  <a href="{{ '/files/cv_steven_abrams.pdf' | relative_url }}">Download CV (PDF)</a>
</div>

## Research and selected work

Three connected areas bring together my methodological research and collaborative work in epidemiology.

<div class="research-grid">
{% for highlight in site.data.research_highlights %}
  <article class="research-card">
    <h3>{{ highlight.title }}</h3>
    <p>{{ highlight.summary }}</p>
    <p class="research-card__label">Selected work · {{ highlight.year }}</p>
    <h4><a href="{{ highlight.url | relative_url }}">{{ highlight.work }}</a></h4>
    <p>{{ highlight.detail }}</p>
  </article>
{% endfor %}
</div>

[Browse all publications]({{ '/publications/' | relative_url }}) · [Explore research projects]({{ '/projects/' | relative_url }})

## Teaching and science communication

I share statistics and infectious disease research with students, teachers, health professionals and the public. Explore [workshops and educational resources]({{ '/science-communication/' | relative_url }}), or browse [conference talks and slides]({{ '/slides/' | relative_url }}).

## Code and reproducible research

Research code and related projects are available on [GitHub](https://github.com/stevenabramslucp2479). Where resources are available for an individual paper, they are linked from its publication entry.
