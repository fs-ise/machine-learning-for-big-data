library(partykit)
library(grid)

# Construct a tree from specified class frequencies.
make_stump <- function(
    variable,
    threshold,
    left_value,
    right_value,
    left_counts,
    right_counts,
    reverse = FALSE
) {

  make_leaf <- function(value, counts) {
    data.frame(
      x = rep(value, sum(counts)),
      respond = factor(
        rep(names(counts), times = counts),
        levels = c("no", "yes")
      )
    )
  }

  data <- rbind(
    make_leaf(left_value, left_counts),
    make_leaf(right_value, right_counts)
  )

  names(data)[1] <- variable

  # Reverse the interval mapping when the larger
  # values should appear on the left.
  split_index <- if (reverse) {
    c(2L, 1L)
  } else {
    c(1L, 2L)
  }

  nodes <- partynode(
    id = 1L,
    split = partysplit(
      varid = 1L,
      breaks = threshold,
      right = FALSE,
      index = split_index
    ),
    kids = list(
      partynode(2L),
      partynode(3L)
    )
  )

  tree <- party(
    node = nodes,
    data = data,
    fitted = data.frame(
      "(fitted)" = fitted_node(nodes, data),
      "(response)" = data$respond,
      check.names = FALSE
    ),
    terms = terms(respond ~ ., data = data)
  )

  as.constparty(tree)
}


# Define the exact two trees.

income_tree <- make_stump(
  variable = "income",
  threshold = 1000,
  left_value = 1500,
  right_value = 500,
  left_counts = c(no = 20L, yes = 30L),
  right_counts = c(no = 30L, yes = 20L),
  reverse = TRUE
)

age_tree <- make_stump(
  variable = "age",
  threshold = 25,
  left_value = 20,
  right_value = 30,
  left_counts = c(no = 42L, yes = 10L),
  right_counts = c(no = 8L, yes = 40L)
)


# Verify the displayed frequencies.

node_counts <- function(tree, id) {
  as.integer(
    table(
      factor(
        data_party(tree, id = id)$respond,
        levels = c("no", "yes")
      )
    )
  )
}

stopifnot(
  identical(node_counts(income_tree, 1L), c(50L, 50L)),
  identical(node_counts(income_tree, 2L), c(20L, 30L)),
  identical(node_counts(income_tree, 3L), c(30L, 20L)),
  identical(node_counts(age_tree, 1L), c(50L, 50L)),
  identical(node_counts(age_tree, 2L), c(42L, 10L)),
  identical(node_counts(age_tree, 3L), c(8L, 40L))
)


# Shared node design.

class_colors <- c(
  no = "#3264C8",
  yes = "#17A85A"
)

make_node_panel <- function(tree, split_label) {

  function(node) {

    id <- id_node(node)

    counts <- table(
      factor(
        data_party(tree, id = id)$respond,
        levels = c("no", "yes")
      )
    )

    n <- sum(counts)
    proportions <- as.numeric(counts) / n

    # Root: splitting variable.
    # Leaves: majority-class prediction.

    if (id == 1L) {
      label <- split_label
      header_fill <- "#EAF0F7"
    } else {
      label <- paste(
        "Predict:",
        names(which.max(counts))
      )
      header_fill <- "#F0F5F1"
    }

    # Node background
    grid.rect(
      width = 0.96,
      height = 0.90,
      gp = gpar(
        fill = "white",
        col = "#64748B",
        lwd = 1
      )
    )

    # Header background
    grid.rect(
      x = 0.5,
      y = 0.81,
      width = 0.96,
      height = 0.24,
      gp = gpar(
        fill = header_fill,
        col = NA
      )
    )

    # Header label
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

    # Class distribution
    row_y <- c(0.51, 0.28)

    for (i in seq_along(counts)) {

      class_name <- names(counts)[i]

      grid.text(
        sprintf(
          "%s %d (%.0f%%)",
          class_name,
          counts[i],
          100 * proportions[i]
        ),
        x = 0.04,
        y = row_y[i],
        just = "left",
        gp = gpar(
          fontsize = 11,
          col = "#26354A"
        )
      )

      # Horizontal bar
      if (proportions[i] > 0) {

        grid.rect(
          x = 0.73,
          y = row_y[i],
          width = 0.23 * proportions[i],
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
}


# Shared plotting function.

plot_stump <- function(tree, label) {

  panel <- make_node_panel(tree, label)

  plot(
    tree,
    inner_panel = panel,
    terminal_panel = panel,
    edge_panel = edge_simple,
    ep_args = list(
      just = "equal",
      fill = "white"
    ),
    drop_terminal = FALSE,
    tnex = 1,
    gp = gpar(
      fontsize = 12,
      col = "#334155"
    )
  )
}
