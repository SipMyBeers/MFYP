# SUPERSEDED — pre-Gormers DittoMeThis era file. Kept for reference.
import subprocess
import asyncio
import pyperclip
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, ListItem, Label, ListView
from textual.containers import Horizontal, VerticalScroll

class ApfelChat(App):
    CSS_PATH = "aesthetic.css"
    output_history = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main_layout"):
            yield ListView(id="memory_bank")
            with VerticalScroll(id="output_container"):
                yield Label(id="thought_stream")
        yield Input(placeholder="Mission Order for Apfel...")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input:
            return

        output_widget = self.query_one("#thought_stream")
        memory_list = self.query_one("#memory_bank")
        
        # Identity Header
        self.output_history.append(f"[bold #FF1010]SIPMYBEERS > [/][#00C8FF]{user_input}[/]")
        output_widget.update("\n".join(self.output_history))
        
        memory_list.append(ListItem(Label(f"[#FF1010]░ {user_input[:12]}...[/#FF1010]")))
        event.input.value = ""

        try:
            process = await asyncio.create_subprocess_exec(
                'apfel', user_input,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.output_history.append("[italic #00C8FF]HUNTING...[/]")
            output_widget.update("\n".join(self.output_history))

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode().strip()
                self.output_history.append(f"[#00C8FF]{decoded_line}[/]")
                output_widget.update("\n".join(self.output_history))
            
            # AUTO-COPY TO CLIPBOARD:
            # We strip the Rich tags so you get clean SQL/Code
            clean_text = "\n".join(self.output_history)
            import re
            clean_text = re.sub(r'\[.*?\]', '', clean_text)
            pyperclip.copy(clean_text)

        except Exception as e:
            self.output_history.append(f"[bold red]SYSTEM_FAULT: {str(e)}[/]")
            output_widget.update("\n".join(self.output_history))

if __name__ == "__main__":
    app = ApfelChat()
    app.run()
