"""Fixture: method with self, async function, and skip marker."""


class Widget:
    def paint(self, color):
        return color.upper()


async def load(path):
    return path.read_text()


# llm-cst: skip
def ignored(x):
    return x
