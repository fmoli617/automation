from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Iterable, Mapping, Optional, Sequence

import pandas as pd
import pyodbc


@lru_cache(maxsize=1)
def get_sql_odbc_driver() -> str:
    """Retorna o driver ODBC mais atualizado disponível para SQL Server."""
    drivers = pyodbc.drivers()
    pattern = re.compile(r"^ODBC Driver (\d+) for SQL Server$")

    found: list[tuple[int, str]] = []
    for d in drivers:
        m = pattern.match(d)
        if m:
            found.append((int(m.group(1)), d))

    if not found:
        raise RuntimeError("Nenhum driver ODBC para SQL Server encontrado (ODBC Driver N for SQL Server).")

    found.sort(key=lambda x: x[0])
    return found[-1][1]


def _normalize_params(params: Any) -> Optional[tuple[Any, ...]]:
    """Normaliza params para o formato esperado pelo pyodbc."""
    if params is None:
        return None
    if isinstance(params, tuple):
        return params
    if isinstance(params, Sequence) and not isinstance(params, (str, bytes, bytearray)):
        return tuple(params)
    return (params,)


def _freeze_kwargs(kwargs: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Cria chave hashable para cache (assume valores hashable)."""
    return tuple(sorted(kwargs.items(), key=lambda x: x[0]))


@dataclass(slots=True)
class SqlServerConfig:
    server: str
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    trusted: bool = False
    timeout_seconds: int = 30


class SqlServerPlugin:
    """Plugin SQL Server para bot 1x: use com 'with' para abrir e fechar.

    Exemplo:
        cfg = SqlServerConfig(server=..., database=..., username=..., password=...)
        with SqlServerPlugin(cfg) as db:
            df = db.read("SELECT 1 AS x")
            db.execute("UPDATE ... WHERE id = ?", (123,))
    """

    def __init__(self, config: SqlServerConfig) -> None:
        self._config = config
        self._connection: Optional[pyodbc.Connection] = None
        self._read_cache: dict[tuple[str, tuple[tuple[str, Any], ...], tuple[Any, ...]], pd.DataFrame] = {}

    # --- lifecycle ---
    def __enter__(self) -> "SqlServerPlugin":
        self._connection = self._connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._connection is None:
            return

        try:
            # Se houve erro, rollback; senão commit.
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            try:
                self._connection.close()
            finally:
                self._connection = None

    def _connect(self) -> pyodbc.Connection:
        driver = "{" + get_sql_odbc_driver() + "}"

        if self._config.trusted:
            conn_str = (
                f"Driver={driver};"
                f"Server={self._config.server};"
                f"Database={self._config.database};"
                "Trusted_Connection=yes;"
            )
        else:
            if not self._config.username or self._config.password is None:
                raise ValueError("username/password são obrigatórios quando trusted=False.")

            conn_str = (
                f"Driver={driver};"
                f"Server={self._config.server};"
                f"Database={self._config.database};"
                f"UID={self._config.username};"
                f"PWD={self._config.password};"
            )

        return pyodbc.connect(conn_str, autocommit=False, timeout=self._config.timeout_seconds)

    def _con(self) -> pyodbc.Connection:
        if self._connection is None:
            raise RuntimeError("Conexão não inicializada. Use: with SqlServerPlugin(cfg) as db: ...")
        return self._connection

    # --- reads ---
    def read(self, query: str, params: Any = None, **pd_kwargs: Any) -> pd.DataFrame:
        norm = _normalize_params(params)
        con = self._con()
        if norm is None:
            return pd.read_sql(query, con, **pd_kwargs)
        return pd.read_sql(query, con, params=norm, **pd_kwargs)

    def cached_read(self, query: str, params: Any = None, **pd_kwargs: Any) -> pd.DataFrame:
        norm = _normalize_params(params) or ()
        key = (query, _freeze_kwargs(pd_kwargs), norm)
        if key in self._read_cache:
            return self._read_cache[key].copy(deep=False)

        df = self.read(query, params=params, **pd_kwargs)
        self._read_cache[key] = df
        return df.copy(deep=False)

    def get_date(self) -> datetime:
        cur = self._con().cursor()
        try:
            return cur.execute("SELECT GETDATE()").fetchval()
        finally:
            cur.close()

    # --- writes ---
    def execute(self, sql: str, params: Any = None) -> int:
        norm = _normalize_params(params)
        cur = self._con().cursor()
        try:
            if norm is None:
                cur.execute(sql)
            else:
                cur.execute(sql, norm)
            return cur.rowcount
        finally:
            cur.close()

    def execute_many(self, sql: str, values: Iterable[Sequence[Any]], fast: bool = False) -> int:
        con = self._con()
        cur = con.cursor()
        old_fast = getattr(cur, "fast_executemany", False)
        try:
            cur.fast_executemany = fast
            batch = list(values)  # bot 1x normalmente suporta materializar
            cur.executemany(sql, batch)
            # rowcount pode variar por driver; fallback para tamanho do batch
            return cur.rowcount if cur.rowcount != -1 else len(batch)
        finally:
            cur.fast_executemany = old_fast
            cur.close()
