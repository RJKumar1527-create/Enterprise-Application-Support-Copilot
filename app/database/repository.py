import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


class DatabaseUnavailableError(RuntimeError):
    """IMS DPT1 database access is disabled or unavailable."""


class QueryNotApprovedError(ValueError):
    """Only pre-approved read-only queries may be executed."""


@dataclass(frozen=True)
class DatabaseSettings:
    enabled: bool = (
        os.getenv(
            "IMS_DB_ENABLED",
            "false",
        ).lower()
        == "true"
    )
    host: str = os.getenv(
        "IMS_DB_HOST",
        "",
    )
    port: int = int(
        os.getenv(
            "IMS_DB_PORT",
            "1521",
        )
    )
    service_name: str = os.getenv(
        "IMS_DB_SERVICE_NAME",
        "",
    )
    username: str = os.getenv(
        "IMS_DB_USERNAME",
        "",
    )
    password: str = os.getenv(
        "IMS_DB_PASSWORD",
        "",
    )


APPROVED_QUERIES = {
    "batch_status": """
        SELECT
            batch_reference,
            batch_status,
            frozen_indicator,
            invoice_count,
            authorized_invoice_count,
            export_status,
            last_updated_date
        FROM ims_ai_batch_status_v
        WHERE batch_reference = :reference
    """,
    "invoice_status": """
        SELECT
            invoice_reference,
            invoice_status,
            invoice_type,
            batch_reference,
            validation_status,
            current_owner,
            last_updated_date
        FROM ims_ai_invoice_status_v
        WHERE invoice_reference = :reference
    """,
    "file_processing_status": """
        SELECT
            file_reference,
            file_type,
            processing_status,
            rejection_reason,
            received_date,
            processed_date
        FROM ims_ai_file_status_v
        WHERE file_reference = :reference
    """,
    "incident_history": """
        SELECT
            incident_reference,
            application_area,
            symptom_summary,
            confirmed_root_cause,
            resolution_summary,
            incident_status,
            created_date,
            resolved_date
        FROM ims_ai_incident_history_v
        WHERE application_area = :application_area
        ORDER BY created_date DESC
        FETCH FIRST 20 ROWS ONLY
    """,
}


class IMSDatabaseRepository:
    """
    Read-only IMS DPT1 repository.

    User questions and LLM output can never supply arbitrary SQL.
    """

    def __init__(self):
        self.settings = DatabaseSettings()

    @contextmanager
    def get_connection(self):
        if not self.settings.enabled:
            raise DatabaseUnavailableError(
                "IMS DPT1 integration is currently disabled."
            )

        try:
            import oracledb
        except ImportError as error:
            raise DatabaseUnavailableError(
                "The oracledb package is not installed."
            ) from error

        required_values = {
            "host": self.settings.host,
            "service_name": (
                self.settings.service_name
            ),
            "username": self.settings.username,
            "password": self.settings.password,
        }

        missing = [
            name
            for name, value
            in required_values.items()
            if not value
        ]

        if missing:
            raise DatabaseUnavailableError(
                "Missing IMS database settings: "
                + ", ".join(missing)
            )

        dsn = oracledb.makedsn(
            self.settings.host,
            self.settings.port,
            service_name=(
                self.settings.service_name
            ),
        )

        connection = None

        try:
            connection = oracledb.connect(
                user=self.settings.username,
                password=self.settings.password,
                dsn=dsn,
            )

            yield connection

        finally:
            if connection is not None:
                connection.close()

    def execute_approved_query(
        self,
        query_name: str,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if query_name not in APPROVED_QUERIES:
            raise QueryNotApprovedError(
                f"Query is not approved: {query_name}"
            )

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    APPROVED_QUERIES[query_name],
                    parameters,
                )

                columns = [
                    description[0].lower()
                    for description
                    in cursor.description
                ]

                return [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]

    def get_operational_context(
        self,
        application_area: str,
        reference: str,
    ) -> dict[str, Any]:
        if not reference:
            return {
                "available": False,
                "source": "IMS DPT1",
                "reason": (
                    "No operational reference "
                    "was supplied."
                ),
                "records": [],
            }

        query_mapping = {
            "batch_processing": "batch_status",
            "invoice_lifecycle": "invoice_status",
            "d2021": "file_processing_status",
        }

        query_name = query_mapping.get(
            application_area
        )

        if query_name is None:
            return {
                "available": False,
                "source": "IMS DPT1",
                "reason": (
                    "No approved operational query "
                    "exists for the selected area."
                ),
                "records": [],
            }

        try:
            records = self.execute_approved_query(
                query_name=query_name,
                parameters={
                    "reference": reference
                },
            )

            return {
                "available": True,
                "source": "IMS DPT1",
                "access_mode": "READ_ONLY",
                "query_name": query_name,
                "records": records,
            }

        except DatabaseUnavailableError as error:
            return {
                "available": False,
                "source": "IMS DPT1",
                "reason": str(error),
                "records": [],
            }


ims_database_repository = IMSDatabaseRepository()
