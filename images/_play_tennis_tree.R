library(grid)

grid.newpage()

# ------------------------------------------------------------
# Styling matching the partykit tree
# ------------------------------------------------------------

node_fill <- "white"
node_border <- "#333333"

node_w <- 0.22
node_h <- 0.20

# ------------------------------------------------------------
# Node positions
# ------------------------------------------------------------

root_x <- 0.50
root_y <- 0.72

left_x <- 0.25
left_y <- 0.28

right_x <- 0.75
right_y <- 0.28

# ------------------------------------------------------------
# Branches
# ------------------------------------------------------------

grid.lines(
  x = unit(c(root_x - 0.02, left_x), "npc"),
  y = unit(c(root_y - node_h / 2, left_y + node_h / 2), "npc"),
  gp = gpar(
    col = "#333333",
    lwd = 1
  )
)

grid.lines(
  x = unit(c(root_x + 0.02, right_x), "npc"),
  y = unit(c(root_y - node_h / 2, right_y + node_h / 2), "npc"),
  gp = gpar(
    col = "#333333",
    lwd = 1
  )
)

# ------------------------------------------------------------
# Branch labels
# ------------------------------------------------------------

grid.text(
  "light",
  x = 0.15,
  y = 0.48,
  gp = gpar(
    fontsize = 24
  )
)

grid.text(
  "strong",
  x = 0.85,
  y = 0.48,
  gp = gpar(
    fontsize = 24
  )
)

# ------------------------------------------------------------
# Nodes
# ------------------------------------------------------------

grid.rect(
  x = root_x,
  y = root_y,
  width = node_w,
  height = node_h,
  gp = gpar(
    fill = node_fill,
    col = node_border,
    lwd = 1
  )
)

grid.rect(
  x = left_x,
  y = left_y,
  width = node_w,
  height = node_h,
  gp = gpar(
    fill = node_fill,
    col = node_border,
    lwd = 1
  )
)

grid.rect(
  x = right_x,
  y = right_y,
  width = node_w,
  height = node_h,
  gp = gpar(
    fill = node_fill,
    col = node_border,
    lwd = 1
  )
)

# ------------------------------------------------------------
# Split-variable label
# ------------------------------------------------------------

grid.text(
  "wind",
  x = root_x,
  y = 0.53,
  gp = gpar(
    fontsize = 24,
    fontface = "bold"
  )
)