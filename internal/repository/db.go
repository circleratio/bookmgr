package repository

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

// migrationFiles lists the migration SQL files to apply on startup, in order.
// A simple ordered list is sufficient here since migrations use
// CREATE TABLE/INDEX IF NOT EXISTS and are safe to re-run.
var migrationFiles = []string{
	"0001_create_books.sql",
}

func Open(dbPath string, migrationsDir string) (*sql.DB, error) {
	if dir := filepath.Dir(dbPath); dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, fmt.Errorf("create db directory: %w", err)
		}
	}

	db, err := sql.Open("sqlite", dbPath+"?_pragma=foreign_keys(1)")
	if err != nil {
		return nil, fmt.Errorf("open db: %w", err)
	}
	// sqlite3 does not support concurrent writers; a single connection
	// avoids "database is locked" errors under concurrent requests.
	db.SetMaxOpenConns(1)

	if err := migrate(db, migrationsDir); err != nil {
		db.Close()
		return nil, fmt.Errorf("migrate: %w", err)
	}

	return db, nil
}

func migrate(db *sql.DB, migrationsDir string) error {
	for _, name := range migrationFiles {
		path := filepath.Join(migrationsDir, name)
		content, err := os.ReadFile(path)
		if err != nil {
			return fmt.Errorf("read migration %s: %w", name, err)
		}
		if _, err := db.Exec(string(content)); err != nil {
			return fmt.Errorf("apply migration %s: %w", name, err)
		}
	}
	return nil
}
