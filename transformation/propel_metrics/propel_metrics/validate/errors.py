"""Validation error types with stable codes and JSON-path locators."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ValidationError:
    code: str
    path: str
    message: str
    file: str | None = None

    def format(self) -> str:
        loc = f"{self.file}:" if self.file else ""
        return f"{loc}{self.path}: [{self.code}] {self.message}"


@dataclass
class ValidationResult:
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: ValidationResult) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def error(
        self,
        code: str,
        path: str,
        message: str,
        *,
        file: str | None = None,
    ) -> None:
        self.errors.append(
            ValidationError(code=code, path=path, message=message, file=file)
        )

    def warn(
        self,
        code: str,
        path: str,
        message: str,
        *,
        file: str | None = None,
    ) -> None:
        self.warnings.append(
            ValidationError(code=code, path=path, message=message, file=file)
        )
