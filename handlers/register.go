package handler

import (
	"database/sql"
	"log"
	"os"

	_ "github.com/mattn/go-sqlite3"
)

func RegisterHandler() {
	db, err := sql.Open("sqlite3", "data/user.db")
	if err != nil {
		log.Fatal("Couldnt open DB: ", err)
	}
	defer db.Close()

	schema, err := os.ReadFile("sql/init.sql")
	query := string(schema)
	_, err = db.Exec(query)
	if err != nil {
		log.Fatal("Coudlnt init db: ", err)
	}
}
