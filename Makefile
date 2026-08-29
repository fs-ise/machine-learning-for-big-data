QUARTO ?= quarto
PYTHON ?= python
DOCKER_IMAGE ?= machine-learning-for-big-data-decktape
SRC_SLIDES_DIR := slides
OUT_DIR := _site
SLIDES_DIR := $(OUT_DIR)/slides
SLIDES_QMD := $(shell find $(SRC_SLIDES_DIR) -type f -name '*.qmd' 2>/dev/null)
SLIDES_HTML := $(patsubst $(SRC_SLIDES_DIR)/%.qmd,$(SLIDES_DIR)/%.html,$(SLIDES_QMD))
SLIDES_PDF := $(SLIDES_HTML:.html=.pdf)
.PHONY: help site site-fast pdfs group-work-pdf decktape-image exercises exercises-generate exercises-render exercises-check all sync-events clean
help:
	@echo "Targets: site, pdfs, group-work-pdf, exercises-generate, exercises-render, exercises, exercises-check, all, sync-events, clean"
	@echo "Exercises: canonical QMD -> _generated/exercises variant QMD -> _site/exercises HTML and QMD"
site-fast:
	$(QUARTO) render --no-clean
site: exercises
	$(QUARTO) render --no-clean
all: site pdfs
exercises-generate:
	$(PYTHON) scripts/build_exercises.py
exercises-render: exercises-generate
	$(QUARTO) render _generated/exercises --to html --no-clean
	@mkdir -p _site/exercises
	@cp -R _generated/exercises/_rendered/. _site/exercises/
	@cp _generated/exercises/*_assign.qmd _site/exercises/
	@cp _generated/exercises/*_solution.qmd _site/exercises/
exercises: exercises-render
exercises-check: exercises-generate
	@set -eu; \
		cd _generated/exercises; \
		for exercise in session_*_assign.qmd session_*_solution.qmd; do \
			echo "Rendering $$exercise"; \
			$(QUARTO) render "$$exercise" --to html --no-clean || { \
				echo "Exercise render failed: $$exercise" >&2; \
				exit 1; \
			}; \
		done
pdfs: $(SLIDES_PDF)
# Standalone A4 handout; output: _site/handouts/group_work.pdf
group-work-pdf:
	$(QUARTO) render group_work.qmd --profile group-work-pdf --to pdf
decktape-image: Dockerfile
	docker build --tag $(DOCKER_IMAGE) .
$(SLIDES_DIR)/%.pdf: $(SRC_SLIDES_DIR)/%.qmd _quarto.yml _quarto-pdf.yml scripts/decktape.sh | decktape-image
	@set -eu; \
		tmp_dir="$(abspath _pdf-tmp)/$*"; \
		cleanup() { \
			status=$$?; \
			rm -rf "$$tmp_dir"; \
			exit $$status; \
		}; \
		trap cleanup EXIT INT TERM; \
		mkdir -p "$(SLIDES_DIR)" "$$tmp_dir"; \
		$(QUARTO) render "$<" --profile pdf -P execute=false --output-dir "$$tmp_dir"; \
		docker run --rm \
			--env HOST_UID="$$(id -u)" --env HOST_GID="$$(id -g)" \
			--volume "$(CURDIR):/work" --workdir /work \
			$(DOCKER_IMAGE) ./scripts/decktape.sh \
			"_pdf-tmp/$*/slides/$*.html" "$@"
sync-events:
	$(PYTHON) scripts/sync_events.py
clean:
	rm -rf _site _generated _freeze _pdf-tmp .quarto
