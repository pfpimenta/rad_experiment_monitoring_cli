import time
import re
import datetime
from pathlib import Path
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout

class Dashboard:
    """Handles the visual representation of the monitoring data."""
    
    @staticmethod
    def generate(device_data, model_data, latest_lines, global_latest_ts=None) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="upper_pane", ratio=3),
            Layout(name="model_summary", ratio=2)
        )
        
        layout["upper_pane"].split_row(
            Layout(name="device_summary", ratio=3),
            Layout(name="tail_pane", ratio=2)
        )

        layout["device_summary"].update(
            Panel(Dashboard._create_device_table(device_data, global_latest_ts), 
                  title="Device Overview", border_style="blue")
        )
        
        layout["model_summary"].update(
            Panel(Dashboard._create_model_table(model_data, global_latest_ts), 
                  title="Benchmark Logs", border_style="yellow")
        )

        layout["tail_pane"].update(
            Panel(Dashboard._format_tail_text(latest_lines), 
                  title="Live Active Log Output", border_style="green")
        )

        return layout

    @staticmethod
    def _create_device_table(device_data, global_latest_ts=None):
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Device Name", style="bold white")
        table.add_column("Log Files", justify="right")
        table.add_column("SDCs", justify="right")
        table.add_column("Last SDC", justify="right")
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
            
            last_sdc_ts = info.get("last_sdc_timestamp")
            if last_sdc_ts and global_latest_ts:
                elapsed_sdc = global_latest_ts - last_sdc_ts
                if elapsed_sdc < 0: elapsed_sdc = 0
                last_sdc_str = Dashboard._format_elapsed_time(elapsed_sdc)
            else:
                last_sdc_str = "[dim]Never[/dim]"

            last_update = info.get("last_update_time")
            if last_update is None:
                status_str = "[dim]Never[/dim]"
            else:
                elapsed = current_time - last_update
                status_str = Dashboard._format_elapsed_time(elapsed)

            table.add_row(device, str(num_logs), f"[{sdc_style}]{sdc_count}[/{sdc_style}]", last_sdc_str, status_str)

        table.add_section() 
        table.add_row("TOTAL", str(total_logs), f"[bold magenta]{total_sdcs}[/bold magenta]", "", "")
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
    def _create_model_table(model_data, global_latest_ts=None):
        table = Table(show_header=True, header_style="bold yellow", expand=True)
        table.add_column("Model Name", style="bold white")
        table.add_column("Logs", justify="right")
        table.add_column("SDCs", justify="right")
        table.add_column("First Timestamp", justify="right")
        table.add_column("Last Timestamp", justify="right")
        table.add_column("Time Span", justify="right")
        table.add_column("Last SDC", justify="right")
        table.add_column("SDC Rate", justify="right")
        table.add_column("Last Update", justify="right")

        current_time = time.time()

        for model, info in sorted(model_data.items()):
            num_logs = len(info["logs"])
            sdc_count = info["sdcs"]
            sdc_style = "bold red" if sdc_count > 0 else "green"
            
            last_update = info.get("last_update_time")
            if last_update is None:
                status_str = "[dim]Never[/dim]"
            else:
                elapsed = current_time - last_update
                status_str = Dashboard._format_elapsed_time(elapsed)

            duration_str, rate_str, first_ts, last_ts, last_sdc_str = Dashboard._calculate_model_metrics(info, global_latest_ts)

            table.add_row(
                model, 
                str(num_logs), 
                f"[{sdc_style}]{sdc_count}[/{sdc_style}]", 
                first_ts,
                last_ts,
                duration_str,
                last_sdc_str,
                rate_str,
                status_str
            )
        
        return table

    @staticmethod
    def _parse_log_start_time(filename: str) -> float | None:
        match = re.match(r'^(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_', filename)
        if match:
            try:
                dt = datetime.datetime(
                    year=int(match.group(1)),
                    month=int(match.group(2)),
                    day=int(match.group(3)),
                    hour=int(match.group(4)),
                    minute=int(match.group(5)),
                    second=int(match.group(6))
                )
                return dt.timestamp()
            except ValueError:
                pass
        return None

    @staticmethod
    def _calculate_model_metrics(info, global_latest_ts=None):
        """Calculates running duration and SDC rate for a model.
        
        Returns:
            duration_str: formatted time span (e.g. '2h 15m' or '45s' or 'N/A')
            rate_str: formatted SDC rate (e.g. '1.50/hr' or '0.05/min' or '0.00/hr')
            first_ts_str: formatted first timestamp
            last_ts_str: formatted last timestamp
            last_sdc_str: formatted time since last SDC
        """
        log_paths = info.get("log_paths", set())
        if not log_paths:
            return "0s", "0.00/hr", "N/A", "N/A", "[dim]Never[/dim]"

        # Find earliest start time and latest end time (mtime)
        earliest_start = None
        latest_end = None

        for path in log_paths:
            start_t = Dashboard._parse_log_start_time(path.name)
            end_t = Dashboard._parse_log_end_time(path, start_t)

            if start_t is not None:
                start_t = int(start_t)
                if earliest_start is None or start_t < earliest_start:
                    earliest_start = start_t
            if end_t is not None:
                end_t = int(end_t)
                if latest_end is None or end_t > latest_end:
                    latest_end = end_t

        if earliest_start is None or latest_end is None:
            return "N/A", "N/A", "N/A", "N/A", "[dim]Never[/dim]"

        # Format timestamps
        first_ts_str = datetime.datetime.fromtimestamp(earliest_start).strftime("%Y-%m-%d %H:%M:%S")
        last_ts_str = datetime.datetime.fromtimestamp(latest_end).strftime("%Y-%m-%d %H:%M:%S")

        duration = latest_end - earliest_start
        if duration < 0:
            duration = 0.0

        # Format duration string
        if duration < 60:
            duration_str = f"{int(duration)}s"
        elif duration < 3600:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration_str = f"{minutes}m {seconds}s"
        else:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            duration_str = f"{hours}h {minutes}m"

        # Calculate Last SDC
        last_sdc_ts = info.get("last_sdc_timestamp")
        if last_sdc_ts and global_latest_ts:
            # Use global_latest_ts as the reference "now"
            elapsed_sdc = global_latest_ts - last_sdc_ts
            if elapsed_sdc < 0: elapsed_sdc = 0
            last_sdc_str = Dashboard._format_elapsed_time(elapsed_sdc)
        else:
            last_sdc_str = "[dim]Never[/dim]"

        # Calculate SDC rate
        sdc_count = info.get("sdcs", 0)
        if duration == 0:
            rate_str = "0.00/hr"
        else:
            rate_per_sec = sdc_count / duration
            rate_per_hour = rate_per_sec * 3600
            rate_per_min = rate_per_sec * 60

            if rate_per_hour >= 1.0:
                rate_str = f"{rate_per_hour:.2f}/hr"
            elif rate_per_min >= 0.01:
                rate_str = f"[yellow]{rate_per_min:.2f}/min[/yellow]"
            else:
                rate_str = f"{rate_per_hour:.4f}/hr"

        return duration_str, rate_str, first_ts_str, last_ts_str, last_sdc_str

    @staticmethod
    def _parse_log_end_time(path: Path, start_t: float | None) -> float | None:
        """Attempts to parse the end time of a log from its content, avoiding system clock."""
        try:
            size = path.stat().st_size
            with open(path, 'rb') as f:
                header = f.read(4096).decode('utf-8', errors='ignore')
                if size > 4096:
                    f.seek(size - 4096)
                else:
                    f.seek(0)
                footer = f.read().decode('utf-8', errors='ignore')

            # Try to find content start time to calculate duration
            content_start = None
            start_match = re.search(r'#SERVER_BEGIN Y:(\d+) M:(\d+) D:(\d+) TIME:(\d+):(\d+):(\d+)', header)
            if start_match:
                try:
                    dt_start = datetime.datetime(
                        year=int(start_match.group(1)),
                        month=int(start_match.group(2)),
                        day=int(start_match.group(3)),
                        hour=int(start_match.group(4)),
                        minute=int(start_match.group(5)),
                        second=int(start_match.group(6))
                    )
                    content_start = dt_start.timestamp()
                except ValueError:
                    pass

            # Try to find content end time (SERVER_DUE or last IT)
            content_end = None
            due_match = re.findall(r'#SERVER_DUE:.*?TIME:(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})', footer)
            if due_match:
                last_m = due_match[-1]
                try:
                    dt_end = datetime.datetime(
                        year=int(last_m[0]), month=int(last_m[1]), day=int(last_m[2]),
                        hour=int(last_m[3]), minute=int(last_m[4]), second=int(last_m[5])
                    )
                    content_end = dt_end.timestamp()
                except ValueError:
                    pass
            
            if content_end is None:
                # Fallback to last #IT AccTime
                it_matches = re.findall(r'#IT \d+ .*?AccTime:([\d.]+)', footer)
                if it_matches:
                    last_acc_time = float(it_matches[-1])
                    if content_start:
                        content_end = content_start + last_acc_time
                    elif start_t:
                        # Assume AccTime is relative to filename start if no #SERVER_BEGIN found
                        return start_t + last_acc_time

            # If we have both content start and end, we can calculate duration
            # and apply it to the filename start_t to stay in the 1970 timeline if needed
            if content_start is not None and content_end is not None and start_t is not None:
                duration = content_end - content_start
                return start_t + duration
            
            return content_end or start_t
        except Exception:
            return start_t


    @staticmethod
    def _format_tail_text(lines):
        if not lines:
            return "Waiting for log events..."
        
        text = "\n".join(lines)
        text = text.replace("SDC", "[bold blink red]SDC[/bold blink red]")
        text = text.replace("sdc", "[bold blink red]sdc[/bold blink red]")
        return text
