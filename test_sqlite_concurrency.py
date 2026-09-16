from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


DB_PATH = Path("weekly_test_concurrency.db")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DB_PATH,
        timeout=5,
        check_same_thread=False,
    )

    connection.execute(
        "PRAGMA journal_mode=WAL;"
    )

    connection.execute(
        "PRAGMA busy_timeout=5000;"
    )

    connection.execute(
        "PRAGMA foreign_keys=ON;"
    )

    return connection


def setup_database() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    wal_file = Path(
        str(DB_PATH) + "-wal"
    )

    shm_file = Path(
        str(DB_PATH) + "-shm"
    )

    if wal_file.exists():
        wal_file.unlink()

    if shm_file.exists():
        shm_file.unlink()

    connection = connect()

    connection.execute(
        """
        CREATE TABLE parent (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        """
    )

    connection.execute(
        """
        CREATE TABLE child (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER NOT NULL,
            value TEXT NOT NULL,
            FOREIGN KEY(parent_id)
                REFERENCES parent(id)
        );
        """
    )

    connection.execute(
        """
        INSERT INTO parent (
            id,
            name
        )
        VALUES (
            1,
            'weekly_v1'
        );
        """
    )

    connection.commit()
    connection.close()


def test_pragmas() -> None:
    connection = connect()

    journal_mode = connection.execute(
        "PRAGMA journal_mode;"
    ).fetchone()[0]

    busy_timeout = connection.execute(
        "PRAGMA busy_timeout;"
    ).fetchone()[0]

    foreign_keys = connection.execute(
        "PRAGMA foreign_keys;"
    ).fetchone()[0]

    connection.close()

    if str(journal_mode).lower() != "wal":
        raise AssertionError(
            f"journal_mode expected WAL, "
            f"got {journal_mode!r}"
        )

    if int(busy_timeout) != 5000:
        raise AssertionError(
            f"busy_timeout expected 5000, "
            f"got {busy_timeout}"
        )

    if int(foreign_keys) != 1:
        raise AssertionError(
            f"foreign_keys expected ON, "
            f"got {foreign_keys}"
        )


def test_foreign_key_enforced() -> None:
    connection = connect()

    try:
        connection.execute(
            """
            INSERT INTO child (
                parent_id,
                value
            )
            VALUES (
                999,
                'should_fail'
            );
            """
        )

        connection.commit()

    except sqlite3.IntegrityError:
        connection.rollback()
        connection.close()
        return

    connection.close()

    raise AssertionError(
        "Foreign key violation was not blocked."
    )


def writer_task(
    results: dict,
) -> None:
    connection = connect()

    try:
        connection.execute(
            "BEGIN IMMEDIATE;"
        )

        connection.execute(
            """
            INSERT INTO child (
                parent_id,
                value
            )
            VALUES (
                1,
                'writer_uncommitted'
            );
            """
        )

        results[
            "writer_inserted"
        ] = True

        # Keep write transaction open briefly
        # while reader accesses DB.
        time.sleep(2)

        connection.commit()

        results[
            "writer_committed"
        ] = True

    except Exception as exc:
        results[
            "writer_error"
        ] = repr(exc)

        connection.rollback()

    finally:
        connection.close()


def reader_task(
    results: dict,
) -> None:
    # Let writer enter transaction first.
    time.sleep(0.5)

    connection = connect()

    try:
        start = time.perf_counter()

        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM parent;
            """
        ).fetchone()

        elapsed = (
            time.perf_counter()
            - start
        )

        results[
            "reader_parent_count"
        ] = row[0]

        results[
            "reader_elapsed_seconds"
        ] = elapsed

        # Reader should see committed data only.
        child_count_before_commit = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM child;
                """
            ).fetchone()[0]
        )

        results[
            "reader_child_count_before_commit"
        ] = child_count_before_commit

    except Exception as exc:
        results[
            "reader_error"
        ] = repr(exc)

    finally:
        connection.close()


def second_writer_task(
    results: dict,
) -> None:
    # Start while writer #1 holds lock.
    time.sleep(0.5)

    connection = connect()

    try:
        start = time.perf_counter()

        connection.execute(
            """
            INSERT INTO child (
                parent_id,
                value
            )
            VALUES (
                1,
                'second_writer'
            );
            """
        )

        connection.commit()

        elapsed = (
            time.perf_counter()
            - start
        )

        results[
            "second_writer_success"
        ] = True

        results[
            "second_writer_elapsed_seconds"
        ] = elapsed

    except Exception as exc:
        results[
            "second_writer_error"
        ] = repr(exc)

        connection.rollback()

    finally:
        connection.close()


def test_concurrent_access() -> dict:
    results: dict = {}

    writer = threading.Thread(
        target=writer_task,
        args=(results,),
    )

    reader = threading.Thread(
        target=reader_task,
        args=(results,),
    )

    second_writer = threading.Thread(
        target=second_writer_task,
        args=(results,),
    )

    writer.start()
    reader.start()
    second_writer.start()

    writer.join()
    reader.join()
    second_writer.join()

    if "writer_error" in results:
        raise AssertionError(
            results["writer_error"]
        )

    if "reader_error" in results:
        raise AssertionError(
            results["reader_error"]
        )

    if "second_writer_error" in results:
        raise AssertionError(
            results["second_writer_error"]
        )

    if not results.get(
        "writer_committed"
    ):
        raise AssertionError(
            "Primary writer did not commit."
        )

    if (
        results.get(
            "reader_parent_count"
        )
        != 1
    ):
        raise AssertionError(
            "Reader could not read committed "
            "parent data during writer transaction."
        )

    if (
        results.get(
            "reader_child_count_before_commit"
        )
        != 0
    ):
        raise AssertionError(
            "Reader saw uncommitted writer data."
        )

    if not results.get(
        "second_writer_success"
    ):
        raise AssertionError(
            "Second writer did not succeed "
            "after waiting for lock."
        )

    return results


def test_final_rows() -> int:
    connection = connect()

    count = connection.execute(
        """
        SELECT COUNT(*)
        FROM child;
        """
    ).fetchone()[0]

    connection.close()

    if count != 2:
        raise AssertionError(
            f"Expected 2 committed child rows, "
            f"got {count}"
        )

    return count


def run_test(
    name: str,
    function,
):
    try:
        result = function()

        print(
            f"PASS - {name}"
        )

        return True, result

    except Exception as exc:
        print(
            f"FAIL - {name}"
        )

        print(
            f"       {type(exc).__name__}: "
            f"{exc}"
        )

        return False, None


def cleanup() -> None:
    for path in [
        DB_PATH,
        Path(str(DB_PATH) + "-wal"),
        Path(str(DB_PATH) + "-shm"),
    ]:
        try:
            if path.exists():
                path.unlink()
        except PermissionError:
            pass


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 SQLITE CONCURRENCY TEST"
    )
    print("=" * 78)
    print()

    setup_database()

    results = []

    passed, _ = run_test(
        "WAL + busy_timeout + foreign_keys PRAGMAs",
        test_pragmas,
    )

    results.append(passed)

    passed, _ = run_test(
        "Foreign-key enforcement",
        test_foreign_key_enforced,
    )

    results.append(passed)

    passed, concurrency = run_test(
        "Concurrent Worker/Web-style access",
        test_concurrent_access,
    )

    results.append(passed)

    if concurrency is not None:
        print()
        print(
            "reader_elapsed_seconds:",
            round(
                concurrency[
                    "reader_elapsed_seconds"
                ],
                4,
            ),
        )

        print(
            "reader_child_count_before_commit:",
            concurrency[
                "reader_child_count_before_commit"
            ],
        )

        print(
            "second_writer_elapsed_seconds:",
            round(
                concurrency[
                    "second_writer_elapsed_seconds"
                ],
                4,
            ),
        )

        print()

    passed, final_count = run_test(
        "Final committed-row integrity",
        test_final_rows,
    )

    results.append(passed)

    if final_count is not None:
        print(
            "final_child_rows:",
            final_count,
        )

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)

    passed_count = sum(
        1
        for result in results
        if result
    )

    print(
        "tests_passed:",
        passed_count,
        "/",
        len(results),
    )

    if all(results):
        print()
        print(
            "SQLite WAL concurrency: PASS"
        )

        print(
            "busy_timeout behavior: PASS"
        )

        print(
            "foreign_keys enforcement: PASS"
        )

        print(
            "Worker read / writer access model: PASS"
        )

    else:
        print()
        print(
            "SQLite concurrency: CHECK REQUIRED"
        )

    cleanup()


if __name__ == "__main__":
    main()