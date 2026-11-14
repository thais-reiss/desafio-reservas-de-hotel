"""Testes adicionais, derivados por particionamento de equivalência e análise de valor limite.

Organização:
- Reutiliza ``run_cli`` de ``helpers`` nos cenários de sucesso (código de saída 0).
- Usa runners próprios (``_run_cli_process``/``run_failing_cli``) nos cenários de erro,
  pois o ``run_cli`` fornecido afirma ``returncode == 0``.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

from helpers import BASE, COLUMNS, PROJECT_ROOT, SRC_DIR, run_cli

DEFAULT_RATES = "currency,rate_to_brl\nBRL,1.000000\nUSD,5.420000\nEUR,5.880000\n"


def _write_reservations_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {key: value for key, value in {**BASE, **row}.items() if key in columns} for row in rows
        )


def _run_cli_process(cli_args: list[str]) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *cli_args],
        cwd=str(PROJECT_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


def run_failing_cli(
    tmp_path: Path,
    rows: list[dict[str, str]] | None = None,
    *,
    top: str = "5",
    input_path: Path | None = None,
    rates_path: Path | None = None,
    columns: list[str] = COLUMNS,
) -> subprocess.CompletedProcess:
    """Roda o CLI sem afirmar sucesso, devolvendo o processo para inspeção."""
    if input_path is None:
        input_path = tmp_path / "reservas.csv"
        _write_reservations_csv(input_path, rows or [], columns)
    if rates_path is None:
        rates_path = tmp_path / "rates.csv"
        rates_path.write_text(DEFAULT_RATES, encoding="utf-8")
    output_path = tmp_path / "report.json"
    return _run_cli_process(
        ["--input", str(input_path), "--rates", str(rates_path), "--output", str(output_path), "--top", top]
    )


# ---------------------------------------------------------------------------
# Ranking: desempate e limites de --top
# ---------------------------------------------------------------------------


def test_top_hotels_tie_break_by_hotel_id_ascending(tmp_path):
    """Empate em total_brl é resolvido por hotel_id ascendente."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H03", "hotel_name": "Hotel C", "amount": "500.00"},
            {"reservation_id": "R-2", "hotel_id": "H01", "hotel_name": "Hotel A", "amount": "500.00"},
            {"reservation_id": "R-3", "hotel_id": "H02", "hotel_name": "Hotel B", "amount": "800.00"},
        ],
    )
    assert [hotel["hotel_id"] for hotel in report["top_hotels"]] == ["H02", "H01", "H03"]


def test_top_larger_than_hotel_count_returns_all(tmp_path):
    """--top maior que o número de hotéis devolve todos, sem erro."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H02", "amount": "200.00"},
        ],
        top=5,
    )
    assert len(report["top_hotels"]) == 2


def test_top_equal_one_returns_only_leader(tmp_path):
    """Limite inferior válido de --top: exatamente 1 item."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H02", "amount": "200.00"},
        ],
        top=1,
    )
    assert [hotel["hotel_id"] for hotel in report["top_hotels"]] == ["H02"]


# ---------------------------------------------------------------------------
# Tamanho do arquivo: limites 0 e 201 linhas
# ---------------------------------------------------------------------------


def test_reads_file_beyond_200_rows(tmp_path):
    """Regressão do truncamento: 201 linhas (limite exato do defeito) são todas lidas."""
    rows = [{"reservation_id": f"R-{i}"} for i in range(1, 202)]
    report = run_cli(tmp_path, rows)
    assert report["summary"]["total_reservations"] == 201
    assert report["summary"]["confirmed_reservations"] == 201


def test_empty_reservation_file_produces_zeroed_report(tmp_path):
    """Arquivo só com cabeçalho: relatório zerado, listas vazias, saída 0."""
    report = run_cli(tmp_path, [])
    assert report["summary"] == {
        "total_reservations": 0,
        "confirmed_reservations": 0,
        "cancelled_reservations": 0,
        "no_show_reservations": 0,
        "total_room_nights": 0,
        "total_amount_brl": "0.00",
        "average_nightly_rate_brl": "0.00",
    }
    assert report["by_month"] == []
    assert report["top_hotels"] == []


# ---------------------------------------------------------------------------
# Datas: limites de calendário e agrupamento mensal
# ---------------------------------------------------------------------------


def test_by_month_uses_checkin_month_for_cross_month_stay(tmp_path):
    """Estadia que cruza o mês conta inteira no mês do check-in."""
    report = run_cli(
        tmp_path,
        [{"reservation_id": "R-1", "checkin_date": "2025-01-30", "checkout_date": "2025-02-02"}],
    )
    assert [month["month"] for month in report["by_month"]] == ["2025-01"]
    assert report["by_month"][0]["room_nights"] == 3


def test_nights_across_year_boundary(tmp_path):
    """Virada de ano: 30/12 a 02/01 são 3 noites, agrupadas em dezembro."""
    report = run_cli(
        tmp_path,
        [{"reservation_id": "R-1", "checkin_date": "2025-12-30", "checkout_date": "2026-01-02"}],
    )
    assert report["summary"]["total_room_nights"] == 3
    assert [month["month"] for month in report["by_month"]] == ["2025-12"]


def test_nights_in_leap_february(tmp_path):
    """Ano bissexto: 28/02 a 01/03 de 2024 são 2 noites (29/02 existe)."""
    report = run_cli(
        tmp_path,
        [{"reservation_id": "R-1", "checkin_date": "2024-02-28", "checkout_date": "2024-03-01"}],
    )
    assert report["summary"]["total_room_nights"] == 2


def test_day_use_checkout_equals_checkin(tmp_path):
    """Limite checkout == checkin: aceito com 0 noites; média cai na regra de zero noites."""
    report = run_cli(
        tmp_path,
        [{"reservation_id": "R-1", "checkout_date": BASE["checkin_date"], "amount": "100.00"}],
    )
    assert report["summary"]["total_room_nights"] == 0
    assert report["summary"]["total_amount_brl"] == "100.00"
    assert report["summary"]["average_nightly_rate_brl"] == "0.00"


# ---------------------------------------------------------------------------
# Quartos: multiplicador acima do limite 1
# ---------------------------------------------------------------------------


def test_room_nights_multiply_by_rooms(tmp_path):
    """3 quartos por 2 noites são 6 room_nights."""
    report = run_cli(
        tmp_path,
        [
            {
                "reservation_id": "R-1",
                "checkin_date": "2025-01-10",
                "checkout_date": "2025-01-12",
                "rooms": "3",
            }
        ],
    )
    assert report["summary"]["total_room_nights"] == 6


# ---------------------------------------------------------------------------
# Dinheiro: limites de arredondamento e valor zero
# ---------------------------------------------------------------------------


def test_money_rounds_half_up_on_serialization(tmp_path):
    """Meio centavo exato arredonda para cima (half-up): 0.125 vira 0.13, não 0.12."""
    report = run_cli(tmp_path, [{"reservation_id": "R-1", "amount": "0.125"}])
    assert report["summary"]["total_amount_brl"] == "0.13"


def test_average_rounds_only_on_serialization(tmp_path):
    """Divisão com dízima (100 / 3 noites) sai com 2 casas: 33.33."""
    report = run_cli(
        tmp_path,
        [
            {
                "reservation_id": "R-1",
                "amount": "100.00",
                "checkin_date": "2025-01-10",
                "checkout_date": "2025-01-13",
            }
        ],
    )
    assert report["summary"]["average_nightly_rate_brl"] == "33.33"


def test_amount_zero_is_accepted(tmp_path):
    """Limite inferior de amount: 0.00 é válido e soma zero."""
    report = run_cli(tmp_path, [{"reservation_id": "R-1", "amount": "0.00"}])
    assert report["summary"]["confirmed_reservations"] == 1
    assert report["summary"]["total_amount_brl"] == "0.00"


# ---------------------------------------------------------------------------
# Status: partição sem faturáveis
# ---------------------------------------------------------------------------


def test_only_non_billable_reservations_zero_totals(tmp_path):
    """Sem CONFIRMED: contagens preenchidas, agregados zerados, listas vazias."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "status": "CANCELLED"},
            {"reservation_id": "R-2", "status": "NO_SHOW"},
        ],
    )
    summary = report["summary"]
    assert summary["total_reservations"] == 2
    assert summary["cancelled_reservations"] == 1
    assert summary["no_show_reservations"] == 1
    assert summary["total_room_nights"] == 0
    assert summary["total_amount_brl"] == "0.00"
    assert summary["average_nightly_rate_brl"] == "0.00"
    assert report["by_month"] == []
    assert report["top_hotels"] == []


# ---------------------------------------------------------------------------
# Comportamento campo a campo da saída: by_month, top_hotels e envelope
# ---------------------------------------------------------------------------


def test_by_month_entries_sorted_and_aggregated(tmp_path):
    """by_month sai em ordem ascendente de mês, com reservations, room_nights e
    total_brl agregados por mês — mesmo com o CSV fora de ordem cronológica."""
    report = run_cli(
        tmp_path,
        [
            {
                "reservation_id": "R-1",
                "checkin_date": "2025-03-10",
                "checkout_date": "2025-03-12",
                "amount": "200.00",
            },
            {
                "reservation_id": "R-2",
                "checkin_date": "2025-01-10",
                "checkout_date": "2025-01-11",
                "amount": "100.00",
            },
            {
                "reservation_id": "R-3",
                "checkin_date": "2025-01-20",
                "checkout_date": "2025-01-22",
                "rooms": "2",
                "currency": "USD",
                "amount": "100.00",
            },
            {
                "reservation_id": "R-4",
                "checkin_date": "2025-02-05",
                "checkout_date": "2025-02-08",
                "currency": "EUR",
                "amount": "50.00",
            },
        ],
    )
    assert report["by_month"] == [
        {"month": "2025-01", "reservations": 2, "room_nights": 5, "total_brl": "642.00"},
        {"month": "2025-02", "reservations": 1, "room_nights": 3, "total_brl": "294.00"},
        {"month": "2025-03", "reservations": 1, "room_nights": 2, "total_brl": "200.00"},
    ]


def test_top_hotels_aggregates_reservations_per_hotel(tmp_path):
    """Várias reservas do mesmo hotel somam room_nights e total_brl (moedas mistas),
    e hotel_name é propagado para o ranking."""
    report = run_cli(
        tmp_path,
        [
            {
                "reservation_id": "R-1",
                "hotel_id": "H01",
                "hotel_name": "Hotel Aurora",
                "amount": "1000.00",
            },
            {
                "reservation_id": "R-2",
                "hotel_id": "H01",
                "hotel_name": "Hotel Aurora",
                "checkin_date": "2025-01-20",
                "checkout_date": "2025-01-22",
                "currency": "USD",
                "amount": "100.00",
            },
            {
                "reservation_id": "R-3",
                "hotel_id": "H02",
                "hotel_name": "Hotel Mirante",
                "amount": "600.00",
            },
        ],
    )
    assert report["top_hotels"] == [
        {"hotel_id": "H01", "hotel_name": "Hotel Aurora", "room_nights": 3, "total_brl": "1542.00"},
        {"hotel_id": "H02", "hotel_name": "Hotel Mirante", "room_nights": 1, "total_brl": "600.00"},
    ]


def test_report_envelope_fields(tmp_path):
    """report_version é fixo em 1.0 e generated_at é ISO-8601 com offset -03:00."""
    from datetime import datetime

    report = run_cli(tmp_path, [{}])
    assert report["report_version"] == "1.0"
    assert report["generated_at"].endswith("-03:00")
    datetime.fromisoformat(report["generated_at"])


def test_money_has_no_thousands_separator(tmp_path):
    """Valores grandes saem sem separador de milhar e com exatamente 2 casas."""
    report = run_cli(tmp_path, [{"reservation_id": "R-1", "amount": "12345.60"}])
    assert report["summary"]["total_amount_brl"] == "12345.60"


def test_informative_columns_do_not_affect_totals(tmp_path):
    """Colunas fora do cálculo (viajante, cidade, pagamento etc.) não mudam os totais."""
    report = run_cli(
        tmp_path,
        [
            {
                "reservation_id": "R-999",
                "traveler_name": "Outra Pessoa, com vírgula",
                "company_id": "EMP-999",
                "city": "Belo Horizonte",
                "country": "AR",
                "payment_method": "INVOICE",
                "booked_at": "2024-12-31T23:59:59-03:00",
            }
        ],
    )
    assert report["summary"]["total_reservations"] == 1
    assert report["summary"]["total_room_nights"] == 1
    assert report["summary"]["total_amount_brl"] == "100.00"


# ---------------------------------------------------------------------------
# Partições inválidas de linha: código de saída 2 com mensagem
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("row", "stderr_fragment"),
    [
        ({"status": "PENDING"}, "status desconhecido"),
        ({"status": "confirmed"}, "status desconhecido"),
        ({"currency": "JPY"}, "moeda sem taxa"),
        ({"checkin_date": "2025-01-10", "checkout_date": "2025-01-05"}, "check-out"),
        ({"rooms": "0"}, "rooms"),
        ({"rooms": "-1"}, "rooms"),
        ({"checkin_date": "2025-13-01"}, "linha 2"),
        ({"rooms": "abc"}, "linha 2"),
        ({"amount": "abc"}, "linha 2"),
        ({"status": ""}, "status desconhecido"),
        ({"currency": ""}, "moeda sem taxa"),
        ({"checkin_date": ""}, "linha 2"),
        ({"rooms": ""}, "linha 2"),
        ({"amount": ""}, "linha 2"),
        ({"checkout_date": "2025/01/13"}, "linha 2"),
        ({"checkin_date": "2025-02-30"}, "linha 2"),
        ({"amount": "R$ 100"}, "linha 2"),
    ],
    ids=[
        "status-desconhecido",
        "status-caixa-baixa",
        "moeda-sem-taxa",
        "checkout-antes-do-checkin",
        "rooms-zero",
        "rooms-negativo",
        "data-malformada",
        "rooms-nao-numerico",
        "amount-nao-numerico",
        "status-vazio",
        "moeda-vazia",
        "checkin-vazio",
        "rooms-vazio",
        "amount-vazio",
        "data-com-barras",
        "data-dia-inexistente",
        "amount-com-simbolo",
    ],
)
def test_invalid_row_exits_2(tmp_path, row, stderr_fragment):
    """Linha semanticamente ou sintaticamente inválida encerra com código 2."""
    process = run_failing_cli(tmp_path, [row])
    assert process.returncode == 2, process.stderr
    assert stderr_fragment in process.stderr


# ---------------------------------------------------------------------------
# Partições inválidas de argumentos e arquivos: código de saída 2
# ---------------------------------------------------------------------------


def test_top_zero_exits_2(tmp_path):
    """Limite inferior inválido de --top."""
    process = run_failing_cli(tmp_path, [{}], top="0")
    assert process.returncode == 2, process.stderr


def test_top_non_integer_exits_2(tmp_path):
    """--top não numérico é rejeitado pelo argparse."""
    process = run_failing_cli(tmp_path, [{}], top="abc")
    assert process.returncode == 2, process.stderr


def test_missing_input_file_exits_2(tmp_path):
    process = run_failing_cli(tmp_path, input_path=tmp_path / "nao-existe.csv")
    assert process.returncode == 2, process.stderr


def test_missing_rates_file_exits_2(tmp_path):
    process = run_failing_cli(tmp_path, [{}], rates_path=tmp_path / "nao-existe.csv")
    assert process.returncode == 2, process.stderr


@pytest.mark.parametrize(
    ("rates_text", "stderr_fragment"),
    [
        ("currency,rate_to_brl\n", "vazia"),
        ("currency,rate_to_brl\nBRL,abc\n", "taxa"),
        ("currency,rate_to_brl\nBRL,0\n", "positiva"),
        ("currency,rate_to_brl\nBRL,-2\n", "positiva"),
        ("currency,rate_to_brl\nBRL,\n", "incompleta"),
        ("currency,taxa\nBRL,1.000000\n", "rate_to_brl"),
    ],
    ids=[
        "tabela-vazia",
        "taxa-nao-numerica",
        "taxa-zero",
        "taxa-negativa",
        "linha-incompleta",
        "coluna-ausente",
    ],
)
def test_invalid_rates_file_exits_2(tmp_path, rates_text, stderr_fragment):
    """Tabela de câmbio inválida encerra com código 2 e mensagem específica."""
    rates_path = tmp_path / "rates_invalidas.csv"
    rates_path.write_text(rates_text, encoding="utf-8")
    process = run_failing_cli(tmp_path, [{}], rates_path=rates_path)
    assert process.returncode == 2, process.stderr
    assert stderr_fragment in process.stderr


def test_top_negative_exits_2(tmp_path):
    """Partição inválida de --top abaixo do limite 0."""
    process = run_failing_cli(tmp_path, [{}], top="-1")
    assert process.returncode == 2, process.stderr


def test_missing_required_arguments_exit_2():
    """Sem --input e --rates, o argparse rejeita com código 2."""
    process = _run_cli_process([])
    assert process.returncode == 2, process.stderr


def test_missing_required_column_exits_2(tmp_path):
    """Cabeçalho sem a coluna amount é rejeitado nomeando a coluna."""
    columns = [column for column in COLUMNS if column != "amount"]
    process = run_failing_cli(tmp_path, [{}], columns=columns)
    assert process.returncode == 2, process.stderr
    assert "amount" in process.stderr
