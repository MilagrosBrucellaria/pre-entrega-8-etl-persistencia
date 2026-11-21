from pathlib import Path
import logging
import sqlite3
import sys

import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

EXCEL_PATH = BASE_DIR / "data" / "online_retail.xlsx"
DATABASE_PATH = BASE_DIR / "database" / "online_retail_analytics.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

TABLE_NAME = "customer_sales_summary"

EXPECTED_COLUMNS = {
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
}


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)



# ============================================================
# EXTRACT
# ============================================================

def extract_data(excel_path):
    """Extrae los datos desde el archivo Excel de origen."""

    logger.info("Iniciando extracción de datos.")

    if not excel_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {excel_path}"
        )

    try:
        df = pd.read_excel(
            excel_path,
            engine="openpyxl"
        )

    except Exception as error:
        raise RuntimeError(
            f"Error al leer el archivo Excel: {error}"
        ) from error

    if df.empty:
        raise ValueError(
            "El archivo de origen no contiene registros."
        )

    missing_columns = EXPECTED_COLUMNS.difference(df.columns)

    if missing_columns:
        raise ValueError(
            f"Faltan columnas requeridas: {sorted(missing_columns)}"
        )

    logger.info(
        "Extracción finalizada: %s registros.",
        len(df)
    )

    return df



# ============================================================
# TRANSFORM
# ============================================================

def transform_data(df):
    """Limpia y transforma los datos transaccionales."""

    logger.info("Iniciando transformación de datos.")

    df_clean = df.copy()

    # Eliminar registros duplicados
    df_clean = df_clean.drop_duplicates()

    # Eliminar registros sin identificador de cliente
    df_clean = df_clean.dropna(
        subset=["CustomerID"]
    )

    # Excluir facturas canceladas
    df_clean = df_clean[
        ~df_clean["InvoiceNo"]
        .astype(str)
        .str.startswith("C", na=False)
    ].copy()

    # Conservar solamente ventas con cantidad y precio positivos
    df_clean = df_clean[
        (df_clean["Quantity"] > 0)
        & (df_clean["UnitPrice"] > 0)
    ].copy()

    if df_clean.empty:
        raise ValueError(
            "No quedaron registros válidos luego de la limpieza."
        )

    # Calcular importe de cada operación
    df_clean["TotalAmount"] = (
        df_clean["Quantity"]
        * df_clean["UnitPrice"]
    )

    # Crear tabla analítica por cliente y país
    df_summary = (
        df_clean
        .groupby(
            ["CustomerID", "Country"],
            as_index=False
        )
        .agg(
            invoice_count=("InvoiceNo", "nunique"),
            product_count=("StockCode", "nunique"),
            total_units=("Quantity", "sum"),
            total_amount=("TotalAmount", "sum"),
            first_purchase_date=("InvoiceDate", "min"),
            last_purchase_date=("InvoiceDate", "max")
        )
    )

    # Normalizar nombres
    df_summary = df_summary.rename(
        columns={
            "CustomerID": "customer_id",
            "Country": "country"
        }
    )

    # Normalizar tipos
    df_summary["customer_id"] = (
        df_summary["customer_id"]
        .astype(int)
        .astype(str)
    )

    df_summary["invoice_count"] = (
        df_summary["invoice_count"].astype(int)
    )

    df_summary["product_count"] = (
        df_summary["product_count"].astype(int)
    )

    df_summary["total_units"] = (
        df_summary["total_units"].astype(int)
    )

    df_summary["total_amount"] = (
        df_summary["total_amount"].round(2)
    )

    # Preparar las fechas para SQLite
    df_summary["first_purchase_date"] = (
        pd.to_datetime(df_summary["first_purchase_date"])
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    df_summary["last_purchase_date"] = (
        pd.to_datetime(df_summary["last_purchase_date"])
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    # Registrar momento de ejecución del ETL
    df_summary["etl_loaded_at"] = (
        pd.Timestamp.now()
        .floor("s")
        .strftime("%Y-%m-%d %H:%M:%S")
    )

    logger.info(
        "Transformación finalizada: %s registros analíticos.",
        len(df_summary)
    )

    return df_summary



# ============================================================
# DATABASE SCHEMA
# ============================================================

def create_schema(connection, schema_path):
    """Crea la tabla de destino a partir del archivo schema.sql."""

    logger.info("Verificando esquema de la base de datos.")

    if not schema_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo SQL: {schema_path}"
        )

    schema_sql = schema_path.read_text(
        encoding="utf-8"
    )

    connection.executescript(schema_sql)

    logger.info("Esquema verificado correctamente.")



# ============================================================
# LOAD
# ============================================================

def load_data(df, database_path, schema_path):
    """Carga los datos transformados en SQLite."""

    logger.info("Iniciando carga en SQLite.")

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = None

    try:
        connection = sqlite3.connect(database_path)

        create_schema(
            connection,
            schema_path
        )

        connection.execute(
            "BEGIN TRANSACTION"
        )

        # Full refresh para evitar duplicados
        connection.execute(
            f"DELETE FROM {TABLE_NAME}"
        )

        df.to_sql(
            name=TABLE_NAME,
            con=connection,
            if_exists="append",
            index=False
        )

        connection.commit()

        logger.info(
            "Carga finalizada: %s registros.",
            len(df)
        )

    except Exception as error:

        if connection is not None:
            connection.rollback()

        raise RuntimeError(
            f"Error durante la carga: {error}"
        ) from error

    finally:

        if connection is not None:
            connection.close()



# ============================================================
# VALIDATE
# ============================================================

def validate_load(database_path, expected_rows):
    """Valida la cantidad de registros persistidos."""

    try:
        with sqlite3.connect(database_path) as connection:

            result = connection.execute(
                f"SELECT COUNT(*) FROM {TABLE_NAME}"
            ).fetchone()

    except sqlite3.Error as error:
        raise RuntimeError(
            f"Error al validar la carga: {error}"
        ) from error

    loaded_rows = result[0]

    if loaded_rows != expected_rows:
        raise ValueError(
            "La cantidad de registros persistidos no coincide "
            "con la cantidad esperada."
        )

    logger.info(
        "Validación exitosa: %s registros persistidos.",
        loaded_rows
    )

    return loaded_rows



# ============================================================
# ETL PIPELINE
# ============================================================

def run_etl():
    """Ejecuta el proceso ETL completo."""

    logger.info("=" * 50)
    logger.info("INICIO DEL PROCESO ETL")
    logger.info("=" * 50)

    # EXTRACT
    df = extract_data(EXCEL_PATH)

    # TRANSFORM
    df_summary = transform_data(df)

    # LOAD
    load_data(
        df_summary,
        DATABASE_PATH,
        SCHEMA_PATH
    )

    # VALIDATE
    loaded_rows = validate_load(
        DATABASE_PATH,
        len(df_summary)
    )

    logger.info("=" * 50)
    logger.info(
        "ETL COMPLETADO CORRECTAMENTE: %s registros.",
        loaded_rows
    )
    logger.info("=" * 50)


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":

    try:
        run_etl()

    except (
        FileNotFoundError,
        ValueError,
        RuntimeError
    ) as error:

        logger.error(
            "El proceso ETL falló: %s",
            error
        )

        sys.exit(1)

    except Exception as error:

        logger.exception(
            "Ocurrió un error inesperado: %s",
            error
        )

        sys.exit(1)
