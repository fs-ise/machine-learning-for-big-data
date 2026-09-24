def plot_svm_margin():
    import numpy as np
    import matplotlib.pyplot as plt
    from sklearn import svm

    np.random.seed(42)

    n = 50

    # clusters closer together + lower variance
    X_success = np.random.normal(loc=[4.5, 4.5], scale=0.4, size=(n, 2))
    X_unsuccess = np.random.normal(loc=[6.0, 6.0], scale=0.4, size=(n, 2))

    X = np.vstack((X_success, X_unsuccess))
    y = np.hstack((np.ones(n), -np.ones(n)))

    # moderately large C → tight but visible margin
    model = svm.SVC(kernel="linear", C=100)
    model.fit(X, y);

    fig, ax = plt.subplots(figsize=(6, 5))

    # plot points
    ax.scatter(X_success[:, 0], X_success[:, 1], marker="o", s=35, label="Successful")
    ax.scatter(X_unsuccess[:, 0], X_unsuccess[:, 1], marker="x", s=35, label="Unsuccessful")

    # highlight support vectors
    ax.scatter(
        model.support_vectors_[:, 0],
        model.support_vectors_[:, 1],
        s=120,
        facecolors="none",
        edgecolors="black",
        linewidths=1.5,
        label="Support vectors",
    )

    # decision boundary and margins
    xx = np.linspace(3.5, 7, 200)
    yy = np.linspace(3.5, 7, 200)
    YY, XX = np.meshgrid(yy, xx)
    xy = np.vstack([XX.ravel(), YY.ravel()]).T
    Z = model.decision_function(xy).reshape(XX.shape)

    ax.contour(XX, YY, Z, levels=[0], linewidths=2);
    ax.contour(XX, YY, Z, levels=[-1, 1], linestyles="--");

    # zoom in → makes margins visually closer
    ax.set_xlim(3.8, 6.8);
    ax.set_ylim(3.8, 6.8);

    ax.set_xlabel("Team size")
    ax.set_ylabel("Experience")
    ax.legend()
    plt.show()
    return fig
