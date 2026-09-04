QUARTO ?= quarto
PYTHON ?= python

DOCKER_IMAGE ?= machine-learning-for-big-data-decktape
DECKTAPE_STAMP := .build/decktape-image.stamp
DECKTAPE_IMAGE_DEPS := Dockerfile

SRC_SLIDES_DIR := slides
OUT_DIR := _site
SLIDES_DIR := $(OUT_DIR)/slides

SLIDES_QMD := $(shell find $(SRC_SLIDES_DIR) -type f -name '*.qmd' 2>/dev/null)
SLIDES_HTML := $(patsubst $(SRC_SLIDES_DIR)/%.qmd,$(SLIDES_DIR)/%.html,$(SLIDES_QMD))
SLIDES_PDF := $(SLIDES_HTML:.html=.pdf)


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
	all \
	sync-events \
	clean


help:
	@echo "Targets:"
	@echo "  site                 Render complete site"
	@echo "  site-fast            Render site without generating exercises"
	@echo "  pdfs                 Generate slide PDFs"
	@echo "  group-work-pdf       Generate group-work handout PDF"
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
	@echo "                -> _site/exercises HTML and QMD"


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------

site-fast:
	$(QUARTO) render --no-clean


site: exercises
	$(QUARTO) render --no-clean


all: site pdfs


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------

exercises-generate:
	$(PYTHON) scripts/build_exercises.py


exercises-render: exercises-generate
	@set -eu; \
		cd _generated/exercises; \
		for exercise in session_*_assign.qmd; do \
			echo "Rendering $$exercise without execution"; \
			$(QUARTO) render "$$exercise" --to html --no-clean --no-execute; \
		done; \
		for exercise in session_*_solution.qmd; do \
			echo "Rendering $$exercise"; \
			$(QUARTO) render "$$exercise" --to html --no-clean; \
		done

	@mkdir -p _site/exercises
	@cp -R _generated/exercises/_rendered/. _site/exercises/
	@cp _generated/exercises/*_assign.qmd _site/exercises/
	@cp _generated/exercises/*_solution.qmd _site/exercises/


exercises: exercises-render


exercises-check: exercises-generate
	@set -eu; \
		cd _generated/exercises; \
		for exercise in session_*_assign.qmd; do \
			echo "Checking $$exercise"; \
			$(QUARTO) render "$$exercise" --to html --no-clean --no-execute; \
		done; \
		for exercise in session_*_solution.qmd; do \
			echo "Checking $$exercise"; \
			$(QUARTO) render "$$exercise" --to html --no-clean; \
		done


# ---------------------------------------------------------------------------
# PDFs
# ---------------------------------------------------------------------------

pdfs: $(SLIDES_PDF)


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