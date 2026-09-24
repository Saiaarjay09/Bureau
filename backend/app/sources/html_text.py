"""Convert a job posting's HTML into plain text, at ingest time.

Job boards return descriptions as HTML (Remotive's run to ~36KB of it).
Storing that raw and rendering it in the frontend would mean injecting
third-party markup straight into the logged-in page — a malicious or
compromised posting could read the session cookie. Since the app is now
reachable from the open internet, that's a live risk rather than a
theoretical one.

Sanitising HTML properly means an allowlist parser and a dependency that
has to stay patched. Job descriptions lose almost nothing as plain text,
so this converts instead: no markup survives, so there is nothing to
sanitise, and the frontend can render it as ordinary text. Block-level
tags become line breaks and list items get a bullet, which is enough
structure to stay readable.
"""

import re
from html.parser import HTMLParser

# Tags whose content is never text to show a reader.
_SKIP_CONTENT = {"script", "style", "noscript", "head", "title"}

# Tags that should force a line break when they open or close.
_BLOCK = {
    "p", "div", "br", "tr", "section", "article", "header", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "blockquote", "pre",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_CONTENT:
            self._skip_depth += 1
        elif tag == "li":
            self.parts.append("\n• ")
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_CONTENT:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def html_to_text(html: str | None, max_chars: int = 20_000) -> str | None:
    """Returns readable plain text, or None for empty/unparseable input.
    Truncated at max_chars — a description is for a person to read and for
    Sabha to decompose, and neither needs 36KB of boilerplate footer."""
    if not html or not html.strip():
        return None

    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        # A malformed posting shouldn't take an ingest run down; fall back
        # to a blunt tag strip rather than losing the description entirely.
        return _collapse(re.sub(r"<[^>]*>", " ", html))[:max_chars] or None

    text = _collapse("".join(parser.parts))
    if not text:
        return None
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n[…truncated]"
    return text


def _collapse(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
