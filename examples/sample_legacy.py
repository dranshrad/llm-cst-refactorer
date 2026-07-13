# Example legacy module used in README walkthroughs.
# Intentionally under-annotated / undocumented.


def greet(name, times=1):
    # Preserve this comment when refactoring.
    return ("hello " + name + "! ") * times


class Counter:
    def __init__(self, start):
        self.value = start

    def bump(self, step):
        self.value += step
        return self.value


async def fetch_title(url):
    return url.rsplit("/", 1)[-1]


# llm-cst: skip
def leave_me_alone(x):
    return x
