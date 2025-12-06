import numpy as np
import pandas as pd

__all__ = [
    "compute_grassmannian_distance",
]

# https://arxiv.org/pdf/1808.02229.pdf
c_dict = {"Geodesic": (np.pi / 2), "Chordal": 1, "Procrustes": 1}
dist_funcs = {
    "Geodesic": lambda theta: np.linalg.norm(theta),
    "Chordal": lambda theta: 2 * np.linalg.norm(np.sin(theta)),
    "Procrustes": lambda theta: 2 * np.linalg.norm(np.sin(theta / 2)),
}


def compute_grassmannian_distance(
    tensor: np.ndarray,
    reference: np.ndarray,
    is_tensor_orth: bool = False,
    is_reference_orth: bool = False,
    perm_no: int = 0,
):
    """Implementation of the grassmannian distance.

    Parameters
    ----------
    tensor : np.ndarray
        Input embeddings.
    reference : np.ndarray
        Input reference.
    is_tensor_orth : bool, optional
        Whether the input embeddings are orthonormal, by default False
    is_reference_orth : bool, optional
        Whether the input reference is orthonormal, by default False
    perm_no : int, optional
        Number of permutations, by default 0

    Returns
    -------
        dists
        u
        s
        u
        vh
        principal_directions_tensor
        principal_directions_reference
        tensor_basis
        reference_basis
    """
    # re-orient (if needed) to match the first dims
    row_matched = tensor.shape[0] == reference.shape[0]
    col_matched = tensor.shape[1] == reference.shape[1]
    if col_matched and not row_matched:
        tensor = tensor.T
        reference = reference.T

    if not is_tensor_orth:
        tensor_basis, _, _ = np.linalg.svd(tensor, compute_uv=True, full_matrices=False)
    else:
        tensor_basis = tensor

    if not is_reference_orth:
        reference_basis, _, _ = np.linalg.svd(reference, compute_uv=True, full_matrices=False)
    else:
        reference_basis = reference

    min_dim = min(tensor_basis.shape[1], reference_basis.shape[1])
    max_dim = max(tensor_basis.shape[1], reference_basis.shape[1])
    delta_dim = max_dim - min_dim

    # Compute the cross-product of basis vectors
    C = tensor_basis.T @ reference_basis

    u, s, vh = np.linalg.svd(C)

    s = s[s < 1]
    theta = np.arccos(s)  # Principal angles

    dists = {k: v(theta) for k, v in dist_funcs.items()}

    # From: https://arxiv.org/abs/1407.0900
    metrics = {k: np.sqrt(delta_dim * (c_dict[k] ** 2) + v**2) for k, v in dists.items()}

    if 0 < perm_no:
        theta_rand = np.arccos(
            np.clip(
                np.array(
                    [
                        np.linalg.svd(
                            tensor_basis[np.random.permutation(
                                tensor_basis.shape[0]), :].T @ reference_basis,
                            full_matrices=True,
                            compute_uv=False,
                        )
                        for _ in range(perm_no)
                    ]
                ),
                0,
                1,
            )
        )
        dists_rand = np.array(
            [[v(theta_rand[i, :]) for k, v in dist_funcs.items()]
                for i in range(theta_rand.shape[0])]
        )
        metrics_rand = pd.DataFrame(
            {
                k: np.sqrt(delta_dim * (c_dict[k] ** 2) + dists_rand[:, j] ** 2)
                for j, (k, v) in enumerate(dist_funcs.items())
            }
        ).to_numpy()
        metrics_z = (np.array(list(metrics.values())) -
                     metrics_rand.mean(axis=0)) / metrics_rand.std(axis=0)
    else:
        metrics_z = np.zeros(len(metrics))

    metrics_z = dict(zip(list(dist_funcs.keys()), metrics_z, strict=False))

    principal_directions_tensor = tensor_basis @ u
    principal_directions_reference = reference_basis @ vh.T

    return (
        dists,
        metrics,
        metrics_z,
        principal_directions_tensor,
        principal_directions_reference,
        u,
        s,
        u,
        vh,
        tensor_basis,
        reference_basis,
    )
