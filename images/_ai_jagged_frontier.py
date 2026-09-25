def plot_ai_jagged_frontier():
    import numpy as np
    import matplotlib.pyplot as plt

    # Categories (axes)
    labels = [
        "Knowledge",
        "Reading & Writing",
        "Math",
        "Reasoning",
        "Working Memory",
        "Memory Storage",
        "Memory Retrieval",
        "Visual",
        "Auditory",
        "Speed"
    ]

    # Example scores (approximate values from the illustration)
    gpt4 = [8, 6, 4, 0, 2, 0, 4, 0, 0, 3]
    gpt5 = [9, 10, 10, 7, 4, 0, 4, 4, 6, 3]

    # Close the polygon
    gpt4 = gpt4 + [gpt4[0]]
    gpt5 = gpt5 + [gpt5[0]]

    # Compute angles
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]

    # Create figure
    # fig, ax = plt.subplots(figsize=(6,6), subplot_kw=dict(polar=True))
    fig, ax = plt.subplots(figsize=(6,6), subplot_kw=dict(polar=True))

    ax.set_theta_offset(np.pi / 2)   # rotate so first label is at top
    ax.set_theta_direction(-1)       # make axes go clockwise

    # Plot data
    ax.plot(angles, gpt5, linewidth=2, label="GPT-5 (2025)")
    ax.fill(angles, gpt5, alpha=0.15)

    ax.plot(angles, gpt4, linewidth=2, label="GPT-4 (2023)")
    ax.fill(angles, gpt4, alpha=0.15)

    # Axis labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)

    # Radial limits
    ax.set_ylim(0, 10)

    # Grid and legend
    ax.set_title("AI Capabilities", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    plt.show()
