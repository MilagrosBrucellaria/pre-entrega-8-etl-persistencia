Pre-Entrega 8 - Persistencia e integración de scripts ETL
Descripción
Este proyecto implementa un proceso ETL (Extract, Transform, Load) automatizado utilizando Python, Pandas y SQLite.

El flujo toma como origen el dataset Online Retail en formato Excel, realiza distintas tareas de limpieza y transformación y persiste el resultado en una base de datos SQLite.

El objetivo es disponer de un proceso reproducible que pueda ejecutarse mediante un único script.

Flujo ETL
El proceso desarrollado sigue las siguientes etapas:

1. Extract
El script lee el archivo:

data/online_retail.xlsx

Durante la extracción se valida:

existencia del archivo;
disponibilidad de registros;
presencia de las columnas necesarias para el proceso.
2. Transform
Sobre los datos transaccionales se aplican las siguientes transformaciones:

eliminación de registros duplicados;
eliminación de registros sin CustomerID;
exclusión de facturas canceladas;
exclusión de cantidades menores o iguales a cero;
exclusión de precios menores o iguales a cero;
cálculo del importe total de cada operación;
agregación de información por cliente y país.
Como resultado se genera una tabla analítica que contiene:

cantidad de facturas;
cantidad de productos diferentes;
unidades adquiridas;
importe total;
fecha de primera compra;
fecha de última compra;
fecha y hora de ejecución del ETL.
3. Load
El resultado transformado se almacena en una base de datos SQLite:

database/online_retail_analytics.db

La tabla de destino se denomina:

customer_sales_summary

El esquema se encuentra definido en:

schema.sql

Prevención de duplicados
El proceso utiliza una estrategia de recarga completa o full refresh.

Antes de insertar los datos transformados se eliminan los registros existentes de customer_sales_summary.

Posteriormente se insertan los nuevos resultados.

Además, la tabla posee una clave primaria compuesta por:

customer_id + country

De esta manera, el ETL puede ejecutarse repetidamente sin acumular registros duplicados.

Manejo de errores
El script incorpora controles para los principales errores que pueden ocurrir durante la ejecución:

archivo de origen inexistente;
archivo sin registros;
columnas requeridas faltantes;
errores durante la lectura del Excel;
errores de conexión o carga en SQLite;
inconsistencias entre la cantidad de registros esperados y persistidos.
La carga se realiza dentro de una transacción. Ante un error, se aplica rollback para evitar que la base quede en un estado inconsistente.

Estructura del proyecto
PreEntrega8_ETL/
│
├── data/
│   └── .gitkeep
│
├── database/
│   └── .gitkeep
│
├── etl.py
├── schema.sql
├── requirements.txt
├── .gitignore
└── README.md
