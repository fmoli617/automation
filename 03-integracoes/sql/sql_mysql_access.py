from __future__ import annotations

from dataclasses import dataclass

from sql_mysql import MySqlOdbcConfig, MySqlOdbcPlugin, ObjetoDinamico


@dataclass(frozen=True, slots=True)
class DbConfig:
    host: str
    database: str
    username: str
    password: str
    port: int = 3306


class FilaRepository:
    """Repositório de operações relacionadas à fila."""

    STATUS_REPROCESSAR = 1
    STATUS_FALHA = 3
    STATUS_SUCESSO = 0
    MAX_TENTATIVAS = 3

    def __init__(self, config: DbConfig) -> None:
        self._db_config = MySqlOdbcConfig(
            host=config.host,
            port=config.port,
            database=config.database,
            username=config.username,
            password=config.password,
        )

    def executar_procedure_y(self) -> object:
        """Executa a procedure e retorna o primeiro item ou 0."""
        query = "CALL banco_x.procedure_y()"

        with MySqlOdbcPlugin(self._db_config) as db:
            output: list[ObjetoDinamico] = db.exec_proc(query)

        return next(iter(output), 0)

    def update_item_tentativa(self, item_id: int, item_qtd_tentativas: int) -> None:
        """Atualiza status conforme tentativas."""
        novo_status = (
            self.STATUS_FALHA
            if item_qtd_tentativas >= self.MAX_TENTATIVAS
            else self.STATUS_REPROCESSAR
        )

        query = """
            UPDATE tb_x
            SET
                status = ?,
                quantidade_tentativas = ?
            WHERE ITEM_ID = ?
        """

        with MySqlOdbcPlugin(self._db_config) as db:
            db.execute(query, (novo_status, item_qtd_tentativas, item_id))

    def update_sucesso(self, item_id: int, user: str) -> None:
        """Atualiza status de sucesso."""
        query = """
            UPDATE tb_x
            SET
                status = ?,
                `user` = ?
            WHERE ITEM_ID = ?
        """

        with MySqlOdbcPlugin(self._db_config) as db:
            db.execute(query, (self.STATUS_SUCESSO, user, item_id))
