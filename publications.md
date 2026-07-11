---
layout: page
title: Publications
---

*Last updated: `r format(Sys.Date(), "%B %d, %Y")`*

## About

All publications are automatically updated from my [ORCID profile](https://orcid.org/0000-0001-7353-9304).\
Use the search box to filter publications. Click column headers to sort.

```{r}
#| echo: false
#| message: false
#| warning: false

library(DT)
library(dplyr)
library(htmltools)

# Function to bold name variations
bold_my_name <- function(author_string, is_mine) {
  if (is_mine != "YES" || is.na(author_string) || author_string == "") {
    return(author_string)
  }
  
  # All name variations
  name_variants <- c(
    "S. Abrams", "Steven Abrams", "Abrams, S.",
    "Abrams, Steven"
  )
  
  # Sort by length (longest first) to avoid partial replacements
  name_variants <- name_variants[order(nchar(name_variants), decreasing = TRUE)]
  
  result <- author_string
  for (variant in name_variants) {
    result <- gsub(variant, 
                  paste0("<strong>", variant, "</strong>"), 
                  result, 
                  fixed = TRUE)
  }
  return(result)
}

# Read the data
pubs <- read.csv("publications_data.csv", stringsAsFactors = FALSE)

# Create formatted columns
pubs_display <- pubs %>%
  rowwise() %>%
  mutate(
    # Format year
    Year = ifelse(year == "", "Unknown", year),
    
    # Bold your name in authors if is_my_paper == "YES"
    Authors = bold_my_name(authors, is_my_paper),
    
    # Format journal with volume/issue
    Journal = case_when(
      journal != "" & volume != "" & issue != "" ~ paste0(journal, " ", volume, "(", issue, ")"),
      journal != "" & volume != "" ~ paste0(journal, " ", volume),
      journal != "" ~ journal,
      TRUE ~ ""
    ),
    
    # Create DOI link
    Link = case_when(
      doi != "" ~ paste0('<a href="https://doi.org/', doi, '" target="_blank">DOI</a>'),
      has_doi == "PMID" ~ '<a href="#" target="_blank">PMID</a>',
      has_doi == "ARXIV" ~ '<a href="#" target="_blank">arXiv</a>',
      TRUE ~ ""
    ),
    
    # Format title with abstract toggle
    Title_Display = ifelse(
      abstract != "",
      paste0(
        '<div class="pub-title">', title, '</div>',
        '<details><summary style="color:#0066cc;cursor:pointer;font-size:0.9em;">Show abstract</summary>',
        '<div style="margin-top:8px;padding:10px;background-color:#f5f5f5;border-left:3px solid #0066cc;">',
        abstract, '</div></details>'
      ),
      paste0('<div class="pub-title">', title, '</div>')
    )
  ) %>%
  ungroup() %>%
  select(Year, Authors, Title_Display, Journal, Link)

# Create the DataTable
datatable(
  pubs_display,
  colnames = c("Year", "Authors", "Title", "Journal", "Link"),
  escape = FALSE,  # Allow HTML
  rownames = FALSE,
  filter = 'top',
  options = list(
    pageLength = 25,
    lengthMenu = c(10, 25, 50, 100),
    order = list(list(0, 'desc')),  # Sort by year descending
    columnDefs = list(
      list(width = '8%', targets = 0),   # Year
      list(width = '25%', targets = 1),  # Authors
      list(width = '42%', targets = 2),  # Title
      list(width = '20%', targets = 3),  # Journal
      list(width = '5%', targets = 4)    # Link
    ),
    dom = 'lfrtip',
    language = list(
      search = "Search publications:",
      lengthMenu = "Show _MENU_ publications",
      info = "Showing _START_ to _END_ of _TOTAL_ publications"
    )
  )
) %>%
  formatStyle(
    'Year',
    fontWeight = 'bold'
  )
```