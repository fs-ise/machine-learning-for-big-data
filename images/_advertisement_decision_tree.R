plot_advertisement_decision_tree <- function() {
  library(partykit)
  library(grid)

  # 1. Reconstruct data from terminal-node counts --------------------

  leaves <- data.frame(
    customer = c(
      "yes", "yes", "yes", "yes",
      "yes", "yes", "no", "no"
    ),
    income = c(
      20000, 40000, 40000, 40000,
      40000, 40000, 40000, 40000
    ),
    age = c(
      35, 35, 35, 35,
      35, 50, 25, 35
    ),
    university_degree = c(
      "no", "yes", "no", "no",
      "no", "no", "no", "no"
    ),
    house_owner = c(
      "no", "no", "yes", "no",
      "no", "no", "no", "no"
    ),
    children = c(
      "no", "no", "no", "yes",
      "no", "no", "no", "no"
    ),
    no = c(32, 4, 4, 0, 6, 14, 16, 43),
    yes = c(16, 24, 9, 1, 0, 8, 12, 10)
  )

  customers <- do.call(
    rbind,
    lapply(seq_len(nrow(leaves)), function(i) {

      counts <- c(leaves$no[i], leaves$yes[i])

      observations <- leaves[
        rep(i, sum(counts)),
        1:6,
        drop = FALSE
      ]

      observations$respond <- factor(
        rep(c("no", "yes"), times = counts),
        levels = c("no", "yes")
      )

      observations
    })
  )

  rownames(customers) <- NULL

  customers$customer <- factor(
    customers$customer,
    levels = c("yes", "no")
  )

  customers$university_degree <- factor(
    customers$university_degree,
    levels = c("yes", "no")
  )

  customers$house_owner <- factor(
    customers$house_owner,
    levels = c("yes", "no")
  )

  customers$children <- factor(
    customers$children,
    levels = c("yes", "no")
  )

  # 2. Construct the exact decision tree -----------------------------

  nodes <- partynode(
    id = 1L,
    split = partysplit(1L, index = 1:2),
    kids = list(

      # Customer = yes
      partynode(
        id = 2L,
        split = partysplit(
          2L,
          breaks = 30000,
          right = FALSE
        ),
        kids = list(

          # Income < 30000
          partynode(3L),

          # Income >= 30000
          partynode(
            id = 4L,
            split = partysplit(
              3L,
              breaks = 42,
              right = FALSE
            ),
            kids = list(

              # Age < 42
              partynode(
                id = 5L,
                split = partysplit(
                  4L,
                  index = 1:2
                ),
                kids = list(

                  # University degree = yes
                  partynode(6L),

                  # University degree = no
                  partynode(
                    id = 7L,
                    split = partysplit(
                      5L,
                      index = 1:2
                    ),
                    kids = list(

                      # House owner = yes
                      partynode(8L),

                      # House owner = no
                      partynode(
                        id = 9L,
                        split = partysplit(
                          6L,
                          index = 1:2
                        ),
                        kids = list(
                          partynode(10L),
                          partynode(11L)
                        )
                      )
                    )
                  )
                )
              ),

              # Age >= 42
              partynode(12L)
            )
          )
        )
      ),

      # Customer = no
      partynode(
        id = 13L,
        split = partysplit(
          3L,
          breaks = 30,
          right = FALSE
        ),
        kids = list(
          partynode(14L),
          partynode(15L)
        )
      )
    )
  )

  # 3. Create the partykit object ------------------------------------

  tree <- party(
    node = nodes,
    data = customers,
    fitted = data.frame(
      "(fitted)" = fitted_node(nodes, customers),
      "(response)" = customers$respond,
      check.names = FALSE
    ),
    terms = terms(
      respond ~ .,
      data = customers
    )
  )

  tree <- as.constparty(tree)

  # 4. Labels and colors ---------------------------------------------

  split_names <- c(
    "1"  = "Customer",
    "2"  = "Income",
    "4"  = "Age",
    "5"  = "University degree",
    "7"  = "House owner",
    "9"  = "Children",
    "13" = "Age"
  )

  class_colors <- c(
    no  = "#3264C8",
    yes = "#17A85A"
  )

  # 5. Improved node panel -------------------------------------------

  node_panel <- function(node) {

    id <- id_node(node)

    observations <- data_party(tree, id = id)

    counts <- table(
      factor(
        observations$respond,
        levels = c("no", "yes")
      )
    )

    n <- sum(counts)
    proportions <- as.numeric(counts) / n
    percentages <- round(100 * proportions)

    if (as.character(id) %in% names(split_names)) {
      label <- split_names[as.character(id)]
      header_fill <- "#EAF0F7"
    } else {
      prediction <- names(which.max(counts))
      label <- sprintf("Predict: %s", prediction)
      header_fill <- "#F0F5F1"
    }

    # node box
    grid.rect(
      x = 0.5,
      y = 0.5,
      width = 0.95,
      height = 0.92,
      gp = gpar(
        fill = "white",
        col = "#64748B",
        lwd = 1
      )
    )

    # header
    grid.rect(
      x = 0.5,
      y = 0.81,
      width = 0.95,
      height = 0.24,
      gp = gpar(
        fill = header_fill,
        col = NA
      )
    )

    grid.text(
      label,
      x = 0.5,
      y = 0.81,
      gp = gpar(
        fontsize = 12,
        fontface = "bold",
        col = "#26354A"
      )
    )

    # separator
    grid.lines(
      x = c(0.03, 0.97),
      y = c(0.68, 0.68),
      gp = gpar(
        col = "#CBD5E1",
        lwd = 0.8
      )
    )

    # class rows
    row_y <- c(0.51, 0.28)

    for (i in seq_along(counts)) {

      class_name <- names(counts)[i]

      grid.text(
        sprintf(
          "%s %d (%d%%)",
          class_name,
          counts[i],
          percentages[i]
        ),
        x = 0.04,
        y = row_y[i],
        just = "left",
        gp = gpar(
          fontsize = 11,
          col = "#26354A"
        )
      )

      if (proportions[i] > 0) {
        grid.rect(
          x = 0.70,
          y = row_y[i],
          width = 0.26 * proportions[i],
          height = 0.14,
          just = c("left", "centre"),
          gp = gpar(
            fill = class_colors[class_name],
            col = NA
          )
        )
      }
    }
  }

  # 6. Plot -----------------------------------------------------------

  plot(
    tree,
    inner_panel = node_panel,
    terminal_panel = node_panel,
    edge_panel = edge_simple,
    ep_args = list(
      just = "equal",
      fill = "white"
    ),
    drop_terminal = FALSE,
    tnex = 1,
    margins = c(0.5, 0.5, 0.5, 0.5),
    gp = gpar(
      fontsize = 12,
      col = "#334155"
    )
  )

  # 7. Add class legend -----------------------------------------------

  # Return to the root viewport
  grid::upViewport(0)

  # Position legend in the bottom-right area
  grid::pushViewport(
    grid::viewport(
      x = 0.77,
      y = 0.16,
      width = unit(2.7, "in"),
      height = unit(1.1, "in"),
      just = c("left", "bottom")
    )
  )

  # Legend background
  grid::grid.rect(
    gp = grid::gpar(
      fill = "white",
      col = "#64748B",
      lwd = 1
    )
  )

  # Title
  grid::grid.text(
    "Respond to Advertisement",
    x = 0.06,
    y = 0.82,
    just = "left",
    gp = grid::gpar(
      fontsize = 13,
      fontface = "bold"
    )
  )

  # Class labels and colored squares
  for (i in seq_along(class_colors)) {

    y <- c(0.53, 0.23)[i]

    grid::grid.rect(
      x = 0.12,
      y = y,
      width = 0.09,
      height = 0.20,
      gp = grid::gpar(
        fill = class_colors[i],
        col = NA
      )
    )

    grid::grid.text(
      names(class_colors)[i],
      x = 0.21,
      y = y,
      just = "left",
      gp = grid::gpar(
        fontsize = 12,
        fontface = "bold"
      )
    )
  }

  grid::popViewport()
}
