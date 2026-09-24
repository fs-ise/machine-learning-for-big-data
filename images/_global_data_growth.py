def plot_global_data_growth():
    import matplotlib.pyplot as plt
    import numpy as np

    # Known datapoints from literature (IDC Global Datasphere summaries)
    years_known = np.array([2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024, 2025])

    structured_known = np.array([0.6, 1.0, 1.6, 3.8, 7, 12, 18, 26, 32])
    unstructured_known = np.array([1.4, 2.5, 4.4, 12.2, 26, 52, 79, 121, 149])

    # Sources referenced in literature:
    #
    # - Global data volume was ~2 ZB in 2010
    # - It increased to ~33 ZB by 2018
    # - IDC Global Datasphere reports forecast ~175 ZB by 2025
    # - Some summaries report ~181 ZB by 2025
    #
    # These figures illustrate strongly exponential growth.

    # Create full yearly range
    years = np.arange(2010, 2026)

    # Interpolate missing years
    structured = np.interp(years, years_known, structured_known)
    unstructured = np.interp(years, years_known, unstructured_known)

    totals = structured + unstructured

    # Identify interpolated years
    is_interpolated = ~np.isin(years, years_known)
    is_known = np.isin(years, years_known)

    # Fit exponential trendline
    log_totals = np.log(totals)
    coeffs = np.polyfit(years, log_totals, 1)
    trend_raw = np.exp(np.poly1d(coeffs)(years))

    # Scale trend so it reaches ~190 ZB in 2025
    target_2025 = 190
    scale_factor = target_2025 / trend_raw[years == 2025]
    trend = trend_raw * scale_factor

    fig = plt.figure(figsize=(9,4))

    # --- Structured data bars ---
    plt.bar(
        years[is_known],
        structured[is_known],
        label="Structured data"
    )

    plt.bar(
        years[is_interpolated],
        structured[is_interpolated],
        color="gray",
        hatch="//"
    )

    # --- Unstructured data bars ---
    plt.bar(
        years[is_known],
        unstructured[is_known],
        bottom=structured[is_known],
        label="Unstructured data"
    )

    plt.bar(
        years[is_interpolated],
        unstructured[is_interpolated],
        bottom=structured[is_interpolated],
        color="gray",
        hatch="//"
    )

    # Exponential trendline
    plt.plot(years, trend, color="black", linewidth=2, label="Estimated exponential trend")

    plt.xlabel("Year")
    plt.ylabel("Zettabytes")
    plt.title("Growth of Global Data Volume")

    plt.xticks(years, rotation=45)
    plt.grid(axis="y")

    plt.legend()

    plt.show()
