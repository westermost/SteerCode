import sys, os
from typing import List, Tuple

class C:
    RST = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    GREEN = "\033[32m"; BGREEN = "\033[92m"; YELLOW = "\033[33m"
    RED = "\033[31m"; WHITE = "\033[97m"; GRAY = "\033[90m"
    BLACK = "\033[30m"; BG_GREEN = "\033[42m"

def _cols() -> int:
    try: return os.get_terminal_size().columns
    except Exception: return 80

def banner():
    w = min(_cols(), 62)
    g = C.BGREEN
    print(f"""
{g}{C.BOLD}  ╔{'═'*(w-4)}╗{C.RST}
{g}{C.BOLD}  ║{C.RST}{g}  ███████╗████████╗███████╗███████╗██████╗   {C.BOLD}║{C.RST}
{g}{C.BOLD}  ║{C.RST}{g}  ██╔════╝╚══██╔══╝██╔════╝██╔════╝██╔══██╗  {C.BOLD}║{C.RST}
{g}{C.BOLD}  ║{C.RST}{g}  ███████╗   ██║   █████╗  █████╗  ██████╔╝  {C.BOLD}║{C.RST}
{g}{C.BOLD}  ║{C.RST}{g}  ╚════██║   ██║   ██╔══╝  ██╔══╝  ██╔══██╗  {C.BOLD}║{C.RST}
{g}{C.BOLD}  ║{C.RST}{g}  ███████║   ██║   ███████╗███████╗██║  ██║  {C.BOLD}║{C.RST}
{g}{C.BOLD}  ║{C.RST}{g}  ╚══════╝   ╚═╝   ╚══════╝╚══════╝╚═╝  ╚═╝  {C.BOLD}║{C.RST}
{g}{C.BOLD}  ║{C.RST}{C.GREEN}       C O D E  {C.BGREEN}{C.BOLD}▸ Scan. Map. Steer.{C.RST}{g}        {C.BOLD}║{C.RST}
{g}{C.BOLD}  ╚{'═'*(w-4)}╝{C.RST}
""")

def phase_header(num: int, total: int, text: str):
    print(f"  {C.BGREEN}[{num}/{total}]{C.RST} {C.GREEN}{text}{C.RST}")

def phase_done(text: str, elapsed: float):
    print(f"  {C.BGREEN}  ✓{C.RST} {C.GREEN}{text}{C.RST} {C.DIM}{C.GREEN}({elapsed:.1f}s){C.RST}")

def phase_item(text: str):
    print(f"  {C.GREEN}    {text}{C.RST}")

def progress_bar(current: int, total: int, label: str, width: int = 25):
    pct = current / total if total else 1
    filled = int(width * pct)
    bar = f"{C.BGREEN}{'█'*filled}{C.GREEN}{'░'*(width-filled)}{C.RST}"
    pct_str = f"{pct*100:3.0f}%"
    counter = f"{current}/{total}"
    max_label = max(8, _cols() - width - len(counter) - len(pct_str) - 14)
    sys.stdout.write(f"\r\033[K  {C.GREEN}  {bar} {C.DIM}{pct_str} {counter}{C.RST} {C.GREEN}{label[:max_label]}{C.RST}")
    sys.stdout.flush()
    if current == total: sys.stdout.write("\n")

def table(rows: List[Tuple[str, str]], indent: int = 6):
    if not rows: return
    max_k = max(len(r[0]) for r in rows)
    for k, v in rows:
        print(f"{' '*indent}{C.GREEN}{k:<{max_k}}{C.RST}  {C.BGREEN}{v}{C.RST}")

def summary_box(lines: List[str]):
    w = min(_cols(), 62)
    print(f"\n  {C.BGREEN}{C.BOLD}╔{'═'*(w-4)}╗{C.RST}")
    for line in lines:
        print(f"  {C.BGREEN}{C.BOLD}║{C.RST} {line}")
    print(f"  {C.BGREEN}{C.BOLD}╚{'═'*(w-4)}╝{C.RST}\n")

def prompt(label: str, default: str = "", options: List[str] = None) -> str:
    hint = f" {C.GREEN}{C.DIM}({'/'.join(options)}){C.RST}" if options else ""
    dflt = f" {C.BGREEN}[{default}]{C.RST}" if default else ""
    sys.stdout.write(f"  {C.BGREEN}▸{C.RST} {C.GREEN}{label}{hint}{dflt}{C.GREEN}: {C.RST}")
    sys.stdout.flush()
    val = input().strip()
    if not val: return default
    if options:
        for opt in options:
            if opt.startswith(val.lower()): return opt
        print(f"    {C.YELLOW}⚠ Invalid, using: {default}{C.RST}")
        return default
    return val
