from __future__ import annotations

from dataclasses import dataclass

from sql_server import SqlServerPlugin


@dataclass(slots=True)
class ItemFila:
    id: int
    qtd_tentativas: int


class FilaRepository:
    """Repositório de operações da fila."""

    STATUS_REPROCESSAR = 1
    STATUS_FALHA = 3
    STATUS_SUCESSO = 0
    MAX_TENTATIVAS = 3

    def __init__(self, db: SqlServerPlugin) -> None:
        self._db = db

    def executar_procedure_y(self) -> object:
        """Executa procedure e retorna primeiro item ou 0."""
        query = "EXEC banco_x.dbo.procedure_y"

        df = self._db.read(query)

        if df.empty:
            return 0

        return df.iloc[0]

    def update_item_tentativa(self, item: ItemFila) -> None:
        """Atualiza status conforme tentativas."""

        novo_status = (
            self.STATUS_FALHA
            if item.qtd_tentativas >= self.MAX_TENTATIVAS
            else self.STATUS_REPROCESSAR
        )

        query = """
            UPDATE tb_x
            SET
                status = ?,
                quantidade_tentativas = ?
            WHERE ITEM_ID = ?
        """

        self._db.execute(query, (novo_status, item.qtd_tentativas, item.id))

    def update_sucesso(self, item_id: int, user: str) -> None:
        """Atualiza item como sucesso."""

        query = """
            UPDATE tb_x
            SET
                status = ?,
                usuario_robo = ?
            WHERE ITEM_ID = ?
        """

        self._db.execute(query, (self.STATUS_SUCESSO, user, item_id))