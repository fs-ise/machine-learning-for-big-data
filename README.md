<p align="center">
    <img alt="Machine Learning for Big Data logo" src="assets/mlbd-logo-long.png" width="600px">
</p>

<div align="center">

![Offered by: FS-ISE](https://img.shields.io/badge/Offered%20by-FS--ISE-blue)
![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-green.svg)

</div>

# Machine Learning for Big Data

Welcome! **Machine Learning for Big Data (MLBD)** is a teaching repository for the Machine Learning for Big Data course.
You can find more information on the following pages:

- [Course page](https://fs-ise.github.io/machine-learning-for-big-data/)
- [Syllabus](https://fs-ise.github.io/machine-learning-for-big-data/syllabus.html)
- [Teaching notes](https://fs-ise.github.io/machine-learning-for-big-data/teaching_notes.html)

## Key files

- `course.yml` is the single source of truth for course metadata, the calendar
  synchronization configuration, synchronized events, and Quarto variables.
- `template/sources.yml` records reviewed source repositories and the template update process.

## Common commands

- `make site` renders exercises and the website.
- `make pdfs` creates every slide PDF.
- `make _site/slides/session_03.pdf` creates one slide deck.
- `make all` renders the complete website and all slide PDFs.
- `make exercises` creates assignment and solution variants.
- `make sync-events` reads the authoritative handbook YAML URL configured only
  under `schedule.source` in `course.yml`, imports calendar-controlled date,
  time, location, and external ID fields into `course.yml`, and preserves
  manually maintained event metadata. The website calendar renders those
  synchronized `course.yml` events; it does not fetch the handbook itself.
- `make clean` removes generated build artifacts.

## Slide PDF prerequisites

Install [Quarto](https://quarto.org/) and Docker. Quarto renders the temporary
Reveal.js presentation on the host; the Makefile automatically builds a Docker
image containing the pinned Decktape version, Chromium dependencies, and
Ghostscript. Node.js, npm, and Decktape do not need to be installed on the
host.

Build all slide PDFs with `make pdfs`, build an individual deck with
`make _site/slides/session_03.pdf`, or build the site and every PDF together
with `make all`. Generated PDFs are written as the current host user.

## R dependencies

The CRAN packages used by executable R chunks are listed in
[`r-packages.txt`](r-packages.txt). Install any packages that are not already
available before rendering the course materials:

```sh
Rscript scripts/install_r_dependencies.R
```

The helper leaves existing installations unchanged and installs only missing
packages. Display-only R examples (fenced with `r` rather than `{r}`) are not
executed during rendering and may demonstrate additional, optional packages.

## License

The teaching contents are licensed under the [CC BY 4.0 License](https://creativecommons.org/licenses/by/4.0/) unless noted otherwise.
