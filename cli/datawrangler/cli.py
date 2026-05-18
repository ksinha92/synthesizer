"""DataWrangler CLI — TDM operations from the command line."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from datawrangler.client import DataWranglerClient

console = Console()


@click.group()
@click.option("--url", envvar="DATAWRANGLER_URL", default="http://localhost:8000", help="DataWrangler API URL")
@click.option("--api-key", envvar="DATAWRANGLER_API_KEY", default="", help="API key (prefer DATAWRANGLER_API_KEY env var)")
@click.pass_context
def main(ctx, url, api_key):
    """DataWrangler CLI — Test Data Management from the command line."""
    if api_key and "--api-key" in sys.argv:
        console.print("[yellow]Warning:[/yellow] API key passed as flag — consider using DATAWRANGLER_API_KEY env var instead (flags appear in shell history)")
    ctx.ensure_object(dict)
    ctx.obj["client"] = DataWranglerClient(base_url=url, api_key=api_key)


@main.command()
@click.option("--project", required=True, help="Project ID")
@click.option("--connection", required=True, help="Connection ID")
@click.pass_context
def discover(ctx, project, connection):
    """Run schema discovery + PII detection."""
    client: DataWranglerClient = ctx.obj["client"]
    console.print(f"Starting discovery for connection {connection[:8]}...")
    job_id = client.discover(project, connection)
    console.print(f"Job dispatched: [bold]{job_id}[/bold]")
    result = client.poll_job(project, job_id)
    _print_job_result(result)


@main.command()
@click.option("--project", required=True, help="Project ID")
@click.option("--policy", required=True, help="Masking policy ID")
@click.option("--connection", required=True, help="Connection ID")
@click.pass_context
def mask(ctx, project, policy, connection):
    """Execute data masking."""
    client: DataWranglerClient = ctx.obj["client"]
    console.print(f"Starting masking with policy {policy[:8]}...")
    job_id = client.mask(project, policy, connection)
    console.print(f"Job dispatched: [bold]{job_id}[/bold]")
    result = client.poll_job(project, job_id)
    _print_job_result(result)


@main.command()
@click.option("--project", required=True, help="Project ID")
@click.option("--config", required=True, help="Synthetic config ID")
@click.pass_context
def generate(ctx, project, config):
    """Generate synthetic data."""
    client: DataWranglerClient = ctx.obj["client"]
    console.print(f"Starting generation with config {config[:8]}...")
    job_id = client.generate(project, config)
    console.print(f"Job dispatched: [bold]{job_id}[/bold]")
    result = client.poll_job(project, job_id)
    _print_job_result(result)


@main.command()
@click.option("--project", required=True, help="Project ID")
@click.option("--config", required=True, help="Subset config ID")
@click.pass_context
def subset(ctx, project, config):
    """Execute data subsetting."""
    client: DataWranglerClient = ctx.obj["client"]
    console.print(f"Starting subset with config {config[:8]}...")
    job_id = client.subset(project, config)
    console.print(f"Job dispatched: [bold]{job_id}[/bold]")
    result = client.poll_job(project, job_id)
    _print_job_result(result)


@main.command("workflow")
@click.option("--project", required=True, help="Project ID")
@click.option("--id", "workflow_id", required=True, help="Workflow ID")
@click.pass_context
def workflow_run(ctx, project, workflow_id):
    """Execute a workflow."""
    client: DataWranglerClient = ctx.obj["client"]
    console.print(f"Starting workflow {workflow_id[:8]}...")
    job_id = client.workflow_run(project, workflow_id)
    console.print(f"Job dispatched: [bold]{job_id}[/bold]")
    result = client.poll_job(project, job_id)
    _print_job_result(result)


@main.command()
@click.option("--project", required=True, help="Project ID")
@click.option("--job", required=True, help="Job ID")
@click.pass_context
def status(ctx, project, job):
    """Check job status."""
    client: DataWranglerClient = ctx.obj["client"]
    result = client.get_job(project, job)
    _print_job_result(result)


@main.command()
@click.option("--project", required=True, help="Project ID")
@click.pass_context
def jobs(ctx, project):
    """List recent jobs."""
    client: DataWranglerClient = ctx.obj["client"]
    job_list = client.list_jobs(project)
    table = Table(title="Recent Jobs")
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Progress")
    table.add_column("Started")
    for j in job_list:
        status_style = {"completed": "green", "failed": "red", "running": "blue", "pending": "yellow"}.get(j["status"], "")
        table.add_row(j["id"][:8], j["job_type"], f"[{status_style}]{j['status']}[/{status_style}]", f"{j['progress']}%", j.get("started_at", "—"))
    console.print(table)


def _print_job_result(job: dict):
    status = job["status"]
    style = {"completed": "green", "failed": "red", "running": "blue"}.get(status, "yellow")
    console.print(f"\n[{style} bold]{status.upper()}[/{style} bold] — {job['job_type']} ({job['progress']}%)")
    if job.get("error_message"):
        console.print(f"[red]Error: {job['error_message']}[/red]")


if __name__ == "__main__":
    main()
