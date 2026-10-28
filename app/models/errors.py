"""Feil som domenemodellen og repositoryene kaster."""


class ValidationError(Exception):
    """Ugyldige data. messages: {feltnavn: melding}."""

    def __init__(self, messages):
        super().__init__(messages)
        self.messages = messages


class InvalidTransitionError(ValidationError):
    """Overgangen er ikke lov i tilstandsmaskinen (design.md §4 og §5)."""


class DuplicateEmailError(Exception):
    """Det finnes allerede en bruker med denne e-postadressen."""
