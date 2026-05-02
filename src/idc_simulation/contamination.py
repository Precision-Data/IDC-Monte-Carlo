"""Closed-form contamination function (ANALYSIS_PLAN.md Section 5.1).

The IDC contamination function gives the expected per-confabulation
contribution to cumulative contamination at encounter index ``n``:

    Contamination(n) = E0 * epsilon * (1 - P^(n+1)) / (1 - P) * (1 - R)^n

with parameters

    E0       initial confabulation rate per AI-generated claim,
    epsilon  entrenchment rate (escapes review and is signed),
    P        per-encounter propagation factor,
    R        per-encounter de-entrenchment rate,
    n        encounter index, n in {0, 1, 2, ...}.

The implementation is vectorised across parameter samples: pass equal-
length arrays for the four parameters and a scalar (or compatible-shape
array) for ``n``. The rising geometric series factor

    G(P, n) = (1 - P^(n+1)) / (1 - P)

has a removable singularity at ``P = 1``, where L'Hopital gives the
limit ``n + 1``. The implementation handles this branch numerically.
"""

from __future__ import annotations

from typing import Union

import numpy as np
from numpy.typing import NDArray

# Tolerance below which |1 - P| is treated as zero and the L'Hopital
# limit ``(n + 1)`` is used instead of the geometric-series form. Beta
# samples cannot equal 1.0 exactly, so this branch is taken only when
# round-trip floating-point arithmetic loses all precision in (1 - P).
_P_NEAR_ONE_TOL: float = 1e-12

ArrayLike = Union[float, NDArray[np.floating]]


def geometric_sum_factor(P: ArrayLike, n: ArrayLike) -> NDArray[np.float64]:
    """Return ``(1 - P^(n+1)) / (1 - P)`` with the L'Hopital branch at P=1.

    For ``|1 - P| < _P_NEAR_ONE_TOL`` the function returns ``n + 1``.
    Defined element-wise on numpy arrays.
    """
    P_arr = np.asarray(P, dtype=np.float64)
    n_arr = np.asarray(n, dtype=np.float64)
    one_minus_P = 1.0 - P_arr
    near_one = np.abs(one_minus_P) < _P_NEAR_ONE_TOL

    safe_denom = np.where(near_one, 1.0, one_minus_P)
    main = (1.0 - np.power(P_arr, n_arr + 1.0)) / safe_denom
    return np.where(near_one, n_arr + 1.0, main)


def contamination(
    E0: ArrayLike,
    epsilon: ArrayLike,
    P: ArrayLike,
    R: ArrayLike,
    n: ArrayLike,
) -> NDArray[np.float64]:
    """Evaluate the IDC contamination function element-wise.

    All parameter inputs must be broadcastable. ``n`` may be a scalar or
    an array of the same shape as the parameters. The returned array
    has the broadcast shape of ``(E0, epsilon, P, R, n)``.

    Parameters
    ----------
    E0, epsilon, P, R
        Per-sample parameter values in [0, 1].
    n
        Encounter index, n >= 0.

    Returns
    -------
    np.ndarray
        Per-confabulation contamination at horizon ``n``.
    """
    E0_a = np.asarray(E0, dtype=np.float64)
    eps_a = np.asarray(epsilon, dtype=np.float64)
    P_a = np.asarray(P, dtype=np.float64)
    R_a = np.asarray(R, dtype=np.float64)
    n_a = np.asarray(n, dtype=np.float64)

    if np.any(n_a < 0):
        raise ValueError("n must be non-negative")

    geom = geometric_sum_factor(P_a, n_a)
    decay = np.power(1.0 - R_a, n_a)
    return E0_a * eps_a * geom * decay
