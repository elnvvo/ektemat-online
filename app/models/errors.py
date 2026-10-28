"""Feil som domenemodellen og repositoryene kaster."""


class ValidationError(Exception):
    """Ugyldige data. messages: {feltnavn: melding}."""

    def __init__(self, messages):
        super().__init__(messages)
        self.messages = messages


class InvalidTransitionError(ValidationError):
    """Overgangen er ikke lov i tilstandsmaskinen (design.md §4 og §5)."""


class AlreadyAnsweredError(ValidationError):
    """Et spørsmål kan bare ha ett svar (design.md §2: Question 1 *-- 0..1 Answer)."""

    def __init__(self):
        super().__init__({"text": "Spørsmålet er allerede besvart."})


class DuplicateEmailError(Exception):
    """Det finnes allerede en bruker med denne e-postadressen."""
