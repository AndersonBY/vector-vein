import peewee
from peewee_migrate import Router
from playhouse.sqlite_ext import SqliteExtDatabase


def custom_run_migrations(db_path):
    database = SqliteExtDatabase(db_path)
    router = Router(database, migrate_dir="./migrations")

    print("Current migration status:")
    router.logger.info("Applied migrations: %s", router.done)
    router.logger.info("Migrations to apply: %s", router.diff)

    for migration in router.diff:
        try:
            migrator = router.migrator
            print(f"Applying migration: {migration}")
            router.run_one(migration, migrator, fake=False)
            print(f"Successfully applied migration: {migration}")
        except peewee.OperationalError as e:
            error_message = str(e).lower()
            if "already exists" in error_message or "duplicate column name" in error_message:
                print(f"Skipping {migration}, seems already applied: {e}")
                try:
                    router.run_one(migration, migrator, fake=True, force=True)
                    print(f"Faked migration: {migration}")
                except Exception as fake_error:
                    print(f"Error while faking migration {migration}: {fake_error}")
            else:
                print(f"Error applying migration {migration}: {e}")
                raise

    print("\nFinal migration status:")
    router.logger.info("Applied migrations: %s", router.done)
    router.logger.info("Migrations to apply: %s", router.diff)

    # 验证迁移历史
    with database.atomic():
        cursor = database.execute_sql("SELECT name FROM migratehistory ORDER BY id")
        applied_migrations = [row[0] for row in cursor.fetchall()]
        print("\nMigrations in database:")
        for migration in applied_migrations:
            print(f" - {migration}")


if __name__ == "__main__":
    db_path = input("Database file (my_database.db) path>")
    custom_run_migrations(db_path)
