"""Command-line interface for workday-sync."""

from __future__ import annotations

from pathlib import Path

import click
import pytz

from workday_sync.ics_builder import build_ics
from workday_sync.parser import parse_xlsx


@click.group()
def cli() -> None:
    """workday-sync: Convert a Workday absence export to a Google Calendar ICS file."""


@cli.command()
@click.argument("input_xlsx", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Output ICS file path. Defaults to stdout.",
)
@click.option(
    "--timezone",
    "-t",
    default="Europe/London",
    show_default=True,
    help="IANA timezone name for event datetimes (e.g. Europe/London, America/New_York).",
)
@click.option(
    "--out-of-office",
    is_flag=True,
    default=False,
    help=(
        "Add X-MICROSOFT-CDO-BUSYSTATUS:OOF to each event. "
        "Recognised by Outlook/Exchange; Google Calendar cannot import OOF event types "
        "via ICS and will treat these as regular busy events regardless."
    ),
)
@click.option(
    "--gcal",
    is_flag=True,
    default=False,
    help=(
        "Push absences directly to Google Calendar as native Out of Office events. "
        "Opens a browser for OAuth authentication on first use. "
        "Token is cached at ~/.config/workday-sync/token.json."
    ),
)
@click.option(
    "--calendar-id",
    default="primary",
    show_default=True,
    help="Google Calendar ID to create events in (e.g. 'primary' or 'team@example.com').",
)
@click.option(
    "--client-secrets",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Path to OAuth client_secret.json from Google Cloud Console. "
        "Defaults to ~/.config/workday-sync/client_secret.json."
    ),
)
def convert(
    input_xlsx: Path,
    output: Path | None,
    timezone: str,
    out_of_office: bool,
    gcal: bool,
    calendar_id: str,
    client_secrets: Path | None,
) -> None:
    """Convert INPUT_XLSX (a Workday absence export) to an ICS file.

    INPUT_XLSX is the path to the .xlsx file downloaded from the Workday
    'My Absence' page.

    By default the ICS content is written to stdout. Use --output to write
    to a file instead.

    \b
    Examples:
      workday-sync convert absences.xlsx
      workday-sync convert absences.xlsx --output calendar.ics
      workday-sync convert absences.xlsx --timezone America/New_York --out-of-office
      workday-sync convert absences.xlsx --gcal
      workday-sync convert absences.xlsx --gcal --output calendar.ics
    """
    # Validate timezone before doing any work
    try:
        pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise click.BadParameter(
            f"{timezone!r} is not a valid IANA timezone. "
            "See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            param_hint="--timezone",
        )

    result = parse_xlsx(input_xlsx)
    for warning in result.warnings:
        click.echo(f"Warning: {warning}", err=True)

    if gcal:
        if out_of_office and output is None:
            click.echo(
                "Warning: --out-of-office has no effect when --gcal is used without --output.",
                err=True,
            )
        from workday_sync import gcal_client  # noqa: PLC0415

        secrets_path = client_secrets or gcal_client._DEFAULT_SECRETS_PATH
        try:
            creds = gcal_client.get_credentials(client_secrets_path=secrets_path)
            service = gcal_client.build_service(creds)
            created = gcal_client.push_events(
                result.requests, service, calendar_id=calendar_id, timezone=timezone
            )
            click.echo(f"Created {len(created)} event(s) in Google Calendar.", err=True)
        except FileNotFoundError as exc:
            raise click.ClickException(str(exc)) from exc
        except Exception as exc:  # googleapiclient.errors.HttpError or similar
            try:
                from googleapiclient.errors import HttpError  # noqa: PLC0415

                if isinstance(exc, HttpError):
                    raise click.ClickException(
                        f"Google Calendar API error: {exc.status_code} {exc.reason}"
                    ) from exc
            except ImportError:
                pass
            raise click.ClickException(str(exc)) from exc

    if output is not None or not gcal:
        ics_content = build_ics(result.requests, timezone=timezone, out_of_office=out_of_office)
        if output is None:
            click.echo(ics_content, nl=False)
        else:
            output.write_text(ics_content, encoding="utf-8")
            click.echo(f"Written to {output}", err=True)
