class Repo:
    """A tiny repository-shaped service used by the tier-4 fixtures."""

    def save(self) -> str:
        return "saved"

    def load(self) -> str:
        return "loaded"


class Cache:
    def __init__(self) -> None:
        self.repo = Repo()

    def save(self) -> str:
        return "cache-saved"
