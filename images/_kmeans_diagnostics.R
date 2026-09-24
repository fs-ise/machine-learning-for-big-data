plot_kmeans_elbow <- function(X) {
  elbow <- map_dfr(1:9, \(k) {
    set.seed(42)

    km <- kmeans(
      X,
      centers = k,
      nstart = 25
    )

    tibble(
      k = k,
      withinss = km$tot.withinss
    )
  })

  ggplot(elbow, aes(k, withinss)) +
    geom_line() +
    geom_point() +
    labs(
      x = "Number of clusters (k)",
      y = "Within-cluster sum of squares"
    )
}

plot_kmeans_silhouette <- function(X) {
  silhouette_scores <- map_dfr(2:9, \(k) {
    set.seed(42)

    km <- kmeans(
      X,
      centers = k,
      nstart = 25
    )

    s <- cluster::silhouette(
      km$cluster,
      dist(X)
    )

    tibble(
      k = k,
      silhouette = mean(s[, "sil_width"])
    )
  })

  ggplot(
    silhouette_scores,
    aes(k, silhouette)
  ) +
    geom_line() +
    geom_point() +
    labs(
      x = "Number of clusters (k)",
      y = "Average silhouette score"
    )
}
