"""Conversão de uma linha do CSV para o modelo de reserva."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from ..exceptions import InputFileError
from ..models import RawRow, Reservation

VALID_STATUSES = frozenset({"CONFIRMED", "CANCELLED", "NO_SHOW"})


class RowParser:
    """Converte a linha crua em Reservation.

    O arquivo de entrada é consistente; falhas de formato são erro de arquivo, não dado a
    ser descartado.
    """

    def parse(self, raw: RawRow) -> Reservation:
        values = raw.values
        try:
            reservation = Reservation(
                reservation_id=(values.get("reservation_id") or "").strip(),
                traveler_name=(values.get("traveler_name") or "").strip(),
                company_id=(values.get("company_id") or "").strip(),
                hotel_id=(values.get("hotel_id") or "").strip(),
                hotel_name=(values.get("hotel_name") or "").strip(),
                city=(values.get("city") or "").strip(),
                country=(values.get("country") or "").strip(),
                checkin=date.fromisoformat((values.get("checkin_date") or "").strip()),
                checkout=date.fromisoformat((values.get("checkout_date") or "").strip()),
                rooms=int((values.get("rooms") or "").strip()),
                status=(values.get("status") or "").strip(),
                currency=(values.get("currency") or "").strip(),
                amount=Decimal((values.get("amount") or "").strip()),
                payment_method=(values.get("payment_method") or "").strip(),
                line_number=raw.line_number,
            )
        except (ValueError, InvalidOperation) as err:
            raise InputFileError(f"linha {raw.line_number} inválida: {err}") from err

        if reservation.status not in VALID_STATUSES:
            raise InputFileError(
                f"linha {raw.line_number} inválida: status desconhecido: {reservation.status!r}"
            )
        if reservation.checkout < reservation.checkin:
            raise InputFileError(
                f"linha {raw.line_number} inválida: check-out ({reservation.checkout}) "
                f"anterior ao check-in ({reservation.checkin})"
            )
        if reservation.rooms < 1:
            raise InputFileError(
                f"linha {raw.line_number} inválida: rooms deve ser >= 1, veio {reservation.rooms}"
            )
        return reservation
