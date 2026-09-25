plot_play_tennis_id3_tree <- function() {
  library(partykit)
  library(grid)

  # 1. Play Tennis dataset -------------------------------------------

  tennis <- data.frame(
    outlook = factor(
      c("sunny", "sunny", "overcast", "rainy", "rainy",
        "rainy", "overcast", "sunny", "sunny", "rainy",
        "sunny", "overcast", "overcast", "rainy"),
      levels = c("sunny", "overcast", "rainy")
    ),
    humidity = factor(
      c("high", "high", "high", "high", "normal",
        "normal", "normal", "high", "normal", "normal",
        "normal", "high", "normal", "high"),
      levels = c("high", "normal")
    ),
    wind = factor(
      c("light", "strong", "light", "light", "light",
        "strong", "strong", "light", "light", "light",
        "strong", "strong", "light", "strong"),
      levels = c("light", "strong")
    ),
    play = factor(
      c("no", "no", "yes", "yes", "yes",
        "no", "yes", "no", "yes", "yes",
        "yes", "yes", "yes", "no"),
      levels = c("no", "yes")
    )
  )

  # 2. Construct the exact ID3 tree -----------------------------------

  nodes <- partynode(
    id = 1L,
    split = partysplit(1L, index = 1:3),
    kids = list(

      # Outlook = sunny -> Humidity
      partynode(
        id = 2L,
        split = partysplit(2L, index = 1:2),
        kids = list(
          partynode(3L),  # High -> No
          partynode(4L)   # Normal -> Yes
        )
      ),

      # Outlook = overcast -> Yes
      partynode(5L),

      # Outlook = rainy -> Wind
      partynode(
        id = 6L,
        split = partysplit(3L, index = 1:2),
        kids = list(
          partynode(7L),  # Light -> Yes
          partynode(8L)   # Strong -> No
        )
      )
    )
  )

  tree <- party(
    node = nodes,
    data = tennis,
    fitted = data.frame(
      "(fitted)" = fitted_node(nodes, tennis),
      "(response)" = tennis$play,
      check.names = FALSE
    ),
    terms = terms(play ~ ., data = tennis)
  )

  tree <- as.constparty(tree)


  # 3. Define node labels ---------------------------------------------

  split_names <- c(
    "1" = "Outlook",
    "2" = "Humidity",
    "6" = "Wind"
  )

  class_colors <- c(
    "no" = "#0000FF",
    "yes" = "#00EE00"
  )


  # 4. Compact node panel ---------------------------------------------

  node_panel <- function(node) {

    id <- id_node(node)

    # Retrieve observations belonging to this node
    node_data <- data_party(tree, id = id)

    counts <- table(
      factor(node_data$play, levels = c("no", "yes"))
    )

    n <- sum(counts)
    proportions <- as.numeric(counts) / n
    percentages <- round(100 * proportions)

    # Split variable for internal nodes;
    # sample size only for terminal nodes
    if (as.character(id) %in% names(split_names)) {
      label <- sprintf(
        "%s (n = %d)",
        split_names[as.character(id)],
        n
      )
    } else {
      label <- sprintf("n = %d", n)
    }

    # Compact node viewport
    pushViewport(
      viewport(
        width = unit(0.94, "npc"),
        height = unit(0.85, "in")
      )
    )

    # Node background and border
    grid.rect(
      gp = gpar(
        fill = "white",
        col = "#333333",
        lwd = 1
      )
    )

    # Two class rows
    row_y <- c(0.76, 0.46)

    for (i in seq_along(counts)) {

      class_name <- names(counts)[i]

      # Class label, count, and percentage
      grid.text(
        sprintf(
          "%s: %d (%d%%)",
          class_name,
          counts[i],
          percentages[i]
        ),
        x = 0.04,
        y = row_y[i],
        just = "left",
        gp = gpar(fontsize = 10)
      )

      # Horizontal class-distribution bar
      if (proportions[i] > 0) {

        grid.rect(
          x = 0.68,
          y = row_y[i],
          width = 0.27 * proportions[i],
          height = 0.17,
          just = c("left", "centre"),
          gp = gpar(
            fill = class_colors[class_name],
            col = NA
          )
        )
      }
    }

    # Split variable BELOW the class distributions
    grid.text(
      label,
      x = 0.5,
      y = 0.14,
      gp = gpar(
        fontsize = 11,
        fontface = "bold"
      )
    )

    popViewport()
  }


  # 5. Plot using native partykit layout ------------------------------

  plot(
    tree,

    # Custom contents, automatic node positioning
    inner_panel = node_panel,
    terminal_panel = node_panel,

    # Native branch labels
    edge_panel = edge_simple,
    ep_args = list(
      just = "equal"
    ),

    # Keep early terminal nodes at their natural depth
    drop_terminal = FALSE,

    # Compact terminal nodes
    tnex = 1,

    # Margins
    margins = c(1, 1, 1, 1),

    # Typography
    gp = gpar(fontsize = 12)
  )
}
