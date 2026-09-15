#!/bin/bash
set -e

echo "Compiling CV..."
latexmk -pdf CurriculumVitae_SA.tex

echo "Copying CV to website..."
cp CurriculumVitae_SA.pdf \
"/Users/stevenabrams/DSI Dropbox/Steven Abrams/Admin/Website/stevenabramslucp2479.github.io/files/cv_steven_abrams.pdf"

echo "Done. CV updated in website repository."
