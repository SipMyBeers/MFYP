from textual.widgets import RichLog

class LeopardRichLog(RichLog):
    def write(self, content):
        # Clean output with no extra blocks for easy copying
        super().write(content)
