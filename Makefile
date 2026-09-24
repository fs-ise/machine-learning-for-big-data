QUARTO ?= quarto
PYTHON ?= python

DOCKER_IMAGE ?= machine-learning-for-big-data-decktape
DECKTAPE_STAMP := .build/decktape-image.stamp
DECKTAPE_IMAGE_DEPS := Dockerfile

SRC_SLIDES_DIR := slides
OUT_DIR := _site
SLIDES_DIR := $(OUT_DIR)/slides

SLIDES_QMD := $(shell find $(SRC_SLIDES_DIR) \
	-type f \
	-name '*.qmd' \
	! -name '_*' \
	2>/dev/null)

SLIDES_HTML := $(patsubst $(SRC_SLIDES_DIR)/%.qmd,$(SLIDES_DIR)/%.html,$(SLIDES_QMD))
SLIDES_PDF := $(SLIDES_HTML:.html=.pdf)
NOTE_SOURCES := $(sort $(wildcard notes/session_*.qmd))
TEACHING_CHECKLIST := notes/teaching_checklist.qmd
NOTES_PDF := $(OUT_DIR)/notes.pdf
NOTES_COMBINER := scripts/combine_notes.py
NOTES_LINEBREAK_FILTER := scripts/html_br_to_linebreak.lua
NEEDSPACE_EXTENSION_DEPS := $(shell find _extensions/needspace -type f 2>/dev/null)
EXERCISE_SOURCES := $(sort $(wildcard exercises/session_*.qmd))
EXERCISE_STEMS := $(patsubst exercises/%.qmd,%,$(EXERCISE_SOURCES))
EXERCISE_ASSIGN_QMD := $(patsubst %,_generated/exercises/%_assign.qmd,$(EXERCISE_STEMS))
EXERCISE_SOLUTION_QMD := $(patsubst %,_generated/exercises/%_solution.qmd,$(EXERCISE_STEMS))
EXERCISE_PDF_QMD := $(patsubst %,_generated/exercises/pdf_%_solution.qmd,$(EXERCISE_STEMS))
EXERCISE_INCLUDES := $(patsubst %,_generated/exercises/includes/_%_solution.qmd,$(EXERCISE_STEMS))
EXERCISE_PDFS := $(patsubst %,$(OUT_DIR)/exercises/%_solution.pdf,$(EXERCISE_STEMS))
EXERCISE_PUBLIC_ASSIGN := $(patsubst %,$(OUT_DIR)/exercises/%_assign.qmd,$(EXERCISE_STEMS))
EXERCISE_PUBLIC_SOLUTION := $(patsubst %,$(OUT_DIR)/exercises/%_solution.qmd,$(EXERCISE_STEMS))
EXERCISE_DATA_SOURCES := $(shell find exercises/data -type f 2>/dev/null)
EXERCISE_PUBLIC_DATA := $(patsubst exercises/data/%,$(OUT_DIR)/exercises/data/%,$(EXERCISE_DATA_SOURCES))
EXERCISE_GENERATOR := scripts/build_exercises.py
EXERCISE_PDF_SHARED_DEPS := \
	$(wildcard scripts/templates/exercise-solution-*.tex) \
	$(NEEDSPACE_EXTENSION_DEPS) \
	$(EXERCISE_DATA_SOURCES)


.PHONY: \
	help \
	site \
	site-fast \
	pdfs \
	group-work-pdf \
	decktape-image \
	decktape-image-check \
	exercises \
	exercises-generate \
	exercises-render \
	exercises-check \
	notes \
	all \
	sync-events \
	clean


help:
	@echo "Targets:"
	@echo "  site                 Render complete site"
	@echo "  site-fast            Render site without generating exercises"
	@echo "  pdfs                 Generate slide PDFs"
	@echo "  group-work-pdf       Generate group-work handout PDF"
	@echo "  notes                Build one A4 PDF containing all teaching notes"
	@echo "  decktape-image       Force rebuild of DeckTape Docker image"
	@echo "  exercises-generate   Generate exercise variants"
	@echo "  exercises-render     Render generated exercises"
	@echo "  exercises             Generate and render exercises"
	@echo "  exercises-check      Check generated exercises"
	@echo "  all                   Render site and PDFs"
	@echo "  sync-events           Synchronize events"
	@echo "  clean                 Remove generated files"
	@echo ""
	@echo "Exercises:"
	@echo "  canonical QMD -> _generated/exercises variant QMD"
	@echo "                -> _site/exercises solution PDF and variant QMD"


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------

site-fast: exercises-generate
	$(QUARTO) render --no-clean


site: exercises
	$(QUARTO) render --no-clean


all: site pdfs notes


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------

exercises-generate:
	$(PYTHON) $(EXERCISE_GENERATOR)


# One source has four generated outputs. The grouped pattern rule records that
# relationship, while the write-if-changed generator runs only once per make.
_generated/exercises/session_%_assign.qmd \
_generated/exercises/session_%_solution.qmd \
_generated/exercises/pdf_session_%_solution.qmd \
_generated/exercises/includes/_session_%_solution.qmd &: exercises/session_%.qmd | exercises-generate
	@test -f _generated/exercises/session_$*_assign.qmd \
		-a -f _generated/exercises/session_$*_solution.qmd \
		-a -f _generated/exercises/pdf_session_$*_solution.qmd \
		-a -f _generated/exercises/includes/_session_$*_solution.qmd

_generated/exercises/_quarto.yml: | exercises-generate
	@test -f "$@"

$(OUT_DIR)/exercises/%_assign.qmd: _generated/exercises/%_assign.qmd
	@mkdir -p "$(dir $@)"
	@cmp -s "$<" "$@" || cp "$<" "$@"

$(OUT_DIR)/exercises/%_solution.qmd: _generated/exercises/%_solution.qmd
	@mkdir -p "$(dir $@)"
	@cmp -s "$<" "$@" || cp "$<" "$@"

$(OUT_DIR)/exercises/data/%: exercises/data/%
	@mkdir -p "$(dir $@)"
	@cmp -s "$<" "$@" || cp "$<" "$@"

$(OUT_DIR)/exercises/session_%_solution.pdf: \
	_generated/exercises/pdf_session_%_solution.qmd \
	_generated/exercises/_quarto.yml \
	$(EXERCISE_PDF_SHARED_DEPS)
	@set -eu; \
		mkdir -p "$(dir $@)" _generated/exercises/_rendered; \
		output="_generated/exercises/_rendered/session_$*_solution.pdf"; \
		rm -f "$$output" "$@"; \
		echo "Rendering $< to $@"; \
		cd _generated/exercises; \
		$(QUARTO) render "pdf_session_$*_solution.qmd" --to pdf \
			--output "session_$*_solution.pdf" --no-clean; \
		if [ ! -s "_rendered/session_$*_solution.pdf" ]; then \
			echo "error: Quarto did not create expected PDF: $$output" >&2; \
			exit 1; \
		fi; \
		cp "_rendered/session_$*_solution.pdf" "$(abspath $@)"

exercises-render: exercises-generate $(EXERCISE_ASSIGN_QMD) $(EXERCISE_SOLUTION_QMD) \
	$(EXERCISE_PDF_QMD) $(EXERCISE_INCLUDES) $(EXERCISE_PUBLIC_ASSIGN) \
	$(EXERCISE_PUBLIC_SOLUTION) $(EXERCISE_PUBLIC_DATA) $(EXERCISE_PDFS)


exercises: exercises-render


exercises-check: exercises-generate $(EXERCISE_PDFS)


# ---------------------------------------------------------------------------
# PDFs
# ---------------------------------------------------------------------------

pdfs: $(SLIDES_PDF)


# Combined, printable teaching notes (rendered directly by Quarto/Pandoc).
notes: $(NOTES_PDF)


$(NOTES_PDF): $(NOTE_SOURCES) $(TEACHING_CHECKLIST) $(NOTES_COMBINER) $(NOTES_LINEBREAK_FILTER) $(NEEDSPACE_EXTENSION_DEPS) $(EXERCISE_INCLUDES)
	@set -eu; \
		mkdir -p "$(OUT_DIR)" _pdf-tmp; \
		rm -rf _pdf-tmp/_extensions/needspace; \
		mkdir -p _pdf-tmp/_extensions; \
		cp -R _extensions/needspace _pdf-tmp/_extensions/needspace; \
		combined_qmd="_pdf-tmp/teaching-notes.qmd"; \
		$(PYTHON) "$(NOTES_COMBINER)" --checklist "$(TEACHING_CHECKLIST)" --output "$$combined_qmd" $(NOTE_SOURCES); \
		$(QUARTO) render "$$combined_qmd" --to pdf --output notes.pdf; \
		mv "notes.pdf" "$(NOTES_PDF)"; \
		rm -f "$$combined_qmd"


# Standalone A4 handout
# Output: _site/handouts/group_work.pdf
group-work-pdf:
	$(QUARTO) render group_work.qmd --profile group-work-pdf --to pdf


# ---------------------------------------------------------------------------
# DeckTape Docker image
# ---------------------------------------------------------------------------

# Build the image when one of its build inputs changes.
#
# Add additional files to DECKTAPE_IMAGE_DEPS if the Dockerfile uses them
# as build-time inputs, for example:
#
# DECKTAPE_IMAGE_DEPS := Dockerfile package.json package-lock.json

$(DECKTAPE_STAMP): $(DECKTAPE_IMAGE_DEPS)
	@echo "Building DeckTape Docker image: $(DOCKER_IMAGE)"
	docker build --tag $(DOCKER_IMAGE) .
	@mkdir -p "$(dir $@)"
	@touch "$@"


# Cheap check performed once per Make invocation.
# This handles the case where the stamp exists but the Docker image was
# manually removed.
decktape-image-check: $(DECKTAPE_STAMP)
	@if ! docker image inspect "$(DOCKER_IMAGE)" >/dev/null 2>&1; then \
		echo "DeckTape Docker image is missing; rebuilding it"; \
		docker build --tag "$(DOCKER_IMAGE)" .; \
		mkdir -p "$(dir $(DECKTAPE_STAMP))"; \
		touch "$(DECKTAPE_STAMP)"; \
	fi


# Explicit command to force a fresh image build.
decktape-image:
	@echo "Rebuilding DeckTape Docker image: $(DOCKER_IMAGE)"
	docker build --tag $(DOCKER_IMAGE) .
	@mkdir -p "$(dir $(DECKTAPE_STAMP))"
	@touch "$(DECKTAPE_STAMP)"


$(SLIDES_DIR)/%.pdf: \
	$(SRC_SLIDES_DIR)/%.qmd \
	_quarto.yml \
	_quarto-pdf.yml \
	scripts/decktape.sh \
	| decktape-image-check
	@set -eu; \
		tmp_dir="$(abspath _pdf-tmp)/$*"; \
		cleanup() { \
			status=$$?; \
			rm -rf "$$tmp_dir"; \
			exit $$status; \
		}; \
		trap cleanup EXIT INT TERM; \
		mkdir -p "$(SLIDES_DIR)" "$$tmp_dir"; \
		$(QUARTO) render "$<" \
			--profile pdf \
			-P execute=false \
			--output-dir "$$tmp_dir"; \
		docker run --rm \
			--env HOST_UID="$$(id -u)" \
			--env HOST_GID="$$(id -g)" \
			--volume "$(CURDIR):/work" \
			--workdir /work \
			"$(DOCKER_IMAGE)" \
			./scripts/decktape.sh \
			"_pdf-tmp/$*/slides/$*.html" \
			"$@"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

sync-events:
	$(PYTHON) scripts/sync_events.py


clean:
	rm -rf _site _generated _freeze _pdf-tmp .quarto
