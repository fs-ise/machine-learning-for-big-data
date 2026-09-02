#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = FALSE)
script_arg <- grep("^--file=", args, value = TRUE)
if (length(script_arg) != 1) {
  stop("Run this helper with Rscript.")
}

script_path <- normalizePath(sub("^--file=", "", script_arg))
requirements_path <- file.path(dirname(script_path), "..", "r-packages.txt")

packages <- trimws(readLines(requirements_path, warn = FALSE))
packages <- packages[nzchar(packages) & !startsWith(packages, "#")]
missing_packages <- packages[
  !vapply(packages, requireNamespace, quietly = TRUE, FUN.VALUE = logical(1))
]

if (length(missing_packages) == 0) {
  message("All R dependencies are already installed.")
} else {
  repos <- getOption("repos")
  if (is.null(repos) || identical(unname(repos["CRAN"]), "@CRAN@")) {
    repos["CRAN"] <- "https://cloud.r-project.org"
  }
  message("Installing missing R dependencies: ", paste(missing_packages, collapse = ", "))
  install.packages(missing_packages, repos = repos)
}
