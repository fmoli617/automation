from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Iterable, Iterator, Mapping, Optional, Sequence

import pandas as pd
import pyodbc


# ---------------- Driver discovery (MySQL) ----------------
@lru_cache(maxsize=1)
def get_mysql_odbc_driver(preferred: Optional[str] = None) -> str:
    """Retorna o melhor driver MySQL ODBC instalado.

    Regra:
      - se preferred for informado, exige match exato
      - caso contrário, prefere Unicode e maior versão (8.x > 5.x)
    """
    drivers = list(pyodbc.drivers())

    if preferred:
        if preferred not in drivers:
            raise RuntimeError(f"Driver preferido não encontrado: '{preferred}'. Instalados: {drivers}")
        return preferred

    # Exemplos:
    # "MySQL ODBC 8.0 Unicode Driver"
    # "MySQL ODBC 8.0 ANSI Driver"
    uni = re.compile(r"^MySQL ODBC (\d+)\.(\d+) Unicode Driver$")
    ansi = re.compile(r"^MySQL ODBC (\d+)\.(\d+) ANSI Driver$")

    scored: list[tuple[tuple[int, int, int], str]] = []
    for d in drivers:
        m = uni.match(d)
        if m:
            major, minor = int(m.group(1)), int(m.group(2))
            scored.append(((major, minor, 2), d))  # 2 = unicode preferido
            continue

        m = ansi.match(d)
        if m:
            major, minor = int(m.group(1)), int(m.group(2))
            scored.append(((major, minor, 1), d))  # 1 = ansi fallback

    if not scored:
        raise RuntimeError("Nenhum driver MySQL ODBC encontrado (MySQL ODBC x.y Unicode/ANSI Driver).")

    scored.sort(key=lambda x: x[0])
    return scored[-1][1]


# ---------------- Helpers ----------------
def _normalize_params(params: Any) -> Optional[tuple[Any, ...]]:
    if params is None:
        return None
    if isinstance(params, tuple):
        return params
    if isinstance(params, Sequence) and not isinstance(params, (str, bytes, bytearray)):
        return tuple(params)
    return (params,)


def _freeze_kwargs(kwargs: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(kwargs.items(), key=lambda x: x[0]))


# ---------------- Dynamic rows ----------------
@dataclass(slots=True)
class ObjetoDinamico:
    __dict__: dict[str, Any]

    def __init__(self, row: pyodbc.Row, fields: list[str]) -> None:
        for field in fields:
            setattr(self, field, getattr(row, field))


class CursorByName(Iterator[ObjetoDinamico]):
    def __init__(self, cursor: pyodbc.Cursor) -> None:
        self._cursor = cursor
        self._fields = [desc[0] for desc in (cursor.description or [])]

    def __iter__(self) -> CursorByName:
        return self

    def __next__(self) -> ObjetoDinamico:
        row = self._cursor.fetchone()
        if row is None:
            raise StopIteration
        return ObjetoDinamico(row, self._fields)

# ---------------- Config ----------------
@dataclass(slots=True)
class MySqlOdbcConfig:
    host: str
    database: str
    username: str
    password: str
    port: int = 3306
    timeout_seconds: int = 30

    # driver
    preferred_driver: Optional[str] = None  # ex.: "MySQL ODBC 8.0 Unicode Driver"

    # extras de conexão (quando precisar ajustar ambiente)
    charset: str = "utf8mb4"
    ssl_disabled: bool = False  # se seu ambiente não usa SSL e o driver estiver exigindo


# ---------------- Plugin ----------------
class MySqlOdbcPlugin:
    """Plugin MySQL via ODBC (pyodbc) para bot 1x.

    Uso:
        cfg = MySqlOdbcConfig(host=..., database=..., username=..., password=...)
        with MySqlOdbcPlugin(cfg) as db:
            df = db.read_df("SELECT 1 AS x")
            rows = db.read("SELECT id, status FROM tb LIMIT 1")
            db.execute("UPDATE tb SET status=? WHERE id=?", (1, 10))
    """

    def __init__(self, config: MySqlOdbcConfig) -> None:
        self._cfg = config
        self._con: Optional[pyodbc.Connection] = None
        self._df_cache: dict[tuple[str, tuple[tuple[str, Any], ...], tuple[Any, ...]], pd.DataFrame] = {}

    # ---- lifecycle ----
    def __enter__(self) -> "MySqlOdbcPlugin":
        self._con = self._connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._con is None:
            return

        try:
            if exc_type is None:
                self._con.commit()
            else:
                self._con.rollback()
        finally:
            try:
                self._con.close()
            finally:
                self._con = None

    def _connection(self) -> pyodbc.Connection:
        if self._con is None:
            raise RuntimeError("Conexão não inicializada. Use: with MySqlOdbcPlugin(cfg) as db: ...")
        return self._con

    def _connect(self) -> pyodbc.Connection:
        driver_name = get_mysql_odbc_driver(self._cfg.preferred_driver)
        driver = "{" + driver_name + "}"

        # OPTION=3: habilita alguns defaults comuns (inclui CLIENT_FOUND_ROWS etc. dependendo do driver)
        # CHARSET: importante pra evitar problemas com acentos/utf8
        conn_str = (
            f"Driver={driver};"
            f"Server={self._cfg.host};"
            f"Port={self._cfg.port};"
            f"Database={self._cfg.database};"
            f"UID={self._cfg.username};"
            f"PWD={self._cfg.password};"
            f"CHARSET={self._cfg.charset};"
            "OPTION=3;"
        )

        # Alguns ambientes quebram por SSL. Se precisar, desabilite (varia com driver/política).
        if self._cfg.ssl_disabled:
            conn_str += "SSL=0;"

        return pyodbc.connect(conn_str, autocommit=False, timeout=self._cfg.timeout_seconds)

    # ---- misc ----
    def get_date(self) -> datetime:
        cur = self._connection().cursor()
        try:
            return cur.execute("SELECT NOW()").fetchval()
        finally:
            cur.close()

    def clear_cache(self) -> None:
        self._df_cache.clear()

    # ---- DataFrame reads ----
    def read_df(self, query: str, params: Any = None, **pd_kwargs: Any) -> pd.DataFrame:
        norm = _normalize_params(params)
        con = self._connection()
        if norm is None:
            return pd.read_sql(query, con, **pd_kwargs)
        return pd.read_sql(query, con, params=norm, **pd_kwargs)

    def cached_read_df(self, query: str, params: Any = None, **pd_kwargs: Any) -> pd.DataFrame:
        norm = _normalize_params(params) or ()
        key = (query, _freeze_kwargs(pd_kwargs), norm)
        if key in self._df_cache:
            return self._df_cache[key].copy(deep=False)

        df = self.read_df(query, params=params, **pd_kwargs)
        self._df_cache[key] = df
        return df.copy(deep=False)

    # ---- Object reads ----
    def read(self, query: str, params: Any = None) -> list[ObjetoDinamico]:
        norm = _normalize_params(params)
        cur = self._connection().cursor()
        try:
            if norm is None:
                cur.execute(query)
            else:
                cur.execute(query, norm)
            return list(CursorByName(cur))
        finally:
            cur.close()

    def exec_proc(self, query: str, params: Any = None) -> list[ObjetoDinamico]:
        """Execução de stored procedure.

        Em MySQL, geralmente: CALL schema.proc(?, ?)
        """
        norm = _normalize_params(params)
        con = self._connection()
        old_autocommit = con.autocommit
        con.autocommit = True

        cur = con.cursor()
        try:
            if norm is None:
                cur.execute(query)
            else:
                cur.execute(query, norm)
            return list(CursorByName(cur))
        finally:
            cur.close()
            con.autocommit = old_autocommit

    # ---- writes ----
    def execute(self, sql: str, params: Any = None) -> int:
        norm = _normalize_params(params)
        cur = self._connection().cursor()
        try:
            if norm is None:
                cur.execute(sql)
            else:
                cur.execute(sql, norm)
            return cur.rowcount
        finally:
            cur.close()

    def execute_many(self, sql: str, values: Iterable[Sequence[Any]]) -> int:
        cur = self._connection().cursor()
        try:
            batch = list(values)
            cur.executemany(sql, batch)
            return cur.rowcount if cur.rowcount != -1 else len(batch)
        finally:
            cur.close()
