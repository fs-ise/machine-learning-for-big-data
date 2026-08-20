QUARTO ?= quarto
PYTHON ?= python
DOCKER_IMAGE ?= machine-learning-for-big-data-decktape
SRC_SLIDES_DIR := slides
OUT_DIR := _site
SLIDES_DIR := $(OUT_DIR)/slides
SLIDES_QMD := $(shell find $(SRC_SLIDES_DIR) -type f -name '*.qmd' 2>/dev/null)
SLIDES_HTML := $(patsubst $(SRC_SLIDES_DIR)/%.qmd,$(SLIDES_DIR)/%.html,$(SLIDES_QMD))
SLIDES_PDF := $(SLIDES_HTML:.html=.pdf)
.PHONY: help site site-fast pdfs decktape-image exercises exercises-assign exercises-solution all sync-events clean
help:
	@echo "Targets: site, pdfs, exercises, all, sync-events, clean"
site-fast:
	$(QUARTO) render --no-clean
site: exercises site-fast
all: site pdfs
exercises-assign:
	$(QUARTO) render exercises --profile assign --to ipynb --no-clean
	$(QUARTO) render exercises --profile assign --to html --no-clean
	@for f in _site/exercises/*.ipynb _site/exercises/*.html; do [ -e "$$f" ] && mv "$$f" "$${f%.*}_assign.$${f##*.}" || true; done
exercises-solution:
	$(QUARTO) render exercises --profile solution --to ipynb --no-clean
	$(QUARTO) render exercises --profile solution --to html --no-clean
	@for f in _site/exercises/*.ipynb _site/exercises/*.html; do case "$$f" in *_assign.*|*_solution.*) continue;; esac; [ -e "$$f" ] && mv "$$f" "$${f%.*}_solution.$${f##*.}" || true; done
exercises: exercises-assign exercises-solution
pdfs: $(SLIDES_PDF)
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
	rm -rf _site _freeze _pdf-tmp .quarto
