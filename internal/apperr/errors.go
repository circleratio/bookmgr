// Package apperr defines application-level error types shared between the
// service layer and the handler layers, so handlers can translate them into
// HTTP responses without depending on repository/service internals.
package apperr

import "errors"

var (
	ErrValidation = errors.New("validation error")
	ErrNotFound   = errors.New("not found")
	ErrConflict   = errors.New("conflict")
)

// ValidationError wraps ErrValidation with a human-readable message.
type ValidationError struct {
	Message string
}

func (e *ValidationError) Error() string { return e.Message }
func (e *ValidationError) Unwrap() error { return ErrValidation }

func NewValidationError(message string) error {
	return &ValidationError{Message: message}
}

// ConflictError wraps ErrConflict with a human-readable message.
type ConflictError struct {
	Message string
}

func (e *ConflictError) Error() string { return e.Message }
func (e *ConflictError) Unwrap() error { return ErrConflict }

func NewConflictError(message string) error {
	return &ConflictError{Message: message}
}
