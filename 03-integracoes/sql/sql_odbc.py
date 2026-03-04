from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Any, Iterable, Iterator, Mapping, Optional, Sequence

import pandas as pd
import pyodbc


# ---------------- Dialects ----------------
class DbDialect(str, Enum):
    SQLSERVER = "sqlserver"
    MYSQL = "mysql"


# ---------------- Driver discovery ----------------
@lru_cache(maxsize=32)
def list_odbc_drivers() -> tuple[str, ...]:
    return tuple(pyodbc.drivers())


def _pick_best_driver(drivers: Sequence[str], patterns: list[re.Pattern[str]]) -> Optional[str]:
    """Escolhe o melhor driver baseado em padrões e versão (se houver)."""
    scored: list[tuple[int, str]] = []

    for d in drivers:
        for p in patterns:
            m = p.match(d)
            if not m:
                continue

            # tenta extrair versão numérica se existir no regex
            version = 0
            if m.lastindex:
                for i in range(1, m.lastindex + 1):
                    try:
                        version = max(version, int(m.group(i)))
                    except Exception:
                        pass

            scored.append((version, d))

    if not scored:
        return None

    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[-1][1]


@lru_cache(maxsize=64)
def resolve_driver(dialect: DbDialect, preferred: Optional[str] = None) -> str:
    """Resolve driver ODBC.

    - preferred: se informado, tenta usar exatamente esse nome (desde que instalado)
    - caso contrário, escolhe o "melhor" baseado em padrões por dialeto
    """
    drivers = list_odbc_drivers()

    if preferred:
        if preferred not in drivers:
            raise RuntimeError(f"Driver ODBC preferido não encontrado: '{preferred}'. Instalados: {list(drivers)}")
        return preferred

    if dialect == DbDialect.SQLSERVER:
        # ODBC Driver 17/18 for SQL Server etc
        patterns = [
            re.compile(r"^ODBC Driver (\d+) for SQL Server$"),
        ]
        chosen = _pick_best_driver(drivers, patterns)
        if not chosen:
            raise RuntimeError("Nenhum driver ODBC para SQL Server encontrado (ODBC Driver N for SQL Server).")
        return chosen

    if dialect == DbDialect.MYSQL:
        # Exemplos comuns no Windows:
        # - "MySQL ODBC 8.0 ANSI Driver"
        # - "MySQL ODBC 8.0 Unicode Driver"
        # - "MySQL ODBC 5.3 ANSI Driver"
        # Preferir Unicode e maior versão.
        patterns = [
            re.compile(r"^MySQL ODBC (\d+)\.(\d+) Unicode Driver$"),
            re.compile(r"^MySQL ODBC (\d+)\.(\d+) ANSI Driver$"),
        ]
        chosen = _pick_best_driver(drivers, patterns)
        if not chosen:
            raise RuntimeError("Nenhum driver ODBC para MySQL encontrado (MySQL ODBC x.y ... Driver).")
        return chosen

    raise ValueError(f"Dialect inválido: {dialect}")


# ---------------- Helpers ----------------
def normalize_params(params: Any) -> Optional[tuple[Any, ...]]:
    if params is None:
        return None
    if isinstance(params, tuple):
        return params
    if isinstance(params, Sequence) and not isinstance(params, (str, bytes, bytearray)):
        return tuple(params)
    return (params,)


def freeze_kwargs(kwargs: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
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
class DbConfig:
    dialect: DbDialect
    server: Optional[str] = None          # SQL Server
    database: Optional[str] = None        # SQL Server / MySQL schema
    host: Optional[str] = None            # MySQL
    port: Optional[int] = None            # MySQL
    username: Optional[str] = None
    password: Optional[str] = None
    trusted: bool = False                 # SQL Server
    timeout_seconds: int = 30

    # drivers
    preferred_driver: Optional[str] = None  # nome exato do driver para override


# ---------------- Client ----------------
class DbClient:
    """Cliente unificado (SQL Server + MySQL via ODBC), ideal para bot 1x.

    - with DbClient(cfg) as db: ...
    - read_df / read / exec_proc / execute / execute_many / get_date
    """

    def __init__(self, config: DbConfig) -> None:
        self._cfg = config
        self._con: Optional[pyodbc.Connection] = None
        self._df_cache: dict[tuple[str, tuple[tuple[str, Any], ...], tuple[Any, ...]], pd.DataFrame] = {}

    # ---- lifecycle ----
    def __enter__(self) -> "DbClient":
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
            raise RuntimeError("Conexão não inicializada. Use: with DbClient(cfg) as db: ...")
        return self._con

    def _connect(self) -> pyodbc.Connection:
        driver_name = resolve_driver(self._cfg.dialect, preferred=self._cfg.preferred_driver)
        driver = "{" + driver_name + "}"

        if self._cfg.dialect == DbDialect.SQLSERVER:
            if not self._cfg.server or not self._cfg.database:
                raise ValueError("Para SQL Server, server e database são obrigatórios.")

            if self._cfg.trusted:
                conn_str = (
                    f"Driver={driver};"
                    f"Server={self._cfg.server};"
                    f"Database={self._cfg.database};"
                    "Trusted_Connection=yes;"
                )
            else:
                if not self._cfg.username or self._cfg.password is None:
                    raise ValueError("Para SQL Server (trusted=False), username/password são obrigatórios.")

                conn_str = (
                    f"Driver={driver};"
                    f"Server={self._cfg.server};"
                    f"Database={self._cfg.database};"
                    f"UID={self._cfg.username};"
                    f"PWD={self._cfg.password};"
                )

            return pyodbc.connect(conn_str, autocommit=False, timeout=self._cfg.timeout_seconds)

        if self._cfg.dialect == DbDialect.MYSQL:
            if not self._cfg.host or not self._cfg.database:
                raise ValueError("Para MySQL, host e database são obrigatórios.")
            if not self._cfg.username or self._cfg.password is None:
                raise ValueError("Para MySQL, username/password são obrigatórios.")

            port = self._cfg.port or 3306

            # DSN-less string comum para MySQL ODBC
            conn_str = (
                f"Driver={driver};"
                f"Server={self._cfg.host};"
                f"Port={port};"
                f"Database={self._cfg.database};"
                f"UID={self._cfg.username};"
                f"PWD={self._cfg.password};"
                "OPTION=3;"
            )

            return pyodbc.connect(conn_str, autocommit=False, timeout=self._cfg.timeout_seconds)

        raise ValueError(f"Dialect inválido: {self._cfg.dialect}")

    # ---- SQL differences ----
    def _sql_now(self) -> str:
        return "SELECT GETDATE()" if self._cfg.dialect == DbDialect.SQLSERVER else "SELECT NOW()"

    # ---- API ----
    def get_date(self) -> datetime:
        cur = self._connection().cursor()
        try:
            return cur.execute(self._sql_now()).fetchval()
        finally:
            cur.close()

    def read_df(self, query: str, params: Any = None, **pd_kwargs: Any) -> pd.DataFrame:
        norm = normalize_params(params)
        con = self._connection()
        if norm is None:
            return pd.read_sql(query, con, **pd_kwargs)
        return pd.read_sql(query, con, params=norm, **pd_kwargs)

    def cached_read_df(self, query: str, params: Any = None, **pd_kwargs: Any) -> pd.DataFrame:
        norm = normalize_params(params) or ()
        key = (query, freeze_kwargs(pd_kwargs), norm)
        if key in self._df_cache:
            return self._df_cache[key].copy(deep=False)

        df = self.read_df(query, params=params, **pd_kwargs)
        self._df_cache[key] = df
        return df.copy(deep=False)

    def read(self, query: str, params: Any = None) -> list[ObjetoDinamico]:
        norm = normalize_params(params)
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
        """Procedure genérica: você passa o texto correto para o dialeto.

        SQL Server: EXEC schema.proc ?, ?
        MySQL: CALL schema.proc(?, ?)
        """
        norm = normalize_params(params)
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

    def execute(self, sql: str, params: Any = None) -> int:
        norm = normalize_params(params)
        cur = self._connection().cursor()
        try:
            if norm is None:
                cur.execute(sql)
            else:
                cur.execute(sql, norm)
            return cur.rowcount
        finally:
            cur.close()

    def execute_many(self, sql: str, values: Iterable[Sequence[Any]], fast: bool = False) -> int:
        con = self._connection()
        cur = con.cursor()
        old_fast = getattr(cur, "fast_executemany", False)

        try:
            cur.fast_executemany = fast  # faz diferença real no SQL Server
            batch = list(values)
            cur.executemany(sql, batch)
            return cur.rowcount if cur.rowcount != -1 else len(batch)
        finally:
            cur.fast_executemany = old_fast
            cur.close()
