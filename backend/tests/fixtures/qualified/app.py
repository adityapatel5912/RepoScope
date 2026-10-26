from services import Cache, Repo


def run() -> str:
    repo: Repo = Repo()
    return repo.save()


def inferred() -> str:
    repo = Repo()
    return repo.load()


def annotated_parameter(repo: Repo) -> str:
    return repo.save()


class Controller:
    def __init__(self) -> None:
        self.repo = Repo()

    def persist(self) -> str:
        # Chained receiver: must stay unresolved rather than becoming
        # Controller.save() (which would be a wrong edge).
        return self.repo.save()

    def save(self) -> str:
        return "controller-saved"


def shadowed() -> str:
    repo: Repo = Repo()
    repo = Cache()
    return repo.save()


def after_shadow() -> str:
    repo: Repo = Repo()
    return repo.save()
