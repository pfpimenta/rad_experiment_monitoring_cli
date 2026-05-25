import time
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout

class Dashboard:
    """Handles the visual representation of the monitoring data."""
    
    @staticmethod
    def generate(device_data, model_data, latest_lines) -> Layout:
        layout = Layout()
        layout.split_row(
            Layout(name="table_pane", ratio=3),
            Layout(name="tail_pane", ratio=2)
        )
        
        layout["table_pane"].split_column(
            Layout(name="device_summary"),
            Layout(name="model_summary")
        )

        layout["device_summary"].update(
            Panel(Dashboard._create_device_table(device_data), 
                  title="Device Overview", border_style="blue")
        )
        
        layout["model_summary"].update(
            Panel(Dashboard._create_model_table(model_data), 
                  title="Model-wise Breakdown", border_style="yellow")
        )

        layout["tail_pane"].update(
            Panel(Dashboard._format_tail_text(latest_lines), 
                  title="Live Active Log Output", border_style="green")
        )

        return layout

    @staticmethod
    def _create_device_table(device_data):
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Device Name", style="bold white")
        table.add_column("Log Files", justify="right")
        table.add_column("SDCs Found", justify="right")
        table.add_column("Last Update", justify="right")

        total_logs = 0
        total_sdcs = 0
        current_time = time.time()

        for device, info in sorted(device_data.items()):
            num_logs = len(info["logs"])
            sdc_count = info["sdcs"]
            total_logs += num_logs
            total_sdcs += sdc_count
            sdc_style = "bold red" if sdc_count > 0 else "green"
            
            last_update = info.get("last_update_time")
            if last_update is None:
                status_str = "[dim]Never[/dim]"
            else:
                elapsed = current_time - last_update
                status_str = Dashboard._format_elapsed_time(elapsed)

            table.add_row(device, str(num_logs), f"[{sdc_style}]{sdc_count}[/{sdc_style}]", status_str)

        table.add_section() 
        table.add_row("TOTAL", str(total_logs), f"[bold magenta]{total_sdcs}[/bold magenta]", "")
        return table

    @staticmethod
    def _format_elapsed_time(elapsed: float) -> str:
        if elapsed < 0:
            elapsed = 0
        
        if elapsed < 10:
            return f"[bold green]Just now ({int(elapsed)}s)[/bold green]"
        elif elapsed < 60:
            return f"[green]{int(elapsed)}s ago[/green]"
        elif elapsed < 3600:
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            return f"[yellow]{minutes}m {seconds}s ago[/yellow]"
        else:
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            return f"[bold red]{hours}h {minutes}m ago[/bold red]"

    @staticmethod
    def _create_model_table(model_data):
        table = Table(show_header=True, header_style="bold yellow", expand=True)
        table.add_column("Device", style="dim white")
        table.add_column("Model Name", style="bold white")
        table.add_column("Logs", justify="right")
        table.add_column("SDCs", justify="right")

        for (device, model), info in sorted(model_data.items()):
            num_logs = len(info["logs"])
            sdc_count = info["sdcs"]
            sdc_style = "bold red" if sdc_count > 0 else "green"
            table.add_row(device, model, str(num_logs), f"[{sdc_style}]{sdc_count}[/{sdc_style}]")
        
        return table

    @staticmethod
    def _format_tail_text(lines):
        if not lines:
            return "Waiting for log events..."
        
        text = "\n".join(lines)
        text = text.replace("SDC", "[bold blink red]SDC[/bold blink red]")
        text = text.replace("sdc", "[bold blink red]sdc[/bold blink red]")
        return text
