library(tidyverse)

set.seed(42)

n_specialists <- 100
n_coordinators <- 200
n_balanced <- 500

specialists <- tibble(
  profile = "Specialist",
  meeting_hours = rnorm(n_specialists, mean = 6, sd = 2.5),
  focus_hours = rnorm(n_specialists, mean = 30, sd = 3.5),
  remote_share = rnorm(n_specialists, mean = 0.75, sd = 0.10),
  performance = rnorm(n_specialists, mean = 82, sd = 7),
  job_satisfaction = rnorm(n_specialists, mean = 7.5, sd = 1.0)
)

coordinators <- tibble(
  profile = "Coordinator",
  meeting_hours = rnorm(n_coordinators, mean = 28, sd = 3.5),
  focus_hours = rnorm(n_coordinators, mean = 8, sd = 3),
  remote_share = rnorm(n_coordinators, mean = 0.35, sd = 0.12),
  performance = rnorm(n_coordinators, mean = 76, sd = 8),
  job_satisfaction = rnorm(n_coordinators, mean = 6.8, sd = 1.1)
)

balanced <- tibble(
  profile = "Balanced",
  meeting_hours = rnorm(n_balanced, mean = 17, sd = 3),
  focus_hours = rnorm(n_balanced, mean = 19, sd = 3),
  remote_share = rnorm(n_balanced, mean = 0.55, sd = 0.11),
  performance = rnorm(n_balanced, mean = 86, sd = 6),
  job_satisfaction = rnorm(n_balanced, mean = 8.0, sd = 0.9)
)

employee_work_df <- bind_rows(
  specialists,
  coordinators,
  balanced
) |>
  mutate(
    employee_id = sprintf("E%04d", row_number()),
    meeting_hours = pmax(meeting_hours, 0),
    focus_hours = pmax(focus_hours, 0),
    remote_share = pmin(pmax(remote_share, 0), 1),
    performance = pmin(pmax(performance, 0), 100),
    job_satisfaction = pmin(pmax(job_satisfaction, 1), 10)
  ) |>
  select(
    employee_id,
    meeting_hours,
    focus_hours,
    remote_share,
    performance,
    job_satisfaction,
    profile
  )

employee_work_df |>
  select(-profile) |>
  write_csv("employee_work_profiles.csv")

employee_work_df |>
  ggplot(
    aes(
      x = meeting_hours,
      y = focus_hours,
      color = profile
    )
  ) +
  geom_point(alpha = 0.5) +
  labs(
    x = "Meeting hours per week",
    y = "Focus hours per week",
    color = "True profile"
  )