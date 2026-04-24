import argparse
from pathlib import Path
from typing import List, Optional

import matplotlib.pyplot as plt
import pandas as pd
from pandas.plotting import scatter_matrix
from sklearn.decomposition import PCA


IGNORED_COLUMNS = {"theta_deg", "theta", "angle", "theta_degree"}


def infer_csv_path(model_name: str, base_dir: Path) -> Path:
    """Return sources/models/{model_name}/standard_model.csv relative to base_dir."""
    return base_dir / "sources" / "models" / model_name / "standard_model.csv"



def find_label_column(df: pd.DataFrame) -> Optional[str]:
    """Pick the first non-numeric column as the label column."""
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            return col
    return None



def find_dimension_columns(df: pd.DataFrame) -> List[str]:
    """Return numeric dimensions, ignoring theta-like columns."""
    dims = []
    for col in df.columns:
        if col.lower() in IGNORED_COLUMNS:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            dims.append(col)
    return dims



def annotate_points(ax, df: pd.DataFrame, x_col: str, y_col: str, label_col: Optional[str]) -> None:
    if label_col is None:
        return
    for _, row in df.iterrows():
        ax.annotate(str(row[label_col]), (row[x_col], row[y_col]), fontsize=8, alpha=0.8)



def plot_1d(df: pd.DataFrame, dim: str, label_col: Optional[str], out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(df[dim], bins=min(20, max(5, len(df) // 2)))
    ax.set_title(f"1D distribution of {dim}")
    ax.set_xlabel(dim)
    ax.set_ylabel("count")
    fig.tight_layout()
    fig.savefig(out_dir / f"hist_{dim}.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 2.5))
    ax.scatter(df[dim], [0] * len(df))
    if label_col is not None:
        for _, row in df.iterrows():
            ax.annotate(str(row[label_col]), (row[dim], 0), fontsize=8, rotation=35)
    ax.set_title(f"1D labeled positions for {dim}")
    ax.set_xlabel(dim)
    ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(out_dir / f"positions_{dim}.png", dpi=200)
    plt.close(fig)



def plot_2d(df: pd.DataFrame, dims: List[str], label_col: Optional[str], out_dir: Path) -> None:
    x_col, y_col = dims
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(df[x_col], df[y_col])
    ax.axhline(0, linewidth=1)
    ax.axvline(0, linewidth=1)
    annotate_points(ax, df, x_col, y_col, label_col)
    ax.set_title(f"2D conceptual space: {x_col} vs {y_col}")
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_aspect("equal" if df[x_col].between(-1.1, 1.1).all() and df[y_col].between(-1.1, 1.1).all() else "auto")
    fig.tight_layout()
    fig.savefig(out_dir / f"scatter_{x_col}_{y_col}.png", dpi=200)
    plt.close(fig)



def plot_3d(df: pd.DataFrame, dims: List[str], label_col: Optional[str], out_dir: Path) -> None:
    fig = plt.figure(figsize=(9, 8))
    ax = fig.add_subplot(111, projection="3d")
    x_col, y_col, z_col = dims
    ax.scatter(df[x_col], df[y_col], df[z_col])
    if label_col is not None:
        for _, row in df.iterrows():
            ax.text(row[x_col], row[y_col], row[z_col], str(row[label_col]), fontsize=8)
    ax.set_title(f"3D conceptual space: {x_col}, {y_col}, {z_col}")
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_zlabel(z_col)
    fig.tight_layout()
    fig.savefig(out_dir / f"scatter3d_{x_col}_{y_col}_{z_col}.png", dpi=200)
    plt.close(fig)



def plot_high_dimensional(df: pd.DataFrame, dims: List[str], out_dir: Path) -> None:
    scatter_ax = scatter_matrix(df[dims], figsize=(12, 12), diagonal="hist")
    plt.suptitle("Scatter matrix of dimensions", y=0.98)
    plt.tight_layout()
    plt.savefig(out_dir / "scatter_matrix.png", dpi=200)
    plt.close()

    pca = PCA(n_components=2)
    reduced = pca.fit_transform(df[dims])

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(reduced[:, 0], reduced[:, 1])
    ax.set_title("PCA projection to 2D")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.2%} var)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.2%} var)")
    fig.tight_layout()
    fig.savefig(out_dir / "pca_2d.png", dpi=200)
    plt.close(fig)



def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize a standard emotion model CSV.")
    parser.add_argument("model_name", help="Model name inside sources/models/{model_name}/standard_model.csv")
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Project root directory. Defaults to the current directory.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    csv_path = infer_csv_path(args.model_name, base_dir)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    label_col = find_label_column(df)
    dims = find_dimension_columns(df)

    if not dims:
        raise ValueError("No numeric dimensions found after ignoring theta-like columns.")

    out_dir = csv_path.parent / "visualizations"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded: {csv_path}")
    print(f"Rows: {len(df)}")
    print(f"Label column: {label_col}")
    print(f"Dimensions ({len(dims)}): {dims}")
    print(f"Saving plots to: {out_dir}")

    if len(dims) == 1:
        plot_1d(df, dims[0], label_col, out_dir)
    elif len(dims) == 2:
        plot_2d(df, dims, label_col, out_dir)
    elif len(dims) == 3:
        plot_3d(df, dims, label_col, out_dir)
    else:
        plot_high_dimensional(df, dims, out_dir)

    print("Done.")


if __name__ == "__main__":
    main()
