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
if (anyDuplicated(packages)) {
  stop("Duplicate entries in ", requirements_path, ": ",
       paste(unique(packages[duplicated(packages)]), collapse = ", "))
}

missing_packages <- packages[
  !vapply(packages, requireNamespace, quietly = TRUE, FUN.VALUE = logical(1))
]

if (length(missing_packages) == 0L) {
  message("All R dependencies are already installed.")
} else {
  message(
    "Installing missing R dependencies: ",
    paste(missing_packages, collapse = ", ")
  )
  install.packages(missing_packages)
}

# install.packages() reports an unavailable or failed source package as a
# warning. Turn that into an actionable CI failure before rendering begins.
unavailable <- packages[
  !vapply(packages, requireNamespace, quietly = TRUE, FUN.VALUE = logical(1))
]

if (length(unavailable) > 0L) {
  stop(
    "Required R packages unavailable: ",
    paste(unavailable, collapse = ", ")
  )
}

message("Validated R dependencies: ", paste(packages, collapse = ", "))
