import subprocess
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, ListItem, ListView
from textual.containers import Horizontal

class ApfelChat(App):
    # THEME: Red/Black/Cyan stipple aesthetic
    CSS = """
    Screen { background: #000000; }
    Header { background: #FF0000; color: #00FFFF; text-style: bold; }
    Footer { background: #000000; color: #FF0000; }
    #main_layout { layout: horizontal; }
    #thought_stream { 
        width: 75%; 
        border: solid #00FFFF; 
        background: #000000; 
        color: #00FFFF;
    }
    #memory_bank { 
        width: 25%; 
        border: solid #FF0000; 
        background: #000000; 
        color: #FF0000; 
    }
    Input { 
        dock: bottom; 
        border: thick #FF0000; 
        background: #000000; 
        color: #00FFFF;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main_layout"):
            yield ListView(id="memory_bank")
            yield RichLog(id="thought_stream", wrap=True, highlight=True, markup=True)
        yield Input(placeholder="Mission Order for Apfel...")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input:
            return

        log = self.query_one("#thought_stream")
        # Visual feedback: SipMyBeers Identity
        log.write(f"[bold red]░ SIPMYBEERS > [/bold red][cyan]{user_input}[/cyan]")
        event.input.value = ""

        try:
            # REAL-TIME STREAMING: Read stdout line by line
            process = await asyncio.create_subprocess_exec(
                'apfel', user_input,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            log.write("[italic red]░ HUNTING...[/italic red]")

            # Loop through lines as they arrive
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode().strip()
                # Simulate the 'OpenCode' streaming feel
                log.write(f"[cyan]░ {decoded_line}[/cyan]")
            
            # Update memory bank
            self.query_one("#memory_bank").append(ListItem(user_input[:20] + "..."))
            
        except Exception as e:
            log.write(f"[bold red]SYSTEM_FAULT: {str(e)}[/bold red]")

if __name__ == "__main__":
    app = ApfelChat()
    app.run()
