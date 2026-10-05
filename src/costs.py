"""Expected dollar cost of each action for a transaction.

Each function takes the calibrated fraud probability `p` and, where needed, the
amount and the `costs` section of config.yaml. They work on single numbers and,
unchanged, on whole pandas columns or numpy arrays at once.
"""


def approve_cost(p, amount):
    """Expected cost of approving: p x amount.

    Assumptions: an approved fraud loses its whole amount (no chargeback or
    recovery), and an approved legitimate transaction costs nothing.
    """
    return p * amount


def review_cost(p, costs: dict):
    """Expected cost of sending to an analyst: the review cost, whatever p is.

    Assumptions: one review costs `review_cost_usd`; the analyst always catches a
    fraud (so nothing is lost) and always approves a legitimate transaction (so
    no customer is wrongly declined).
    """
    return p * 0 + costs["review_cost_usd"]  # p * 0 keeps the shape when p is a column


def block_cost(p, costs: dict):
    """Expected cost of blocking: (1 - p) x false-decline cost.

    Assumptions: blocking a legitimate customer costs `false_decline_cost_usd`
    (lost sale, support call, annoyance); blocking a fraud costs nothing.
    """
    return (1 - p) * costs["false_decline_cost_usd"]
